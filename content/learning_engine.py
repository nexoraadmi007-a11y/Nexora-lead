import logging
from typing import Dict, List, Tuple, Optional
import anthropic
from config import CLAUDE_API_KEY, CLAUDE_MODEL

logger = logging.getLogger(__name__)

_client = None

_PROBLEM_KEYWORDS = {"problem", "mistake", "losing", "missing", "why", "secret", "hidden", "costing", "forgetting", "stealing"}
_DEMO_KEYWORDS    = {"result", "24 hours", "setup", "system", "transform", "booked", "inquiries", "messages", "before", "after"}


def _get_client():
    global _client
    if _client is None:
        _client = anthropic.Anthropic(api_key=CLAUDE_API_KEY)
    return _client


def analyze_patterns(scored_posts: List[Dict]) -> Dict:
    if not scored_posts:
        return {}

    scaled = [p for p in scored_posts if p.get("classification") == "SCALE"]
    weak   = [p for p in scored_posts if p.get("classification") in ("WEAK", "DROP")]

    winning_hooks = [p.get("caption", "")[:80] for p in scaled]
    weak_formats  = [p.get("caption", "")[:80] for p in weak]

    platform_avg: Dict[str, float] = {}
    for p in scored_posts:
        plat = p.get("platform", "unknown")
        platform_avg.setdefault(plat, []).append(p.get("total_score", 0))
    best_platform = max(
        platform_avg,
        key=lambda k: sum(platform_avg[k]) / len(platform_avg[k]),
        default="",
    ) if platform_avg else ""

    problem_scores = [p.get("total_score", 0) for p in scored_posts
                      if any(w in p.get("caption", "").lower() for w in _PROBLEM_KEYWORDS)]
    demo_scores    = [p.get("total_score", 0) for p in scored_posts
                      if any(w in p.get("caption", "").lower() for w in _DEMO_KEYWORDS)]

    avg_problem = sum(problem_scores) / max(len(problem_scores), 1)
    avg_demo    = sum(demo_scores)    / max(len(demo_scores), 1)
    winning_type = "Problem/Insight" if avg_problem >= avg_demo else "Demo/Conversion"

    avg_score = sum(p.get("total_score", 0) for p in scored_posts) / max(len(scored_posts), 1)

    return {
        "winning_hook":         winning_hooks[0] if winning_hooks else "",
        "winning_content_type": winning_type,
        "weak_format":          weak_formats[0] if weak_formats else "",
        "best_platform":        best_platform,
        "scaled_count":         len(scaled),
        "weak_count":           len(weak),
        "avg_score":            avg_score,
    }


def generate_ai_insight(scored_posts: List[Dict], patterns: Dict) -> Tuple[str, str]:
    if not CLAUDE_API_KEY or not scored_posts:
        return _fallback_insight(patterns), _fallback_action(patterns)

    summary_lines = [
        f"- [{p.get('platform','?')}] Score:{p.get('total_score',0)} ({p.get('classification','?')}) | "
        f"Views:{p.get('views',0)} Likes:{p.get('likes',0)} Comments:{p.get('comments',0)} "
        f"Shares:{p.get('shares',0)} Leads:{p.get('whatsapp_leads',0)} | "
        f"Caption: {p.get('caption','')[:80]}"
        for p in scored_posts
    ]

    prompt = f"""You are NEXORA's performance analyst. Analyze today's content data sharply and briefly.

Posts:
{chr(10).join(summary_lines)}

Patterns: best_platform={patterns.get('best_platform')} | winning_type={patterns.get('winning_content_type')} | avg_score={patterns.get('avg_score', 0):.1f}

Respond EXACTLY in this format — two lines, nothing else:
INSIGHT: [One sentence — the single most important pattern, cite specific numbers]
ACTION: [One sentence — exactly what to change tomorrow, be specific]"""

    try:
        response = _get_client().messages.create(
            model=CLAUDE_MODEL,
            max_tokens=200,
            messages=[{"role": "user", "content": prompt}],
        )
        text    = response.content[0].text.strip()
        insight = ""
        action  = ""
        for line in text.splitlines():
            if line.startswith("INSIGHT:"):
                insight = line.removeprefix("INSIGHT:").strip()
            elif line.startswith("ACTION:"):
                action  = line.removeprefix("ACTION:").strip()
        return insight or _fallback_insight(patterns), action or _fallback_action(patterns)
    except Exception as e:
        logger.error(f"AI insight generation failed: {e}")
        return _fallback_insight(patterns), _fallback_action(patterns)


def _fallback_insight(patterns: Dict) -> str:
    sc = patterns.get("scaled_count", 0)
    if sc > 0:
        return f"{sc} post(s) hit SCALE — {patterns.get('winning_content_type','problem-style')} content drove the most engagement."
    avg = patterns.get("avg_score", 0)
    return f"Average score today: {avg:.1f}/100. No posts hit SCALE — hooks need a stronger pattern interrupt."


def _fallback_action(patterns: Dict) -> str:
    wct = patterns.get("winning_content_type", "Demo/Conversion")
    bp  = patterns.get("best_platform", "Instagram")
    return f"Lead with {wct} scripts on {bp} tomorrow. Open with a stronger scroll-stopper visual."

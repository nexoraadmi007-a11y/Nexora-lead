"""
Sales intelligence: deal moment detection, priority scoring, coaching tips.
"""
import logging
from typing import Dict, List, Optional
from database.db import get_leads, get_pipeline_summary, get_team_stats_today, get_agent_stats
from config import CLAUDE_API_KEY, CLAUDE_MODEL

logger = logging.getLogger(__name__)

# Keywords that signal buying intent in a prospect's message
BUYING_SIGNALS = [
    "interested", "how much", "price", "when can you", "let's do it",
    "send your details", "i want", "okay let's", "proceed", "confirm",
    "can we meet", "schedule", "demo", "proposal", "quote",
]

COLD_SIGNALS = [
    "not interested", "no thanks", "call me later", "not now",
    "we manage it ourselves", "already have", "no budget",
]


def detect_deal_moment(message: str) -> Optional[str]:
    """Detect if a prospect message contains a buying or cold signal."""
    lower = message.lower()
    if any(s in lower for s in BUYING_SIGNALS):
        return "HOT_SIGNAL"
    if any(s in lower for s in COLD_SIGNALS):
        return "COLD_SIGNAL"
    return None


def score_lead_priority(lead: Dict) -> float:
    """Re-score a lead dynamically based on CRM activity."""
    base = float(lead.get("score") or 0)
    stage_bonus = {
        "new": 0, "contacted": 0.5, "engaged": 1.0,
        "interested": 2.0, "closing": 3.0, "won": 0, "lost": -5,
    }
    bonus = stage_bonus.get(lead.get("stage", "new"), 0)
    return min(10, base + bonus)


def get_hot_leads(limit: int = 10) -> List[Dict]:
    """Return highest-priority leads not yet won/lost."""
    leads = get_leads(limit=100)
    active = [l for l in leads if l.get("stage") not in ("won", "lost")]
    active.sort(key=lambda l: score_lead_priority(l), reverse=True)
    return active[:limit]


def get_stuck_deals() -> List[Dict]:
    """Leads in closing/interested stage with no recent update."""
    from database.db import get_stale_leads
    stale = get_stale_leads(hours=48)
    return [l for l in stale if l.get("stage") in ("interested", "closing")]


def build_intelligence_report() -> str:
    pipeline = get_pipeline_summary()
    hot_leads = get_hot_leads(5)
    stuck = get_stuck_deals()
    team_stats = get_team_stats_today()

    lines = ["<b>NEXORA INTELLIGENCE REPORT</b>", ""]

    # Pipeline summary
    lines.append("<b>Pipeline:</b>")
    for stage, count in pipeline.items():
        if count:
            bar = "█" * min(count, 10)
            lines.append(f"  {stage.upper():<12} {bar} {count}")
    lines.append("")

    # Hot leads
    if hot_leads:
        lines.append("<b>Top Priority Leads:</b>")
        for lead in hot_leads[:5]:
            lines.append(
                f"  • {lead['name']} — {lead.get('niche','')} "
                f"(Stage: {lead['stage']}, Score: {score_lead_priority(lead):.1f})"
            )
        lines.append("")

    # Stuck deals
    if stuck:
        lines.append("<b>Stuck Deals — Need Attention:</b>")
        for lead in stuck[:3]:
            lines.append(f"  ! {lead['name']} — stuck in {lead['stage']}")
        lines.append("")

    # Team performance today
    if team_stats:
        lines.append("<b>Today's Team Stats:</b>")
        for stat in team_stats:
            name = stat.get("name") or stat.get("agent_id", "Unknown")
            lines.append(
                f"  {name}: contacted={stat['contacted']} "
                f"responses={stat['responses']} demos={stat['demos']} won={stat['won']}"
            )
    else:
        lines.append("No activity logged today yet.")

    return "\n".join(lines)


def get_micro_training(stage: str) -> str:
    """Return a quick coaching tip for the given deal stage."""
    tips = {
        "new": (
            "First contact: keep it short. Mention one specific thing about their business "
            "and ask a single yes/no question to get a reply."
        ),
        "contacted": (
            "They haven't replied yet. Send a second touch-point with a case study or "
            "a specific result you got for a similar business."
        ),
        "engaged": (
            "They're talking! Your goal now is to uncover their #1 pain. Ask: "
            "'What's the biggest challenge you face getting new customers right now?'"
        ),
        "interested": (
            "Warm prospect — move to a call or demo quickly. Waiting too long loses momentum. "
            "Offer two specific time slots: 'I'm free Tuesday 2PM or Thursday 4PM, which works?'"
        ),
        "closing": (
            "You're almost there. Identify the last objection and address it directly. "
            "Then send the proposal/contract within 24 hours — don't let it cool."
        ),
    }
    return tips.get(stage, "Keep following up consistently. Persistence wins in sales.")


def generate_daily_insight(stats: Dict, top_leads: List[Dict]) -> str:
    """Generate an AI insight or fall back to rule-based summary."""
    contacted = stats.get("contacted", 0)
    responses = stats.get("responses", 0)
    demos = stats.get("demos", 0)

    if not CLAUDE_API_KEY:
        return _rule_based_insight(contacted, responses, demos)

    try:
        import anthropic
        client = anthropic.Anthropic(api_key=CLAUDE_API_KEY)
        prompt = (
            f"You are a sales manager reviewing daily performance for NEXORA agency.\n"
            f"Stats: contacted={contacted}, responses={responses}, demos={demos}\n"
            f"Top leads today: {[l.get('niche','') for l in top_leads[:3]]}\n\n"
            f"Write 2 short sentences: one insight about what worked, one suggestion for tomorrow.\n"
            f"Be specific and actionable. No emojis."
        )
        response = client.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=120,
            messages=[{"role": "user", "content": prompt}],
        )
        return response.content[0].text.strip()
    except Exception as e:
        logger.error(f"AI insight failed: {e}")
        return _rule_based_insight(contacted, responses, demos)


def _rule_based_insight(contacted: int, responses: int, demos: int) -> str:
    rate = responses / max(contacted, 1)
    if rate >= 0.3:
        insight = "Response rate is strong today — the messaging is resonating."
    elif rate >= 0.15:
        insight = "Moderate response rate. Try more personalised openers tomorrow."
    else:
        insight = "Low response rate. Test a different hook or contact time tomorrow."

    if demos > 0:
        suggestion = f"{demos} demo(s) booked — prioritise follow-up within 24 hours."
    else:
        suggestion = "No demos booked yet — focus on moving engaged leads to a call."

    return f"{insight} {suggestion}"

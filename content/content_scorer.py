from typing import Dict, List
from config import (
    BASELINE_VIEWS, BASELINE_REACH,
    BASELINE_ENGAGEMENT_RATE, BASELINE_LEADS_PER_POST,
)


def score_post(post: Dict) -> Dict:
    views    = post.get("views", 0) or post.get("impressions", 0)
    reach    = post.get("reach", 0)
    likes    = post.get("likes", 0)
    comments = post.get("comments", 0)
    shares   = post.get("shares", 0)
    saves    = post.get("saves", 0)
    leads    = post.get("whatsapp_leads", 0)
    base_pop = max(reach, views, 1)

    # Reach Score (20 pts)
    view_ratio  = min(views / max(BASELINE_VIEWS, 1), 3.0)
    reach_ratio = min(reach / max(BASELINE_REACH, 1), 3.0)
    reach_score = min(int(((view_ratio + reach_ratio) / 2) * 20), 20)

    # Engagement Score (30 pts) — comments and shares weighted higher
    total_eng    = likes + (comments * 2) + (shares * 3) + (saves * 2)
    eng_rate     = total_eng / base_pop
    eng_ratio    = min(eng_rate / max(BASELINE_ENGAGEMENT_RATE, 0.001), 3.0)
    engagement_score = min(int(eng_ratio * 30), 30)

    # Retention Proxy (20 pts) — saves + shares as watch-completion proxy
    retention_rate  = (saves + shares) / base_pop
    retention_ratio = min(retention_rate / 0.01, 3.0)   # 1% baseline
    retention_score = min(int(retention_ratio * 20), 20)

    # Conversion Score (30 pts) — WhatsApp leads
    leads_ratio      = min(leads / max(BASELINE_LEADS_PER_POST, 1), 3.0)
    conversion_score = min(int(leads_ratio * 30), 30)

    total = reach_score + engagement_score + retention_score + conversion_score

    return {
        **post,
        "reach_score":       reach_score,
        "engagement_score":  engagement_score,
        "retention_score":   retention_score,
        "conversion_score":  conversion_score,
        "total_score":       total,
        "classification":    _classify(total),
    }


def _classify(score: int) -> str:
    if score >= 80: return "SCALE"
    if score >= 60: return "OPTIMIZE"
    if score >= 40: return "WEAK"
    return "DROP"


def score_all_posts(posts: List[Dict]) -> List[Dict]:
    return [score_post(p) for p in posts]


def get_top_post(scored_posts: List[Dict]) -> Dict:
    return max(scored_posts, key=lambda p: p.get("total_score", 0)) if scored_posts else {}


def get_low_post(scored_posts: List[Dict]) -> Dict:
    return min(scored_posts, key=lambda p: p.get("total_score", 0)) if scored_posts else {}

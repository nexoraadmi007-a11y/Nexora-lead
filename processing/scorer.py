"""
Lead scoring: max 10 points.

+2 Has phone / WhatsApp
+2 Active business (rating or reviews present)
+2 Posts content (last_post_days ≤ 30 or post_count > 0)
+2 Poor engagement (low follower:post ratio or low rating)
+2 No structured funnel (no website + no booking link in bio)
"""
from typing import Dict, List, Tuple


def score_lead(lead: Dict) -> Tuple[int, List[str]]:
    points = 0
    breakdown = []

    if lead.get("phone"):
        points += 2
        breakdown.append("+2 Has phone/WhatsApp")

    if lead.get("rating", 0) > 0 or lead.get("review_count", 0) > 0:
        points += 2
        breakdown.append("+2 Active business (has reviews/rating)")

    last_post = lead.get("last_post_days", 999)
    post_count = lead.get("post_count", 0)
    if last_post <= 30 or post_count > 5:
        points += 2
        breakdown.append("+2 Posts content regularly")

    followers = lead.get("followers", 0)
    rating    = lead.get("rating", 0)
    if (followers > 200 and post_count > 0 and (followers / max(post_count, 1)) > 50) \
       or (0 < rating < 3.5):
        points += 2
        breakdown.append("+2 Poor engagement detected")

    has_website = bool(lead.get("website", "").strip())
    bio_lower   = lead.get("bio", "").lower()
    has_booking = any(kw in bio_lower for kw in ["book", "order", "shop", "buy", "schedule"])
    if not has_website and not has_booking:
        points += 2
        breakdown.append("+2 No structured funnel (no website/booking)")

    return points, breakdown

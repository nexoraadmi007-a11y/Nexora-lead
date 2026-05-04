"""
Intent classification: HIGH / MEDIUM / LOW

Google Maps leads have no post data — intent is inferred from
rating activity, review volume, and phone availability.
Instagram leads use post recency and promo keywords.
"""
from typing import Dict


def detect_intent(lead: Dict) -> str:
    source      = lead.get("source", "")
    last_post   = lead.get("last_post_days", 999)
    post_count  = lead.get("post_count", 0)
    bio         = lead.get("bio", "").lower()
    rating      = float(lead.get("rating") or 0)
    reviews     = int(lead.get("review_count") or 0)
    phone       = lead.get("phone", "").strip()

    promo_keywords = ["sale", "promo", "discount", "off", "deal", "offer", "order now", "available"]
    has_promo = any(kw in bio for kw in promo_keywords)

    # ── Instagram leads: use post activity ────────────────────────────────────
    if "instagram" in source:
        if last_post <= 7 or has_promo:
            return "HIGH"
        if last_post <= 30 or post_count >= 10:
            return "MEDIUM"
        return "LOW"

    # ── Google Maps leads: infer from rating + reviews + phone ────────────────
    # HIGH: active business with reviews and phone (ready to be contacted)
    if phone and reviews >= 5 and rating >= 3.0:
        return "HIGH"

    # MEDIUM: has some presence (rating or reviews) but less active
    if (rating > 0 or reviews > 0) and phone:
        return "MEDIUM"

    # MEDIUM: no phone but has reviews (worth researching)
    if reviews >= 10:
        return "MEDIUM"

    # LOW: no reviews, no rating, no phone
    return "LOW"

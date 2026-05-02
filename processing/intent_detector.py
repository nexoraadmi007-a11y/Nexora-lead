"""
Intent classification: HIGH / MEDIUM / LOW
"""
from typing import Dict


def detect_intent(lead: Dict) -> str:
    last_post = lead.get("last_post_days", 999)
    post_count = lead.get("post_count", 0)
    bio = lead.get("bio", "").lower()

    promo_keywords = ["sale", "promo", "discount", "off", "deal", "offer", "order now", "available"]
    has_promo = any(kw in bio for kw in promo_keywords)

    if last_post <= 7 or has_promo:
        return "HIGH"

    if last_post <= 30 or post_count >= 10:
        return "MEDIUM"

    return "LOW"

"""
Identifies the specific revenue gap / opportunity for each lead.
"""
from typing import Dict


def detect_opportunity(lead: Dict) -> str:
    gaps = []
    bio     = lead.get("bio", "").lower()
    website = lead.get("website", "").strip()
    phone   = lead.get("phone", "").strip()

    if not phone:
        gaps.append("No phone/WhatsApp — customers can't reach them quickly")

    if not website:
        gaps.append("No website — zero online credibility")

    if website and "wa.me" not in website and "whatsapp" not in bio:
        gaps.append("No WhatsApp link — losing impulse buyers")

    cta_words = ["order", "book", "call", "whatsapp", "click", "buy", "shop", "dm"]
    if not any(w in bio for w in cta_words):
        gaps.append("No call-to-action — visitors leave without converting")

    contact_words = ["phone", "call", "whatsapp", "dm", "message", "contact", "reach"]
    if not any(w in bio for w in contact_words):
        gaps.append("Unclear contact method — customers abandon before reaching out")

    if lead.get("post_count", 0) < 5:
        gaps.append("Very few posts — business barely visible online")

    followers = lead.get("followers", 0)
    engagement = lead.get("review_count", 0)
    if followers > 500 and engagement < 5:
        gaps.append("High followers, low engagement — content not converting to sales")

    if not gaps:
        gaps.append("Weak overall digital presence limiting customer reach")

    return gaps[0]  # Return the most impactful gap

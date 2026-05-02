"""
Normalises raw scraped leads into a consistent Lead dict.
"""
import re
import hashlib
from typing import Dict


def normalize(raw: Dict) -> Dict:
    """
    Produce a clean, consistently-keyed lead dict from any scraper output.
    Adds a `lead_id` fingerprint for deduplication.
    """
    name    = _clean(raw.get("name", ""))
    phone   = _clean_phone(raw.get("phone", ""))
    address = _clean(raw.get("address", ""))
    city    = _clean(raw.get("city", ""))
    website = _clean(raw.get("website", ""))

    lead = {
        "name":           name,
        "phone":          phone,
        "address":        address,
        "city":           city,
        "website":        website,
        "username":       raw.get("username", ""),
        "bio":            raw.get("bio", ""),
        "followers":      int(raw.get("followers") or 0),
        "post_count":     int(raw.get("post_count") or 0),
        "last_post_days": int(raw.get("last_post_days") or 999),
        "rating":         float(raw.get("rating") or 0),
        "review_count":   int(raw.get("review_count") or 0),
        "category":       _clean(raw.get("category", "")),
        "source":         raw.get("source", "unknown"),
        # filled later
        "score":          0,
        "score_breakdown": [],
        "intent":         "",
        "niche":          "",
        "opportunity":    "",
        "hook":           "",
        "strategy":       "",
        "lead_id":        "",
    }

    lead["lead_id"] = _fingerprint(phone, name, city)
    return lead


def _clean(val: str) -> str:
    return " ".join(str(val).strip().split())


def _clean_phone(val: str) -> str:
    digits = re.sub(r"[^\d+]", "", str(val))
    return digits if len(digits) >= 7 else ""


def _fingerprint(phone: str, name: str, city: str) -> str:
    key = (phone or f"{name}|{city}").lower().strip()
    return hashlib.md5(key.encode()).hexdigest()[:12]

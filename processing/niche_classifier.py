"""
Classifies a lead into a NEXORA sales niche.
"""
from typing import Dict

NICHE_KEYWORDS = {
    "Restaurant":         ["restaurant", "food", "eatery", "kitchen", "cafe", "grill", "suya", "buka", "canteen"],
    "Building Materials": ["building", "materials", "iron", "cement", "tiles", "roofing", "hardware", "plumbing"],
    "Salon":              ["salon", "hair", "barber", "beauty", "spa", "nails", "lashes", "makeup", "skincare"],
    "Fashion":            ["fashion", "boutique", "clothing", "clothes", "outfit", "shoes", "wears", "styles"],
    "Pharmacy":           ["pharmacy", "drug", "chemist", "medicine", "health", "medical", "hospital", "clinic"],
    "School":             ["school", "academy", "college", "nursery", "primary", "secondary", "tutorial", "lessons"],
}


def classify_niche(lead: Dict) -> str:
    text = " ".join([
        lead.get("name", ""),
        lead.get("category", ""),
        lead.get("bio", ""),
        lead.get("address", ""),
    ]).lower()

    for niche, keywords in NICHE_KEYWORDS.items():
        if any(kw in text for kw in keywords):
            return niche

    return "Others"

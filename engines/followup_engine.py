"""
Follow-up intelligence engine.
Detects leads that need follow-up based on time since last contact.
"""
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Tuple

from database.db import get_stale_leads, get_leads

logger = logging.getLogger(__name__)

# (hours_since_contact, label, urgency)
FOLLOWUP_RULES: List[Tuple[int, str, str]] = [
    (24,  "24h follow-up",      "normal"),
    (48,  "48h follow-up",      "warm"),
    (72,  "72h — needs action", "hot"),
    (120, "5-day — at risk",    "critical"),
    (168, "7-day — stale",      "critical"),
]


def get_followups_due() -> List[Dict]:
    """
    Returns leads grouped by urgency that need follow-up now.
    Each item includes a 'followup_label' and 'urgency' field.
    """
    due = []
    for hours, label, urgency in FOLLOWUP_RULES:
        stale = get_stale_leads(hours=hours)
        for lead in stale:
            if not any(d["id"] == lead["id"] for d in due):
                lead["followup_label"] = label
                lead["followup_hours"] = hours
                lead["urgency"] = urgency
                due.append(lead)

    # Sort: critical first, then by score descending
    priority = {"critical": 0, "hot": 1, "warm": 2, "normal": 3}
    due.sort(key=lambda x: (priority.get(x["urgency"], 9), -float(x.get("score") or 0)))
    return due


def build_followup_alert(leads: List[Dict]) -> str:
    if not leads:
        return ""

    lines = ["<b>FOLLOW-UP ALERTS</b>", ""]
    critical = [l for l in leads if l["urgency"] == "critical"]
    hot      = [l for l in leads if l["urgency"] == "hot"]
    normal   = [l for l in leads if l["urgency"] in ("warm", "normal")]

    def _fmt(lead: Dict) -> str:
        phone = lead.get("phone") or "no phone"
        return (
            f"  • <b>{lead['name']}</b> ({lead.get('niche','')}) — {phone}\n"
            f"    Stage: {lead['stage']}  |  {lead['followup_label']}"
        )

    if critical:
        lines.append("CRITICAL — Act today:")
        lines += [_fmt(l) for l in critical[:5]]
        lines.append("")

    if hot:
        lines.append("Needs action soon:")
        lines += [_fmt(l) for l in hot[:5]]
        lines.append("")

    if normal:
        lines.append("Regular follow-up:")
        lines += [_fmt(l) for l in normal[:5]]

    return "\n".join(lines)


def get_agent_followups(agent_id: str) -> List[Dict]:
    """Return follow-up due leads assigned to a specific agent."""
    due = get_followups_due()
    return [l for l in due if l.get("agent_id") == str(agent_id)]

"""
Generates a custom, conversion-focused opening hook for each lead using Claude.
Falls back to a rule-based hook if the API is unavailable.
"""
import logging
import anthropic
from config import CLAUDE_API_KEY, CLAUDE_MODEL, NICHE_STRATEGY

logger = logging.getLogger(__name__)

_client = None


def _get_client():
    global _client
    if _client is None and CLAUDE_API_KEY:
        _client = anthropic.Anthropic(api_key=CLAUDE_API_KEY)
    return _client


def generate_hook(lead: dict) -> str:
    client = _get_client()
    if not client:
        return _fallback_hook(lead)

    prompt = f"""You are a sales intelligence engine for NEXORA, a digital marketing firm.

Generate ONE short, natural opening line for a sales outreach to this business.

Business details:
- Name: {lead.get('name', 'Unknown')}
- Niche: {lead.get('niche', 'Others')}
- City: {lead.get('city', '')}
- Opportunity: {lead.get('opportunity', '')}
- Bio/Category: {lead.get('bio') or lead.get('category', '')}

Rules:
- Must feel observational, not salesy
- Must hint at a lost revenue opportunity
- Must be 1-2 sentences, conversational tone
- Do NOT mention "NEXORA" or any company name
- Do NOT use generic lines like "I can help your business grow"

Output ONLY the hook line. Nothing else."""

    try:
        message = client.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=120,
            messages=[{"role": "user", "content": prompt}],
        )
        return message.content[0].text.strip().strip('"')
    except Exception as e:
        logger.warning(f"Claude hook generation failed: {e} — using fallback")
        return _fallback_hook(lead)


def _fallback_hook(lead: dict) -> str:
    opp = lead.get("opportunity", "")
    niche = lead.get("niche", "Others")
    name = lead.get("name", "your business")

    if "WhatsApp" in opp:
        return f"I noticed potential customers visiting {name} might not have a quick way to place orders — that usually means lost sales every day."
    if "call-to-action" in opp:
        return f"I came across {name} and noticed there's no clear next step for interested customers — that gap often silently reduces how many actually buy."
    if "website" in opp:
        return f"A business like {name} without a digital footprint is essentially invisible to customers searching online right now."
    if niche == "Restaurant":
        return f"Customers often decide where to eat before leaving home — if {name} isn't easy to find and order from digitally, those decisions are going elsewhere."
    if niche == "Salon":
        return f"Most salons lose bookings not because they're bad, but because the process of booking is unclear — I think {name} might be experiencing this."
    return f"I came across {name} and noticed something that might be quietly costing you customers every week."

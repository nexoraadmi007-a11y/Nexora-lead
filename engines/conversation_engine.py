"""
AI-powered conversation coaching using Claude.
Generates reply suggestions and objection handlers for sales agents.
"""
import logging
from typing import Dict, List, Optional

from config import CLAUDE_API_KEY, CLAUDE_MODEL

logger = logging.getLogger(__name__)


def _client():
    import anthropic
    return anthropic.Anthropic(api_key=CLAUDE_API_KEY)


def suggest_reply(lead: Dict, last_message: str, conversation_history: List[Dict] = None) -> str:
    """
    Given a lead profile and the last message received, return a suggested reply.
    """
    if not CLAUDE_API_KEY:
        return _fallback_reply(lead, last_message)

    history_text = ""
    if conversation_history:
        lines = []
        for msg in conversation_history[-6:]:
            direction = "Agent" if msg["direction"] == "out" else "Prospect"
            lines.append(f"{direction}: {msg['message']}")
        history_text = "\n".join(lines)

    prompt = f"""You are a sales coach for NEXORA, a digital marketing agency in Abeokuta, Nigeria.
A sales agent is talking to a potential client. Write a short, natural reply the agent should send.

LEAD PROFILE:
- Business: {lead.get('name', '')}
- Type: {lead.get('niche', '')}
- Opportunity: {lead.get('opportunity', '')}
- Stage: {lead.get('stage', '')}

{"CONVERSATION HISTORY:" + chr(10) + history_text if history_text else ""}

PROSPECT'S LAST MESSAGE:
"{last_message}"

Write ONE short reply (2-4 sentences max). Be friendly, professional, and move toward booking a call or demo.
Use Nigerian business context. Do NOT use emojis. Output ONLY the reply text."""

    try:
        client = _client()
        response = client.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=200,
            messages=[{"role": "user", "content": prompt}],
        )
        return response.content[0].text.strip()
    except Exception as e:
        logger.error(f"Claude reply suggestion failed: {e}")
        return _fallback_reply(lead, last_message)


def handle_objection(lead: Dict, objection: str) -> str:
    """Return a suggested response to a common objection."""
    if not CLAUDE_API_KEY:
        return "I understand your concern. Let me share how we've helped similar businesses in Abeokuta get real results. Can we schedule a quick 10-minute call?"

    prompt = f"""You are a sales coach for NEXORA digital marketing agency in Abeokuta.
A prospect raised this objection: "{objection}"

Business context:
- Business: {lead.get('name', '')}
- Type: {lead.get('niche', '')}
- What we offer: website, social media management, online ads, WhatsApp marketing

Write a SHORT objection-handling response (3 sentences max). Be empathetic, then pivot to value.
Do NOT use emojis. Output ONLY the response text."""

    try:
        client = _client()
        response = client.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=150,
            messages=[{"role": "user", "content": prompt}],
        )
        return response.content[0].text.strip()
    except Exception as e:
        logger.error(f"Claude objection handler failed: {e}")
        return "I understand. Many businesses felt the same way before seeing the results. Can I show you a quick example from a similar business in Abeokuta?"


def generate_opening_message(lead: Dict) -> str:
    """Generate a personalised first outreach message for a lead."""
    if not CLAUDE_API_KEY:
        return (
            f"Hello, I'm reaching out from NEXORA. I came across {lead.get('name', 'your business')} "
            f"and noticed a great opportunity to help you grow your online presence. "
            f"Would you be open to a quick conversation?"
        )

    prompt = f"""Write a WhatsApp first-contact message for a sales agent from NEXORA digital agency.

TARGET BUSINESS:
- Name: {lead.get('name', '')}
- Type: {lead.get('niche', '')}
- Location: {lead.get('address') or lead.get('city', 'Abeokuta')}
- Gap identified: {lead.get('opportunity', '')}

Rules:
- 3 sentences max
- Mention something specific about their business
- End with a soft question (not a hard sell)
- Nigerian professional tone
- No emojis
Output ONLY the message text."""

    try:
        client = _client()
        response = client.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=150,
            messages=[{"role": "user", "content": prompt}],
        )
        return response.content[0].text.strip()
    except Exception as e:
        logger.error(f"Claude opening message failed: {e}")
        return (
            f"Hello, I'm from NEXORA digital marketing. I came across {lead.get('name', 'your business')} "
            f"and I believe we can help you attract more customers online. "
            f"Would you be open to a 10-minute conversation?"
        )


def _fallback_reply(lead: Dict, last_message: str) -> str:
    lower = last_message.lower()
    if any(w in lower for w in ["price", "cost", "how much", "rate"]):
        return (
            "Our packages start from an affordable rate tailored to your business size. "
            "I'd love to give you an exact quote after a quick 10-minute call — when are you free?"
        )
    if any(w in lower for w in ["not interested", "no thanks", "busy"]):
        return (
            "No problem at all. I'll check back in a few weeks. "
            "If you ever want to see what we've done for other businesses in Abeokuta, just let me know."
        )
    return (
        "Thank you for getting back to me. I'd love to show you exactly how we can help "
        f"{lead.get('name', 'your business')} grow online. "
        "Can we set up a quick 10-minute call this week?"
    )

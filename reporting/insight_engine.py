"""
AI-powered insight and suggestion generator for the night report.
Tracks niche performance and hook patterns over time.
"""
import json
import logging
import os
from pathlib import Path
from typing import Dict
import anthropic
from config import CLAUDE_API_KEY, CLAUDE_MODEL

logger = logging.getLogger(__name__)

LEARNING_FILE = Path("data/learning_log.json")


def load_learning_log() -> list:
    if LEARNING_FILE.exists():
        try:
            return json.loads(LEARNING_FILE.read_text())
        except Exception:
            return []
    return []


def save_learning_entry(entry: Dict):
    LEARNING_FILE.parent.mkdir(exist_ok=True)
    log = load_learning_log()
    log.append(entry)
    # Keep only last 30 days
    if len(log) > 30:
        log = log[-30:]
    LEARNING_FILE.write_text(json.dumps(log, indent=2))


def generate_insight_and_suggestion(stats: Dict, top_leads: list) -> tuple[str, str]:
    """Returns (insight, suggestion) using Claude or rule-based fallback."""
    save_learning_entry({"stats": stats, "top_niches": [l.get("niche") for l in top_leads]})

    if not CLAUDE_API_KEY:
        return _rule_based_insight(stats), _rule_based_suggestion(stats)

    log = load_learning_log()
    prompt = f"""You are a sales performance analyst for NEXORA, a digital marketing firm targeting local businesses.

Today's stats:
- Leads sent: {stats.get('top_n', 0)}
- Contacted: {stats.get('contacted', 0)}
- Responses: {stats.get('responses', 0)}
- Demos booked: {stats.get('demos', 0)}
- Top niches today: {[l.get('niche') for l in top_leads]}

Historical pattern (last {len(log)} days):
{json.dumps(log[-5:], indent=2) if log else 'No history yet'}

Generate:
1. ONE insight: What worked today or what pattern is emerging (1-2 sentences)
2. ONE suggestion: One concrete action to improve tomorrow (1-2 sentences)

Output EXACTLY this format:
INSIGHT: [your insight]
SUGGESTION: [your suggestion]"""

    try:
        client = anthropic.Anthropic(api_key=CLAUDE_API_KEY)
        msg = client.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=200,
            messages=[{"role": "user", "content": prompt}],
        )
        text = msg.content[0].text.strip()
        insight    = _extract_line(text, "INSIGHT:")
        suggestion = _extract_line(text, "SUGGESTION:")
        return insight, suggestion
    except Exception as e:
        logger.warning(f"Insight generation failed: {e}")
        return _rule_based_insight(stats), _rule_based_suggestion(stats)


def _extract_line(text: str, prefix: str) -> str:
    for line in text.splitlines():
        if line.startswith(prefix):
            return line[len(prefix):].strip()
    return ""


def _rule_based_insight(stats: Dict) -> str:
    if stats.get("responses", 0) > 0:
        return f"Outreach generated {stats['responses']} response(s) today — the hook and targeting are working."
    if stats.get("contacted", 0) > 0:
        return "Leads were contacted but no responses yet — follow up tomorrow or adjust the opening line."
    return "No outreach recorded today — lead quality pipeline is ready, human execution is the bottleneck."


def _rule_based_suggestion(stats: Dict) -> str:
    if stats.get("contacted", 0) == 0:
        return "Prioritise calling the top 2 leads first thing tomorrow morning — WhatsApp cold messages have lower open rates."
    if stats.get("responses", 0) == 0:
        return "Try a different hook on remaining leads — lead with the specific opportunity identified rather than a general question."
    return "Follow up with responsive leads to convert them into booked demos before they go cold."

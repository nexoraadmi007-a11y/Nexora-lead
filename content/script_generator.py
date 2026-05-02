import logging
from datetime import date
from typing import Dict, Optional
import anthropic
from config import CLAUDE_API_KEY, CLAUDE_MODEL

logger = logging.getLogger(__name__)

_client = None

SYSTEM_PROMPT = """You are NEXORA CONTENT ENGINE v3 — a viral content strategist for Nigerian business owners on Instagram, TikTok, and Facebook.

You generate two daily video scripts that drive attention, engagement, and WhatsApp leads.

TARGET AUDIENCE: Nigerian small/medium business owners — restaurants, salons, fashion, pharmacies, schools, building materials dealers.

BUSINESS CONTEXT: NEXORA helps these businesses get more customers through digital systems — WhatsApp funnels, online presence, content strategy. CTA is always: Send 'SYSTEM' on WhatsApp.

Each script MUST follow this EXACT structure:
- Title
- Content Type

🎥 Opening Visual

🎬 Full Script (line-by-line)
  Include [PAUSE] and [EMPHASIS: WORD] markers throughout

🎯 Subtitle Keywords

🎥 Visual Direction

⚡ Pacing Notes

🔁 Loop Ending

💬 Comment Trigger

📢 Caption

📣 CTA

🧠 Content Intent

HARD RULES:
- No generic content. No fluff. No repetition of weak ideas.
- Short punchy lines. Fast pacing. Every line must earn its place.
- Specific callouts to Nigerian business owners — name the pain.
- Loop ending: last frame visually connects back to the opening frame.
- CTA always ends with: Send 'SYSTEM' on WhatsApp"""


def _get_client():
    global _client
    if _client is None:
        _client = anthropic.Anthropic(api_key=CLAUDE_API_KEY)
    return _client


def generate_daily_scripts(learning_context: Optional[Dict] = None) -> str:
    today = date.today().strftime("%A, %d %B %Y")

    adapt_section = ""
    if learning_context:
        winning_hook = learning_context.get("winning_hook") or learning_context.get("Winning Hook", "")
        winning_type = learning_context.get("winning_content_type") or learning_context.get("Winning Content Type", "")
        weak_format  = learning_context.get("weak_format") or learning_context.get("Weak Format", "")
        best_platform = learning_context.get("best_platform") or learning_context.get("Best Platform", "")
        if winning_hook:
            adapt_section += f"\n→ Use this winning hook STYLE (not verbatim): {winning_hook}"
        if winning_type:
            adapt_section += f"\n→ Prioritize this content type: {winning_type}"
        if weak_format:
            adapt_section += f"\n→ Avoid this weak format: {weak_format}"
        if best_platform:
            adapt_section += f"\n→ Optimise pacing for: {best_platform}"

    user_prompt = f"""Generate TODAY'S NEXORA DAILY CONTENT PACK for {today}.
{adapt_section}

Generate TWO complete video scripts:

VIDEO 1: Problem / Insight
→ Open the owner's eyes to a hidden problem costing them money or customers
→ Build tension. End on a curiosity hook that forces them to WhatsApp you.

VIDEO 2: Demo / Conversion
→ Show a real transformation or result a Nigerian business achieved
→ Make it tangible. Hard CTA to WhatsApp at the end.

Format output EXACTLY as:
NEXORA DAILY CONTENT PACK – {today}

Then Video 1 in full, then Video 2 in full — each with every section of the script format."""

    try:
        client = _get_client()
        response = client.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=3500,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_prompt}],
        )
        return response.content[0].text
    except Exception as e:
        logger.error(f"Script generation failed: {e}")
        return _fallback_scripts(today)


def _fallback_scripts(today: str) -> str:
    return f"""NEXORA DAILY CONTENT PACK – {today}

⚠️ AI generation unavailable. Using fallback scripts.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
VIDEO 1 — Problem / Insight
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Title: Your customers are forgetting you exist

Content Type: Problem / Insight

🎥 Opening Visual:
Phone screen — no notifications, empty WhatsApp. Cut to: competitor's screen flooded with messages.

🎬 Full Script:
You opened your business this morning.
[PAUSE]
Cleaned up. Unlocked the door.
[PAUSE]
And waited.
[PAUSE]
But your competitor next door?
[EMPHASIS: ALREADY FULLY BOOKED]
[PAUSE]
The difference isn't luck.
[PAUSE]
It's not location.
[PAUSE]
It's not even price.
[PAUSE]
It's a SYSTEM.
[PAUSE]
And right now — you don't have one.
[PAUSE]
Want to see what that system looks like?
[EMPHASIS: SEND 'SYSTEM' ON WHATSAPP]

🎯 Subtitle Keywords:
FULLY BOOKED | SYSTEM | CUSTOMERS | COMPETITOR

🎥 Visual Direction:
Split screen: empty storefront vs. busy one. Then: phone showing zero messages vs. phone with 40+ notifications.

⚡ Pacing Notes:
Slow build for first 6 lines. Speed up from "The difference isn't luck." Hard stop on SYSTEM. Dramatic pause before CTA.

🔁 Loop Ending:
End on same shot as opening — empty phone screen — then flash "SYSTEM" text before loop.

💬 Comment Trigger:
Drop "OPEN" in the comments if this is your business right now.

📢 Caption:
Your competitor isn't smarter than you. They just have a system you don't know about yet.
Send 'SYSTEM' on WhatsApp. Link in bio.

📣 CTA:
Send 'SYSTEM' on WhatsApp right now. Link in bio.

🧠 Content Intent:
Create pain awareness. Make the viewer self-identify as the business without a system. Drive to WhatsApp via curiosity.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
VIDEO 2 — Demo / Conversion
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Title: We set this up in 24 hours. The result was insane.

Content Type: Demo / Conversion

🎥 Opening Visual:
Before: empty DM inbox. Timer counting 24 hours. After: 47 new customer messages.

🎬 Full Script:
This restaurant had 12 followers.
[PAUSE]
No website. No WhatsApp link.
[PAUSE]
Customers couldn't even find their number.
[PAUSE]
We set up one system.
[EMPHASIS: 24 HOURS LATER]
[PAUSE]
47 new customer messages.
[PAUSE]
3 catering inquiries.
[PAUSE]
Weekend fully booked.
[PAUSE]
Same food. Same location. Same price.
[PAUSE]
Just a SYSTEM.
[EMPHASIS: WANT THIS FOR YOUR BUSINESS?]
[PAUSE]
Send 'SYSTEM' on WhatsApp.

🎯 Subtitle Keywords:
24 HOURS | 47 MESSAGES | SYSTEM | FULLY BOOKED

🎥 Visual Direction:
Show the before (empty, manual, chaotic) then the after (notifications flooding in, bookings confirmed). Real-feeling. Not overly polished.

⚡ Pacing Notes:
Fast from the start. Short lines. Every number is a hard stop with emphasis. End CTA is calm and confident — not pushy.

🔁 Loop Ending:
End on notification screen → fade back to empty inbox from the opening → "SYSTEM" text appears.

💬 Comment Trigger:
What's your business? Drop it below — I'll tell you what system would work for you.

📢 Caption:
47 messages in 24 hours. Same restaurant. Same food. Just a different system.
Send 'SYSTEM' on WhatsApp. Link in bio.

📣 CTA:
Send 'SYSTEM' on WhatsApp. Link in bio.

🧠 Content Intent:
Proof-based conversion. Specific numbers build credibility. Relatable business type (restaurant). Drive to WhatsApp with momentum from results."""

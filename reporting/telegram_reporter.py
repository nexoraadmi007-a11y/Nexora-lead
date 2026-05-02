"""
All Telegram delivery: daily brief (9 AM), check-in (4 PM), night report (9 PM).
"""
import logging
from datetime import date
from typing import List, Dict
import telegram
from config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, OWNER_CHAT_ID

logger = logging.getLogger(__name__)

_bot = None


def _get_bot():
    global _bot
    if _bot is None:
        _bot = telegram.Bot(token=TELEGRAM_BOT_TOKEN)
    return _bot


async def send_message(chat_id: str, text: str):
    bot = _get_bot()
    # Telegram message limit is 4096 chars
    for chunk in _split(text, 4000):
        await bot.send_message(chat_id=chat_id, text=chunk, parse_mode="HTML")


def _split(text: str, size: int) -> List[str]:
    chunks = []
    while len(text) > size:
        cut = text.rfind("\n", 0, size)
        if cut == -1:
            cut = size
        chunks.append(text[:cut])
        text = text[cut:].lstrip("\n")
    if text:
        chunks.append(text)
    return chunks


# ── 9 AM — Daily Brief ────────────────────────────────────────────────────────

def build_daily_brief(top_leads: List[Dict], all_leads: List[Dict]) -> str:
    today = date.today().strftime("%d %b %Y")
    lines = [
        f"🚀 <b>NEXORA DAILY SALES BRIEF</b>",
        f"📅 {today}",
        f"",
        f"📊 Total Qualified Leads Today: <b>{len(all_leads)}</b>",
        f"🔥 Top {len(top_leads)} Priority Leads Selected",
        f"",
        "━" * 30,
    ]

    for i, lead in enumerate(top_leads, 1):
        phone_line = f"📞 {lead['phone']}" if lead.get("phone") else "📞 Not listed"
        web_line   = f"🌐 {lead['website']}" if lead.get("website") else ""
        lines += [
            f"",
            f"<b>#{i}. {lead['name']}</b>",
            f"📍 {lead.get('address') or lead.get('city') or 'Unknown location'}",
            f"🏷️ Niche: {lead['niche']}  |  Score: {lead['score']}/10  |  Intent: {lead['intent']}",
            phone_line,
        ]
        if web_line:
            lines.append(web_line)
        lines += [
            f"",
            f"💰 <b>Opportunity:</b> {lead['opportunity']}",
            f"🎯 <b>Strategy:</b> {lead.get('strategy', '')}",
            f"",
            f"💬 <b>Opening Hook:</b>",
            f"<i>\"{lead['hook']}\"</i>",
            f"",
            f"📲 <b>Approach:</b> WhatsApp / Call — Do NOT auto-message",
            "━" * 30,
        ]

    lines += [
        "",
        "⚠️ <b>Human execution required.</b>",
        "Call or WhatsApp each lead. Do not send automated messages.",
        "",
        "📁 Full lead list → Google Sheets",
    ]
    return "\n".join(lines)


# ── 4 PM — Check-In ───────────────────────────────────────────────────────────

def build_checkin_message() -> str:
    return (
        "📊 <b>NEXORA 4 PM CHECK-IN</b>\n\n"
        "Quick update needed from your team:\n\n"
        "1️⃣ How many leads were contacted today?\n"
        "2️⃣ How many responded?\n"
        "3️⃣ Any demos or calls booked?\n"
        "4️⃣ Any challenges or objections?\n\n"
        "Reply in format:\n"
        "<code>contacted=X responses=X demos=X</code>"
    )


# ── 9 PM — Night Report ───────────────────────────────────────────────────────

def build_night_report(stats: Dict, insight: str = "", suggestion: str = "") -> str:
    contacted   = stats.get("contacted", 0)
    responses   = stats.get("responses", 0)
    demos       = stats.get("demos", 0)
    leads_sent  = stats.get("top_n", 0)
    conv_rate   = f"{(demos / max(contacted, 1) * 100):.1f}%" if contacted else "—"

    lines = [
        "📊 <b>NEXORA DAILY PERFORMANCE REPORT</b>",
        f"📅 {date.today().strftime('%d %b %Y')}",
        "",
        "━" * 30,
        f"📤 Leads Sent:        <b>{leads_sent}</b>",
        f"📞 Contacted:         <b>{contacted}</b>",
        f"💬 Responses:         <b>{responses}</b>",
        f"📅 Demos Booked:      <b>{demos}</b>",
        f"📈 Conversion Rate:   <b>{conv_rate}</b>",
        "━" * 30,
    ]

    if insight:
        lines += ["", f"✅ <b>What worked today:</b>", insight]
    if suggestion:
        lines += ["", f"🔧 <b>What to improve tomorrow:</b>", suggestion]

    lines += ["", "🔁 Next cycle: Tomorrow 9:00 AM"]
    return "\n".join(lines)


# ── Learning Insight (AI) ─────────────────────────────────────────────────────

async def send_daily_brief(top_leads: List[Dict], all_leads: List[Dict]):
    text = build_daily_brief(top_leads, all_leads)
    await send_message(TELEGRAM_CHAT_ID, text)
    logger.info("Daily brief sent to Telegram")


async def send_checkin():
    text = build_checkin_message()
    await send_message(TELEGRAM_CHAT_ID, text)
    logger.info("Check-in message sent")


async def send_night_report(stats: Dict, insight: str = "", suggestion: str = ""):
    text = build_night_report(stats, insight, suggestion)
    await send_message(OWNER_CHAT_ID, text)
    logger.info("Night report sent to owner")

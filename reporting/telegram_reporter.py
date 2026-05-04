"""
All Telegram delivery: daily brief (9 AM), check-in (4 PM), night report (9 PM).
Leads are delivered as Excel documents, NOT text dumps.
"""
import logging
from datetime import date
from pathlib import Path
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
    for chunk in _split(text, 4000):
        await bot.send_message(chat_id=chat_id, text=chunk, parse_mode="HTML")


async def send_document(chat_id: str, file_path: Path, caption: str):
    """Send a file as a Telegram document with retry logic."""
    bot = _get_bot()
    for attempt in range(3):
        try:
            with open(file_path, "rb") as f:
                await bot.send_document(
                    chat_id=chat_id,
                    document=f,
                    filename=file_path.name,
                    caption=caption,
                    parse_mode="HTML",
                )
            logger.info(f"Document sent: {file_path.name}")
            return
        except Exception as e:
            logger.warning(f"Document send attempt {attempt + 1} failed: {e}")
            if attempt == 2:
                await send_message(chat_id, "⚠️ File delivery failed — check logs")


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

def build_top5_summary(top_leads: List[Dict], all_leads: List[Dict]) -> str:
    today    = date.today().strftime("%d %b %Y")
    hot_cnt  = sum(1 for l in all_leads if l.get("intent") == "HIGH")
    warm_cnt = sum(1 for l in all_leads if l.get("intent") == "MEDIUM")
    city     = top_leads[0].get("city", "") if top_leads else ""

    lines = [
        f"<b>NEXORA DAILY SALES BRIEF</b>",
        f"Date: {today}  |  City: {city}",
        f"",
        f"Total Qualified: <b>{len(all_leads)}</b>  |  HOT: <b>{hot_cnt}</b>  |  WARM: <b>{warm_cnt}</b>",
        f"",
        f"<b>TOP {len(top_leads)} PRIORITY LEADS:</b>",
        "─" * 28,
    ]

    for i, lead in enumerate(top_leads, 1):
        phone = lead.get("phone") or "No phone listed"
        lines += [
            f"",
            f"<b>#{i}. {lead['name']}</b>",
            f"  {lead.get('address') or lead.get('city', '')}",
            f"  {lead['niche']}  |  Score: {lead['score']}/10  |  {lead['intent']}",
            f"  Tel: {phone}",
            f"  Gap: {lead['opportunity']}",
            f"  Hook: <i>{lead['hook'][:120]}...</i>" if len(lead.get('hook','')) > 120 else f"  Hook: <i>{lead.get('hook','')}</i>",
        ]

    lines += [
        "",
        "─" * 28,
        "Full list attached as Excel file.",
        "Call or WhatsApp each lead. Do NOT auto-message.",
    ]
    return "\n".join(lines)


async def send_daily_brief(top_leads: List[Dict], all_leads: List[Dict]):
    from reporting.excel_generator import generate_excel

    today    = date.today().strftime("%Y-%m-%d")
    filename = f"nexora_leads_{today}.xlsx"

    # Generate Excel with ALL leads
    xlsx_path = generate_excel(all_leads, filename=filename)

    caption = (
        f"<b>Nexora Daily Leads</b>\n"
        f"Total: <b>{len(all_leads)}</b> leads\n"
        f"Date: {date.today().strftime('%d %b %Y')}"
    )

    # Send Top 5 summary text first
    if top_leads:
        await send_message(TELEGRAM_CHAT_ID, build_top5_summary(top_leads, all_leads))

    # Send Excel file as document
    await send_document(TELEGRAM_CHAT_ID, xlsx_path, caption)
    logger.info(f"Daily brief + Excel sent ({len(all_leads)} leads)")


# ── 4 PM — Check-In ───────────────────────────────────────────────────────────

def build_checkin_message() -> str:
    return (
        "NEXORA 4 PM CHECK-IN\n\n"
        "Quick update needed:\n\n"
        "1. How many leads were contacted today?\n"
        "2. How many responded?\n"
        "3. Any demos or calls booked?\n"
        "4. Any challenges?\n\n"
        "Reply: contacted=X responses=X demos=X"
    )


# ── 9 PM — Night Report ───────────────────────────────────────────────────────

def build_night_report(stats: Dict, insight: str = "", suggestion: str = "") -> str:
    contacted  = stats.get("contacted", 0)
    responses  = stats.get("responses", 0)
    demos      = stats.get("demos", 0)
    leads_sent = stats.get("top_n", 0)
    conv_rate  = f"{(demos / max(contacted, 1) * 100):.1f}%" if contacted else "n/a"

    lines = [
        "<b>NEXORA DAILY PERFORMANCE REPORT</b>",
        f"Date: {date.today().strftime('%d %b %Y')}",
        "",
        f"Leads Sent:      <b>{leads_sent}</b>",
        f"Contacted:       <b>{contacted}</b>",
        f"Responses:       <b>{responses}</b>",
        f"Demos Booked:    <b>{demos}</b>",
        f"Conversion Rate: <b>{conv_rate}</b>",
    ]
    if insight:
        lines += ["", f"What worked: {insight}"]
    if suggestion:
        lines += ["", f"Improve tomorrow: {suggestion}"]
    lines += ["", "Next cycle: Tomorrow 9:00 AM WAT"]
    return "\n".join(lines)


async def send_checkin():
    await send_message(TELEGRAM_CHAT_ID, build_checkin_message())
    logger.info("Check-in message sent")


async def send_night_report(stats: Dict, insight: str = "", suggestion: str = ""):
    await send_message(OWNER_CHAT_ID, build_night_report(stats, insight, suggestion))
    logger.info("Night report sent")

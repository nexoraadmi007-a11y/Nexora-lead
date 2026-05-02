"""
NEXORA CONTENT ENGINE v3
Daily flow: 9 AM content pack → 4 PM check-in → 9 PM performance report
"""
import asyncio
import logging
import re
import sys
from datetime import date
from typing import Dict, Optional

from content.script_generator import generate_daily_scripts
from content.performance_tracker import fetch_all_platform_posts
from content.content_scorer import score_all_posts, get_top_post, get_low_post
from content.learning_engine import analyze_patterns, generate_ai_insight
from content.sheets_manager import (
    save_all_posts, save_patterns, get_recent_patterns,
    save_whatsapp_leads, get_today_lead_count,
)
from reporting.telegram_reporter import send_message
from config import TELEGRAM_CHAT_ID, OWNER_CHAT_ID

logger = logging.getLogger(__name__)


# ── 9 AM — Content Pack ───────────────────────────────────────────────────────

async def run_morning():
    logger.info("Running morning content generation (9 AM WAT)")

    patterns = get_recent_patterns() or {}
    scripts  = generate_daily_scripts(learning_context=patterns)
    today    = date.today().strftime("%A, %d %B %Y")

    header = (
        f"🎬 <b>NEXORA DAILY CONTENT PACK</b>\n"
        f"📅 {today}\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
    )
    footer = (
        f"\n\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"📋 Copy into Word doc. Film both videos today.\n"
        f"📣 All videos end with: <b>Send 'SYSTEM' on WhatsApp</b>\n"
        f"📊 Performance report: tonight at 9 PM"
    )

    # Send header + scripts (may chunk if long) + footer separately
    await send_message(TELEGRAM_CHAT_ID, header + scripts + footer)
    logger.info("Morning content pack sent to Telegram")


# ── 4 PM — Check-In ───────────────────────────────────────────────────────────

async def run_afternoon():
    logger.info("Running afternoon check-in (4 PM WAT)")
    message = (
        "📊 <b>NEXORA 4 PM CONTENT CHECK-IN</b>\n\n"
        "How's today's content performing?\n\n"
        "1️⃣ Both videos posted? (Yes / No)\n"
        "2️⃣ Total comments so far?\n"
        "3️⃣ WhatsApp 'SYSTEM' messages received?\n\n"
        "Reply in format:\n"
        "<code>posted=yes comments=X leads=X</code>\n\n"
        "⚡ Full performance report sent at 9 PM."
    )
    await send_message(TELEGRAM_CHAT_ID, message)
    logger.info("Afternoon check-in sent")


# ── 9 PM — Performance Report ─────────────────────────────────────────────────

async def run_evening(whatsapp_leads: int = 0):
    logger.info("Running evening performance report (9 PM WAT)")

    posts = fetch_all_platform_posts(limit=10)

    if not posts:
        logger.warning("No posts fetched — sending fallback report")
        await _send_no_data_report(whatsapp_leads)
        return

    # Spread today's WhatsApp leads across posts proportionally by views
    if whatsapp_leads > 0:
        total_views = sum(p.get("views", 1) for p in posts) or len(posts)
        for post in posts:
            share = post.get("views", 1) / total_views
            post["whatsapp_leads"] = round(whatsapp_leads * share)

    scored_posts  = score_all_posts(posts)
    top_post      = get_top_post(scored_posts)
    low_post      = get_low_post(scored_posts)
    patterns      = analyze_patterns(scored_posts)
    insight, action = generate_ai_insight(scored_posts, patterns)

    save_all_posts(scored_posts)
    save_patterns(patterns)
    if whatsapp_leads > 0:
        save_whatsapp_leads(whatsapp_leads)

    total_views    = sum(p.get("views", 0)           for p in scored_posts)
    total_comments = sum(p.get("comments", 0)        for p in scored_posts)
    total_leads    = sum(p.get("whatsapp_leads", 0)  for p in scored_posts)
    avg_score      = sum(p.get("total_score", 0)     for p in scored_posts) / max(len(scored_posts), 1)

    report = _build_report(
        total_posts    = len(scored_posts),
        total_views    = total_views,
        total_comments = total_comments,
        total_leads    = int(total_leads),
        avg_score      = avg_score,
        top_post       = top_post,
        low_post       = low_post,
        insight        = insight,
        action         = action,
    )
    await send_message(OWNER_CHAT_ID, report)
    logger.info("Evening performance report sent")


def _build_report(
    total_posts, total_views, total_comments, total_leads,
    avg_score, top_post, low_post, insight, action,
) -> str:
    today = date.today().strftime("%d %B %Y")
    lines = [
        f"📊 <b>NEXORA PERFORMANCE REPORT</b>",
        f"📅 {today}",
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
        f"",
        f"📹 Posts Tracked:     <b>{total_posts}</b>",
        f"👁️ Total Views:       <b>{total_views:,}</b>",
        f"💬 Total Comments:    <b>{total_comments:,}</b>",
        f"📲 WhatsApp Leads:    <b>{total_leads}</b>",
        f"⭐ Avg Content Score: <b>{avg_score:.1f}/100</b>",
        f"",
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
    ]

    if top_post:
        lines += [
            f"",
            f"🔥 <b>TOP POST</b>",
            f"📌 {top_post.get('caption', 'N/A')[:80]}",
            f"🏆 Score: {top_post.get('total_score', 0)}/100 → <b>{top_post.get('classification', '')}</b>",
            f"📊 Views: {top_post.get('views', 0):,} | Likes: {top_post.get('likes', 0)} | "
            f"Shares: {top_post.get('shares', 0)} | Leads: {int(top_post.get('whatsapp_leads', 0))}",
            f"",
            f"<i>Why it worked: {_why_it_worked(top_post)}</i>",
        ]

    low_id  = low_post.get("post_id")
    top_id  = top_post.get("post_id")
    if low_post and low_id != top_id:
        lines += [
            f"",
            f"⚠️ <b>WEAK POST</b>",
            f"📌 {low_post.get('caption', 'N/A')[:80]}",
            f"📉 Score: {low_post.get('total_score', 0)}/100 → <b>{low_post.get('classification', '')}</b>",
            f"<i>Problem: {_why_it_failed(low_post)}</i>",
        ]

    lines += [
        f"",
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
        f"",
        f"🧠 <b>INSIGHT:</b>",
        f"{insight}",
        f"",
        f"🎯 <b>ACTION FOR TOMORROW:</b>",
        f"{action}",
        f"",
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
        f"🔁 Next content pack: Tomorrow 9:00 AM WAT",
    ]
    return "\n".join(lines)


def _why_it_worked(post: Dict) -> str:
    strong = []
    if post.get("reach_score", 0) >= 15:
        strong.append("strong reach")
    if post.get("engagement_score", 0) >= 20:
        strong.append("high engagement")
    if post.get("retention_score", 0) >= 15:
        strong.append("good saves/shares")
    if post.get("conversion_score", 0) >= 20:
        strong.append("WhatsApp conversions")
    return ", ".join(strong) if strong else "balanced performance across all metrics"


def _why_it_failed(post: Dict) -> str:
    weak = []
    if post.get("reach_score", 0) < 5:
        weak.append("low reach — hook not stopping the scroll")
    if post.get("engagement_score", 0) < 8:
        weak.append("low engagement — no comment trigger")
    if post.get("conversion_score", 0) == 0:
        weak.append("zero leads — CTA unclear or missing")
    return "; ".join(weak) if weak else "below baseline on all metrics — revisit format"


async def _send_no_data_report(whatsapp_leads: int):
    leads = whatsapp_leads or get_today_lead_count()
    message = (
        f"📊 <b>NEXORA PERFORMANCE REPORT</b>\n"
        f"📅 {date.today().strftime('%d %B %Y')}\n\n"
        f"⚠️ No platform metrics available.\n"
        f"Connect Meta + TikTok API credentials in .env to enable live tracking.\n\n"
        f"📲 WhatsApp leads today: <b>{leads}</b>\n\n"
        f"🔁 Next content pack: Tomorrow 9:00 AM WAT"
    )
    await send_message(OWNER_CHAT_ID, message)


# ── Telegram reply parser (for 4 PM responses) ────────────────────────────────

def parse_checkin_reply(text: str) -> Dict:
    result = {"posted": False, "comments": 0, "leads": 0}
    m = re.search(r"posted\s*=\s*(yes|no)", text, re.IGNORECASE)
    if m:
        result["posted"] = m.group(1).lower() == "yes"
    m = re.search(r"comments\s*=\s*(\d+)", text, re.IGNORECASE)
    if m:
        result["comments"] = int(m.group(1))
    m = re.search(r"leads\s*=\s*(\d+)", text, re.IGNORECASE)
    if m:
        result["leads"] = int(m.group(1))
    return result


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s — %(message)s",
    )

    mode  = sys.argv[1] if len(sys.argv) > 1 else "morning"
    leads = int(sys.argv[2]) if len(sys.argv) > 2 else 0

    if mode == "morning":
        asyncio.run(run_morning())
    elif mode == "afternoon":
        asyncio.run(run_afternoon())
    elif mode == "evening":
        asyncio.run(run_evening(whatsapp_leads=leads))
    else:
        print("Usage: python content_engine.py [morning|afternoon|evening] [leads_count]")
        print()
        print("Examples:")
        print("  python content_engine.py morning")
        print("  python content_engine.py afternoon")
        print("  python content_engine.py evening 7")

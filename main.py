"""
NEXORA SALES OPERATING SYSTEM — Main Orchestrator

Modes:
  python main.py                    → Run full daily lead cycle now
  python main.py --bot              → Start CRM bot (no scheduler)
  python main.py --scheduler        → Start scheduler daemon (no bot)
  python main.py --full             → Start bot + scheduler together (production)
  python main.py --checkin          → Send check-in message now
  python main.py --report           → Send night report now
  python main.py --test             → Dry run (no Telegram / DB writes)
"""
import asyncio
import logging
import sys
from datetime import date

from scrapers.google_maps         import scrape_google_maps
from scrapers.instagram           import scrape_instagram
from processing.pipeline          import run_pipeline
from storage.sheets               import load_known_ids, save_leads, save_daily_stats, get_today_stats
from reporting.telegram_reporter  import send_daily_brief, send_checkin, send_night_report
from reporting.insight_engine     import generate_insight_and_suggestion
from database.db                  import init_db, insert_leads
from config                       import SEARCH_TARGETS, INSTAGRAM_HASHTAGS, TELEGRAM_BOT_TOKEN

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("nexora")

DRY_RUN = "--test" in sys.argv


async def run_daily_lead_cycle():
    logger.info("=== NEXORA — Daily Lead Cycle START ===")

    raw_leads = []
    for target in SEARCH_TARGETS:
        raw_leads += scrape_google_maps(target["keyword"], target["city"])
    raw_leads += scrape_instagram(INSTAGRAM_HASHTAGS)
    logger.info(f"Total raw leads collected: {len(raw_leads)}")

    known_ids = load_known_ids() if not DRY_RUN else set()
    result    = run_pipeline(raw_leads, known_ids)
    all_leads = result["all_leads"]
    top_leads = result["top_leads"]
    stats     = result["stats"]

    logger.info(f"Pipeline stats: {stats}")

    if not DRY_RUN:
        save_leads(all_leads)
        save_daily_stats(stats)
        insert_leads(all_leads)

    if not DRY_RUN:
        await send_daily_brief(top_leads, all_leads)
    else:
        logger.info(f"[DRY RUN] Would send brief with {len(all_leads)} leads")

    logger.info("=== Daily Cycle COMPLETE ===")
    return result


async def run_checkin():
    await send_checkin()


async def run_night_report(stats: dict = None, top_leads: list = None):
    if stats is None:
        stats = get_today_stats()
    insight, suggestion = generate_insight_and_suggestion(stats, top_leads or [])
    await send_night_report(stats, insight, suggestion)


# ── Telegram CRM Bot ──────────────────────────────────────────────────────────

def build_application():
    from telegram.ext import Application, CommandHandler
    from bot.agent_handler import (
        cmd_start, cmd_lead, cmd_claim, cmd_my_leads, cmd_switch,
        cmd_call, cmd_sent, cmd_demo, cmd_close, cmd_done,
        cmd_hook, cmd_reply, cmd_followups,
    )
    from bot.admin_handler import (
        cmd_admin_report, cmd_pipeline, cmd_agents, cmd_agent,
        cmd_intelligence, cmd_followup_all, cmd_broadcast, cmd_add_leads,
    )

    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    # Agent commands
    app.add_handler(CommandHandler("start",     cmd_start))
    app.add_handler(CommandHandler("lead",      cmd_lead))
    app.add_handler(CommandHandler("claim",     cmd_claim))
    app.add_handler(CommandHandler("my_leads",  cmd_my_leads))
    app.add_handler(CommandHandler("switch",    cmd_switch))
    app.add_handler(CommandHandler("call",      cmd_call))
    app.add_handler(CommandHandler("sent",      cmd_sent))
    app.add_handler(CommandHandler("demo",      cmd_demo))
    app.add_handler(CommandHandler("close",     cmd_close))
    app.add_handler(CommandHandler("done",      cmd_done))
    app.add_handler(CommandHandler("hook",      cmd_hook))
    app.add_handler(CommandHandler("reply",     cmd_reply))
    app.add_handler(CommandHandler("followups", cmd_followups))

    # Admin commands
    app.add_handler(CommandHandler("admin_report",  cmd_admin_report))
    app.add_handler(CommandHandler("pipeline",      cmd_pipeline))
    app.add_handler(CommandHandler("agents",        cmd_agents))
    app.add_handler(CommandHandler("agent",         cmd_agent))
    app.add_handler(CommandHandler("intelligence",  cmd_intelligence))
    app.add_handler(CommandHandler("followup_all",  cmd_followup_all))
    app.add_handler(CommandHandler("broadcast",     cmd_broadcast))
    app.add_handler(CommandHandler("add_leads",     cmd_add_leads))

    return app


def start_bot_only():
    """Run only the Telegram bot (no scheduler)."""
    init_db()
    app = build_application()
    logger.info("NEXORA CRM Bot starting...")
    app.run_polling(drop_pending_updates=True)


def start_full():
    """Run Telegram bot + APScheduler in the same asyncio loop."""
    from apscheduler.schedulers.asyncio import AsyncIOScheduler
    from config import DAILY_BRIEF_HOUR, CHECKIN_HOUR, NIGHT_REPORT_HOUR

    init_db()
    app = build_application()

    async def _run():
        scheduler = AsyncIOScheduler(timezone="UTC")
        scheduler.add_job(run_daily_lead_cycle, trigger="cron",
                          hour=DAILY_BRIEF_HOUR, minute=0, id="daily_brief")
        scheduler.add_job(run_checkin, trigger="cron",
                          hour=CHECKIN_HOUR, minute=0, id="checkin")
        scheduler.add_job(run_night_report, trigger="cron",
                          hour=NIGHT_REPORT_HOUR, minute=0, id="night_report")
        scheduler.start()
        logger.info(
            f"Scheduler LIVE — Brief@{DAILY_BRIEF_HOUR}UTC "
            f"| Check-in@{CHECKIN_HOUR}UTC "
            f"| Report@{NIGHT_REPORT_HOUR}UTC"
        )

        async with app:
            await app.start()
            await app.updater.start_polling(drop_pending_updates=True)
            logger.info("NEXORA CRM Bot + Scheduler running.")
            try:
                while True:
                    await asyncio.sleep(3600)
            except (KeyboardInterrupt, SystemExit):
                pass
            finally:
                scheduler.shutdown()
                await app.updater.stop()
                await app.stop()

    asyncio.run(_run())


def start_scheduler():
    """Run only the scheduler (no bot)."""
    from apscheduler.schedulers.asyncio import AsyncIOScheduler
    from config import DAILY_BRIEF_HOUR, CHECKIN_HOUR, NIGHT_REPORT_HOUR

    init_db()

    async def _run():
        scheduler = AsyncIOScheduler(timezone="UTC")
        scheduler.add_job(run_daily_lead_cycle, trigger="cron",
                          hour=DAILY_BRIEF_HOUR, minute=0, id="daily_brief")
        scheduler.add_job(run_checkin, trigger="cron",
                          hour=CHECKIN_HOUR, minute=0, id="checkin")
        scheduler.add_job(run_night_report, trigger="cron",
                          hour=NIGHT_REPORT_HOUR, minute=0, id="night_report")
        scheduler.start()
        logger.info("Scheduler-only mode LIVE")
        try:
            while True:
                await asyncio.sleep(3600)
        except (KeyboardInterrupt, SystemExit):
            scheduler.shutdown()

    asyncio.run(_run())


# ── Entry Point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    if "--full" in sys.argv:
        start_full()
    elif "--bot" in sys.argv:
        start_bot_only()
    elif "--scheduler" in sys.argv:
        start_scheduler()
    elif "--checkin" in sys.argv:
        asyncio.run(run_checkin())
    elif "--report" in sys.argv:
        asyncio.run(run_night_report())
    else:
        init_db()
        asyncio.run(run_daily_lead_cycle())

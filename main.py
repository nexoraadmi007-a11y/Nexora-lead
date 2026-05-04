"""
NEXORA LEAD ENGINE v2 — Main Orchestrator

Trigger:
  python main.py                    → Run full daily lead cycle now
  python main.py --scheduler        → Start scheduled daemon (9AM/4PM/9PM)
  python main.py --checkin          → Send check-in message now
  python main.py --report           → Send night report now
  python main.py --test             → Dry run (no Telegram / Sheets writes)
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
from config import SEARCH_TARGETS, INSTAGRAM_HASHTAGS

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("nexora_lead")

DRY_RUN = "--test" in sys.argv


async def run_daily_lead_cycle():
    logger.info("=== NEXORA LEAD ENGINE — Daily Cycle START ===")

    # 1. Scrape
    raw_leads = []
    for target in SEARCH_TARGETS:
        raw_leads += scrape_google_maps(target["keyword"], target["city"])

    raw_leads += scrape_instagram(INSTAGRAM_HASHTAGS)
    logger.info(f"Total raw leads collected: {len(raw_leads)}")

    # 2. Load known IDs for deduplication
    known_ids = load_known_ids() if not DRY_RUN else set()

    # 3. Run pipeline
    result     = run_pipeline(raw_leads, known_ids)
    all_leads  = result["all_leads"]
    top_leads  = result["top_leads"]
    stats      = result["stats"]

    logger.info(f"Pipeline stats: {stats}")

    if not all_leads:
        logger.warning("No qualified leads found today")

    # 4. Save to Sheets
    if not DRY_RUN:
        save_leads(all_leads)
        save_daily_stats(stats)

    # 5. Send Telegram brief
    if not DRY_RUN:
        await send_daily_brief(top_leads, all_leads)
    else:
        from reporting.telegram_reporter import build_daily_brief
        print("\n" + "=" * 60)
        print(build_daily_brief(top_leads, all_leads))
        print("=" * 60)

    logger.info("=== Daily Cycle COMPLETE ===")
    return result


async def run_checkin():
    await send_checkin()


async def run_night_report(stats: dict = None, top_leads: list = None):
    if stats is None:
        stats = get_today_stats()
    insight, suggestion = generate_insight_and_suggestion(
        stats, top_leads or []
    )
    await send_night_report(stats, insight, suggestion)


# ── Scheduler ─────────────────────────────────────────────────────────────────

def start_scheduler():
    from apscheduler.schedulers.asyncio import AsyncIOScheduler
    from config import DAILY_BRIEF_HOUR, CHECKIN_HOUR, NIGHT_REPORT_HOUR

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
            f"✅ Scheduler LIVE — Brief@{DAILY_BRIEF_HOUR}UTC "
            f"| Check-in@{CHECKIN_HOUR}UTC "
            f"| Report@{NIGHT_REPORT_HOUR}UTC (WAT = UTC+1)"
        )
        try:
            while True:
                await asyncio.sleep(3600)
        except (KeyboardInterrupt, SystemExit):
            scheduler.shutdown()
            logger.info("Scheduler stopped")

    asyncio.run(_run())


# ── Entry Point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    if "--scheduler" in sys.argv:
        start_scheduler()
    elif "--checkin" in sys.argv:
        asyncio.run(run_checkin())
    elif "--report" in sys.argv:
        asyncio.run(run_night_report())
    else:
        asyncio.run(run_daily_lead_cycle())

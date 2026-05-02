"""
NEXORA Grant Bot — entry point.
Run: python run_grant_bot.py
"""
import logging
import os
from dotenv import load_dotenv
from grant.grant_bot import build_grant_application

load_dotenv()

logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(name)s — %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


def main():
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN not set in .env")

    logger.info("Starting NEXORA Grant Bot...")
    app = build_grant_application(token)
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()

"""
Instagram lead scraper via Apify apify/instagram-scraper actor.
"""
import logging
from datetime import datetime, timezone, timedelta
from typing import List, Dict
from apify_client import ApifyClient
from config import APIFY_TOKEN, INSTAGRAM_ACTOR_ID, RECENT_POST_DAYS

logger = logging.getLogger(__name__)


def scrape_instagram(hashtags: List[str], max_posts: int = 50) -> List[Dict]:
    """
    Scrape business profiles from Instagram hashtags.

    Returns raw lead dicts with keys:
      name, phone, username, bio, website, followers,
      post_count, last_post_days, source
    """
    if not APIFY_TOKEN:
        logger.warning("APIFY_TOKEN not set — skipping Instagram scrape")
        return []

    client = ApifyClient(APIFY_TOKEN)
    run_input = {
        "hashtags": hashtags,
        "resultsLimit": max_posts,
        "scrapeType": "posts",
    }

    logger.info(f"Scraping Instagram hashtags: {hashtags}")
    run = client.actor(INSTAGRAM_ACTOR_ID).call(run_input=run_input)

    seen_usernames = set()
    leads = []

    for post in client.dataset(run["defaultDatasetId"]).iterate_items():
        owner = post.get("ownerUsername") or post.get("owner", {}).get("username", "")
        if not owner or owner in seen_usernames:
            continue
        seen_usernames.add(owner)

        timestamp = post.get("timestamp") or post.get("taken_at_timestamp")
        last_post_days = _days_since(timestamp)
        bio = post.get("ownerFullName", "") or ""

        leads.append({
            "name":           post.get("ownerFullName") or owner,
            "phone":          _extract_phone_from_bio(bio),
            "username":       owner,
            "bio":            bio,
            "website":        post.get("ownerExternalUrl", ""),
            "followers":      post.get("followersCount", 0),
            "post_count":     post.get("postsCount", 0),
            "last_post_days": last_post_days,
            "address":        "",
            "city":           "",
            "category":       "",
            "source":         "instagram",
        })

    logger.info(f"Instagram returned {len(leads)} unique profiles")
    return leads


def _days_since(timestamp) -> int:
    """Return days since a post timestamp, or 999 if unknown."""
    if not timestamp:
        return 999
    try:
        if isinstance(timestamp, (int, float)):
            dt = datetime.fromtimestamp(timestamp, tz=timezone.utc)
        else:
            dt = datetime.fromisoformat(str(timestamp).replace("Z", "+00:00"))
        return (datetime.now(tz=timezone.utc) - dt).days
    except Exception:
        return 999


def _extract_phone_from_bio(bio: str) -> str:
    """Best-effort phone extraction from an Instagram bio."""
    import re
    match = re.search(r"(\+?\d[\d\s\-]{7,14}\d)", bio)
    return match.group(1).strip() if match else ""

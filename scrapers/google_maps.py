"""
Google Maps lead scraper via Apify compass/crawler-google-places actor.
"""
import logging
from typing import List, Dict
from apify_client import ApifyClient
from config import APIFY_TOKEN, GOOGLE_MAPS_ACTOR_ID

logger = logging.getLogger(__name__)


def scrape_google_maps(keyword: str, city: str, max_results: int = 40) -> List[Dict]:
    """
    Scrape business listings from Google Maps.

    Returns a list of raw lead dicts with keys:
      name, phone, address, website, rating, review_count,
      category, latitude, longitude, source
    """
    if not APIFY_TOKEN:
        logger.warning("APIFY_TOKEN not set — returning mock data for testing")
        return _mock_google_leads(keyword, city)

    client = ApifyClient(APIFY_TOKEN)
    run_input = {
        "searchStringsArray": [f"{keyword} in {city}"],
        "maxCrawledPlacesPerSearch": max_results,
        "language": "en",
        "includeWebResults": False,
    }

    logger.info(f"Scraping Google Maps: {keyword} in {city}")
    run = client.actor(GOOGLE_MAPS_ACTOR_ID).call(run_input=run_input)

    leads = []
    for item in client.dataset(run["defaultDatasetId"]).iterate_items():
        phone = (item.get("phone") or item.get("phoneUnformatted") or "").strip()
        leads.append({
            "name":         item.get("title", ""),
            "phone":        phone,
            "address":      item.get("address", ""),
            "website":      item.get("website", ""),
            "rating":       item.get("totalScore", 0),
            "review_count": item.get("reviewsCount", 0),
            "category":     item.get("categoryName", ""),
            "latitude":     item.get("location", {}).get("lat"),
            "longitude":    item.get("location", {}).get("lng"),
            "city":         city,
            "source":       "google_maps",
        })

    logger.info(f"Google Maps returned {len(leads)} results")
    return leads


def _mock_google_leads(keyword: str, city: str) -> List[Dict]:
    """Fallback mock data when Apify token is not configured."""
    return [
        {
            "name": f"Sample {keyword.title()} Business {i}",
            "phone": f"+234801000000{i}",
            "address": f"{i} Test Street, {city}",
            "website": "",
            "rating": 3.5,
            "review_count": 12,
            "category": keyword,
            "latitude": None,
            "longitude": None,
            "city": city,
            "source": "google_maps_mock",
        }
        for i in range(1, 6)
    ]

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

    # City → GPS centre + country override to avoid ambiguous names (e.g. Lagos Portugal vs Nigeria)
    GEO_CENTRES = {
        "Lagos":         {"lat": 6.5244,  "lng": 3.3792,  "country": "Nigeria"},
        "Abuja":         {"lat": 9.0765,  "lng": 7.3986,  "country": "Nigeria"},
        "Port Harcourt": {"lat": 4.8156,  "lng": 7.0498,  "country": "Nigeria"},
        "Ibadan":        {"lat": 7.3775,  "lng": 3.9470,  "country": "Nigeria"},
        "Kano":          {"lat": 12.0022, "lng": 8.5920,  "country": "Nigeria"},
        "Abeokuta":      {"lat": 7.1475,  "lng": 3.3619,  "country": "Nigeria"},
        "Benin City":    {"lat": 6.3350,  "lng": 5.6271,  "country": "Nigeria"},
        "Enugu":         {"lat": 6.4584,  "lng": 7.5464,  "country": "Nigeria"},
    }
    geo = GEO_CENTRES.get(city, {})
    country = geo.get("country", "")
    search_query = f"{keyword} in {city}{', ' + country if country else ''}"

    client = ApifyClient(APIFY_TOKEN)
    run_input = {
        "searchStringsArray": [search_query],
        "maxCrawledPlacesPerSearch": max_results,
        "language": "en",
        "includeWebResults": False,
    }
    if geo:
        run_input["customGeolocation"] = {
            "type": "Point",
            "coordinates": [geo["lng"], geo["lat"]],
            "radiusKm": 30,
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

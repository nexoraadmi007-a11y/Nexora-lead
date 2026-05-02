import os
from dotenv import load_dotenv

load_dotenv()

# ── Telegram ──────────────────────────────────────────────────────────────────
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID   = os.getenv("TELEGRAM_CHAT_ID")
OWNER_CHAT_ID      = os.getenv("OWNER_CHAT_ID", TELEGRAM_CHAT_ID)

# ── Claude ────────────────────────────────────────────────────────────────────
CLAUDE_API_KEY  = os.getenv("CLAUDE_API_KEY")
CLAUDE_MODEL    = "claude-sonnet-4-6"

# ── Apify (scraping) ──────────────────────────────────────────────────────────
APIFY_TOKEN                 = os.getenv("APIFY_TOKEN")
GOOGLE_MAPS_ACTOR_ID        = "compass/crawler-google-places"
INSTAGRAM_ACTOR_ID          = "apify/instagram-scraper"

# ── Google Sheets ─────────────────────────────────────────────────────────────
GOOGLE_SHEETS_CREDENTIALS   = os.getenv("GOOGLE_SHEETS_CREDENTIALS_PATH", "service_account.json")
GOOGLE_SHEETS_ID            = os.getenv("GOOGLE_SHEETS_ID")
LEADS_WORKSHEET             = "Leads"
STATS_WORKSHEET             = "Daily Stats"

# ── Lead Engine Settings ──────────────────────────────────────────────────────
MIN_LEAD_SCORE      = 6
TOP_N_LEADS         = 5
RECENT_POST_DAYS    = 7

# ── Search Targets (keyword + city pairs) ─────────────────────────────────────
# Edit this list to target specific markets
SEARCH_TARGETS = [
    {"keyword": "restaurant", "city": "Lagos"},
    {"keyword": "salon",      "city": "Lagos"},
    {"keyword": "fashion",    "city": "Lagos"},
    {"keyword": "pharmacy",   "city": "Lagos"},
    {"keyword": "building materials", "city": "Lagos"},
    {"keyword": "school",     "city": "Lagos"},
]

INSTAGRAM_HASHTAGS = [
    "lagosrestaurant",
    "lagossalon",
    "lagosfashion",
    "lagosbusiness",
]

# ── Niche Strategies ──────────────────────────────────────────────────────────
NICHE_STRATEGY = {
    "Restaurant":          "Speed + menu visibility",
    "Building Materials":  "Visual proof + WhatsApp conversion",
    "Salon":               "Booking + before/after visuals",
    "Fashion":             "Product showcase + DM-to-buy flow",
    "Pharmacy":            "Trust signals + quick contact",
    "School":              "Parent reassurance + inquiry flow",
    "Others":              "Clear contact + value proposition",
}

# ── Schedule Times (WAT = UTC+1) ──────────────────────────────────────────────
DAILY_BRIEF_HOUR     = 8   # 9 AM WAT = 8 UTC
CHECKIN_HOUR         = 15  # 4 PM WAT = 15 UTC
NIGHT_REPORT_HOUR    = 20  # 9 PM WAT = 20 UTC

# ── Meta Graph API ────────────────────────────────────────────────────────────
META_ACCESS_TOKEN            = os.getenv("META_ACCESS_TOKEN", "")
META_INSTAGRAM_ACCOUNT_ID    = os.getenv("META_INSTAGRAM_ACCOUNT_ID", "")
META_FACEBOOK_PAGE_ID        = os.getenv("META_FACEBOOK_PAGE_ID", "")

# ── TikTok API ────────────────────────────────────────────────────────────────
TIKTOK_ACCESS_TOKEN          = os.getenv("TIKTOK_ACCESS_TOKEN", "")
TIKTOK_OPEN_ID               = os.getenv("TIKTOK_OPEN_ID", "")

# ── Content Engine Settings ───────────────────────────────────────────────────
CONTENT_POSTS_WORKSHEET      = "Content Posts"
CONTENT_PATTERNS_WORKSHEET   = "Content Patterns"
CONTENT_LEADS_WORKSHEET      = "WhatsApp Leads"
WHATSAPP_TRIGGER_KEYWORD     = "SYSTEM"

# Scoring baselines — update after first week of real data
BASELINE_VIEWS               = 1000
BASELINE_REACH               = 800
BASELINE_ENGAGEMENT_RATE     = 0.03   # 3%
BASELINE_LEADS_PER_POST      = 2

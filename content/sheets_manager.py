import logging
from datetime import date
from typing import Dict, List, Optional
import gspread
from google.oauth2.service_account import Credentials
from config import (
    GOOGLE_SHEETS_CREDENTIALS, GOOGLE_SHEETS_ID,
    CONTENT_POSTS_WORKSHEET, CONTENT_PATTERNS_WORKSHEET, CONTENT_LEADS_WORKSHEET,
)

logger = logging.getLogger(__name__)

_SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
_gc: Optional[gspread.Client] = None


def _get_client() -> Optional[gspread.Client]:
    global _gc
    if _gc is None:
        try:
            creds = Credentials.from_service_account_file(GOOGLE_SHEETS_CREDENTIALS, scopes=_SCOPES)
            _gc = gspread.authorize(creds)
        except Exception as e:
            logger.error(f"Google Sheets auth failed: {e}")
    return _gc


def _get_worksheet(name: str) -> Optional[gspread.Worksheet]:
    gc = _get_client()
    if not gc or not GOOGLE_SHEETS_ID:
        return None
    try:
        wb = gc.open_by_key(GOOGLE_SHEETS_ID)
        try:
            return wb.worksheet(name)
        except gspread.WorksheetNotFound:
            return wb.add_worksheet(title=name, rows=2000, cols=25)
    except Exception as e:
        logger.error(f"Worksheet access failed ({name}): {e}")
        return None


def _ensure_headers(ws: gspread.Worksheet, headers: List[str]):
    if not ws.row_values(1):
        ws.append_row(headers)


# ── Content Posts ─────────────────────────────────────────────────────────────

_POST_HEADERS = [
    "Date", "Platform", "Post ID", "Caption",
    "Views", "Impressions", "Reach", "Likes", "Comments", "Shares", "Saves", "WhatsApp Leads",
    "Reach Score", "Engagement Score", "Retention Score", "Conversion Score",
    "Total Score", "Classification",
]


def save_content_post(post: Dict):
    ws = _get_worksheet(CONTENT_POSTS_WORKSHEET)
    if not ws:
        return
    _ensure_headers(ws, _POST_HEADERS)
    ws.append_row([
        date.today().isoformat(),
        post.get("platform", ""),
        post.get("post_id", ""),
        post.get("caption", "")[:120],
        post.get("views", 0),
        post.get("impressions", 0),
        post.get("reach", 0),
        post.get("likes", 0),
        post.get("comments", 0),
        post.get("shares", 0),
        post.get("saves", 0),
        post.get("whatsapp_leads", 0),
        post.get("reach_score", 0),
        post.get("engagement_score", 0),
        post.get("retention_score", 0),
        post.get("conversion_score", 0),
        post.get("total_score", 0),
        post.get("classification", ""),
    ])


def save_all_posts(scored_posts: List[Dict]):
    for post in scored_posts:
        save_content_post(post)
    logger.info(f"Saved {len(scored_posts)} posts to Sheets")


# ── Content Patterns ──────────────────────────────────────────────────────────

_PATTERN_HEADERS = [
    "Date", "Winning Hook", "Winning Content Type", "Weak Format",
    "Best Platform", "Scaled Count", "Weak Count", "Avg Score",
]


def save_patterns(patterns: Dict):
    ws = _get_worksheet(CONTENT_PATTERNS_WORKSHEET)
    if not ws:
        return
    _ensure_headers(ws, _PATTERN_HEADERS)
    ws.append_row([
        date.today().isoformat(),
        patterns.get("winning_hook", ""),
        patterns.get("winning_content_type", ""),
        patterns.get("weak_format", ""),
        patterns.get("best_platform", ""),
        patterns.get("scaled_count", 0),
        patterns.get("weak_count", 0),
        round(patterns.get("avg_score", 0), 1),
    ])


def get_recent_patterns() -> Optional[Dict]:
    ws = _get_worksheet(CONTENT_PATTERNS_WORKSHEET)
    if not ws:
        return None
    try:
        rows = ws.get_all_records()
        return rows[-1] if rows else None
    except Exception as e:
        logger.error(f"Failed to read patterns: {e}")
        return None


# ── WhatsApp Leads ────────────────────────────────────────────────────────────

_LEADS_HEADERS = ["Date", "WhatsApp Leads", "Note"]


def save_whatsapp_leads(count: int, note: str = ""):
    ws = _get_worksheet(CONTENT_LEADS_WORKSHEET)
    if not ws:
        return
    _ensure_headers(ws, _LEADS_HEADERS)
    ws.append_row([date.today().isoformat(), count, note])


def get_today_lead_count() -> int:
    ws = _get_worksheet(CONTENT_LEADS_WORKSHEET)
    if not ws:
        return 0
    try:
        today = date.today().isoformat()
        return sum(
            int(r.get("WhatsApp Leads", 0))
            for r in ws.get_all_records()
            if str(r.get("Date", "")) == today
        )
    except Exception as e:
        logger.error(f"Failed to get today's lead count: {e}")
        return 0

"""
Lead storage — SQLite primary, Google Sheets optional.

If service_account.json exists and GOOGLE_SHEETS_ID is set, syncs to Sheets.
Otherwise runs fully on local SQLite — no Google setup required.
"""
import csv
import logging
import sqlite3
from datetime import date
from pathlib import Path
from typing import Dict, List, Set

from config import (
    GOOGLE_SHEETS_CREDENTIALS,
    GOOGLE_SHEETS_ID,
    LEADS_WORKSHEET,
    STATS_WORKSHEET,
)

logger = logging.getLogger(__name__)

DB_PATH      = Path("data/leads.db")
EXPORTS_DIR  = Path("data/exports")

LEAD_COLUMNS = [
    "lead_id", "date", "name", "phone", "address", "city",
    "website", "source", "score", "intent", "niche", "opportunity", "hook",
]


# ── SQLite ────────────────────────────────────────────────────────────────────

def _get_conn():
    DB_PATH.parent.mkdir(exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS leads (
            lead_id TEXT PRIMARY KEY,
            date TEXT,
            name TEXT,
            phone TEXT,
            address TEXT,
            city TEXT,
            website TEXT,
            source TEXT,
            score INTEGER,
            intent TEXT,
            niche TEXT,
            opportunity TEXT,
            hook TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS daily_stats (
            date TEXT PRIMARY KEY,
            total_raw INTEGER,
            after_dedup INTEGER,
            after_score INTEGER,
            after_intent INTEGER,
            top_n INTEGER,
            contacted INTEGER DEFAULT 0,
            responses INTEGER DEFAULT 0,
            demos INTEGER DEFAULT 0
        )
    """)
    conn.commit()
    return conn


def load_known_ids() -> Set[str]:
    try:
        conn = _get_conn()
        rows = conn.execute("SELECT lead_id FROM leads").fetchall()
        conn.close()
        return {r[0] for r in rows}
    except Exception as e:
        logger.warning(f"Could not load known IDs: {e}")
        return set()


def save_leads(leads: List[Dict]) -> int:
    if not leads:
        return 0
    today = str(date.today())
    saved = 0
    try:
        conn = _get_conn()
        for lead in leads:
            try:
                conn.execute(
                    "INSERT OR IGNORE INTO leads VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    [lead.get(c, "") for c in LEAD_COLUMNS[0:1]] +
                    [today] +
                    [lead.get(c, "") for c in LEAD_COLUMNS[2:]],
                )
                saved += 1
            except Exception:
                pass
        conn.commit()
        conn.close()
        logger.info(f"Saved {saved} leads to SQLite")

        _export_csv(leads, today)
        _sync_to_sheets(leads)
        return saved
    except Exception as e:
        logger.error(f"Failed to save leads: {e}")
        return 0


def save_daily_stats(stats: Dict):
    today = str(date.today())
    try:
        conn = _get_conn()
        conn.execute(
            """INSERT OR REPLACE INTO daily_stats
               (date, total_raw, after_dedup, after_score, after_intent, top_n)
               VALUES (?,?,?,?,?,?)""",
            [today, stats.get("total_raw", 0), stats.get("after_dedup", 0),
             stats.get("after_score", 0), stats.get("after_intent", 0),
             stats.get("top_n", 0)],
        )
        conn.commit()
        conn.close()
    except Exception as e:
        logger.warning(f"Could not save daily stats: {e}")


def update_checkin_stats(contacted: int, responses: int, demos: int):
    today = str(date.today())
    try:
        conn = _get_conn()
        conn.execute(
            "UPDATE daily_stats SET contacted=?, responses=?, demos=? WHERE date=?",
            [contacted, responses, demos, today],
        )
        conn.commit()
        conn.close()
    except Exception as e:
        logger.warning(f"Could not update check-in stats: {e}")


def get_today_stats() -> Dict:
    today = str(date.today())
    try:
        conn  = _get_conn()
        row   = conn.execute(
            "SELECT * FROM daily_stats WHERE date=?", [today]
        ).fetchone()
        conn.close()
        if row:
            cols = ["date","total_raw","after_dedup","after_score","after_intent",
                    "top_n","contacted","responses","demos"]
            return dict(zip(cols, row))
    except Exception as e:
        logger.warning(f"Could not get today stats: {e}")
    return {}


# ── CSV Export ────────────────────────────────────────────────────────────────

def _export_csv(leads: List[Dict], today: str):
    try:
        EXPORTS_DIR.mkdir(parents=True, exist_ok=True)
        path = EXPORTS_DIR / f"leads_{today}.csv"
        with open(path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=LEAD_COLUMNS)
            writer.writeheader()
            for lead in leads:
                writer.writerow({c: lead.get(c, "") for c in LEAD_COLUMNS})
        logger.info(f"CSV exported: {path}")
    except Exception as e:
        logger.warning(f"CSV export failed: {e}")


# ── Google Sheets (optional) ──────────────────────────────────────────────────

def _sheets_available() -> bool:
    return bool(GOOGLE_SHEETS_ID) and Path(GOOGLE_SHEETS_CREDENTIALS).exists()


def _sync_to_sheets(leads: List[Dict]):
    if not _sheets_available():
        return
    try:
        import gspread
        from google.oauth2.service_account import Credentials

        creds = Credentials.from_service_account_file(
            GOOGLE_SHEETS_CREDENTIALS,
            scopes=[
                "https://www.googleapis.com/auth/spreadsheets",
                "https://www.googleapis.com/auth/drive",
            ],
        )
        gc = gspread.authorize(creds)
        sh = gc.open_by_key(GOOGLE_SHEETS_ID)

        try:
            ws = sh.worksheet(LEADS_WORKSHEET)
        except gspread.WorksheetNotFound:
            ws = sh.add_worksheet(title=LEADS_WORKSHEET, rows=1000, cols=20)
            ws.append_row(LEAD_COLUMNS)

        today = str(date.today())
        rows  = [[lead.get(c, "") for c in LEAD_COLUMNS[0:1]] + [today] +
                 [lead.get(c, "") for c in LEAD_COLUMNS[2:]] for lead in leads]
        ws.append_rows(rows, value_input_option="USER_ENTERED")
        logger.info(f"Synced {len(rows)} leads to Google Sheets")
    except Exception as e:
        logger.warning(f"Google Sheets sync skipped: {e}")

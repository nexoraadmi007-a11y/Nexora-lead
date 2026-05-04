"""
SQLite persistence layer for the NEXORA Sales Operating System.
Tables: agents, leads, conversations, performance
"""
import sqlite3
import logging
from contextlib import contextmanager
from datetime import date, datetime
from pathlib import Path
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)

DB_PATH = Path("data/nexora_crm.db")


@contextmanager
def _conn():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(DB_PATH, detect_types=sqlite3.PARSE_DECLTYPES)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA journal_mode=WAL")
    con.execute("PRAGMA foreign_keys=ON")
    try:
        yield con
        con.commit()
    except Exception:
        con.rollback()
        raise
    finally:
        con.close()


def init_db():
    with _conn() as con:
        con.executescript("""
        CREATE TABLE IF NOT EXISTS agents (
            chat_id   TEXT PRIMARY KEY,
            name      TEXT NOT NULL,
            status    TEXT NOT NULL DEFAULT 'active',
            joined_at TEXT NOT NULL DEFAULT (date('now'))
        );

        CREATE TABLE IF NOT EXISTS leads (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            name          TEXT NOT NULL,
            phone         TEXT,
            address       TEXT,
            city          TEXT,
            niche         TEXT,
            score         REAL DEFAULT 0,
            intent        TEXT DEFAULT 'LOW',
            opportunity   TEXT,
            hook          TEXT,
            source        TEXT,
            stage         TEXT NOT NULL DEFAULT 'new',
            agent_id      TEXT REFERENCES agents(chat_id),
            claimed_at    TEXT,
            last_contact  TEXT,
            notes         TEXT,
            created_at    TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at    TEXT NOT NULL DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS conversations (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            lead_id    INTEGER REFERENCES leads(id),
            agent_id   TEXT REFERENCES agents(chat_id),
            direction  TEXT NOT NULL,
            message    TEXT NOT NULL,
            ts         TEXT NOT NULL DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS performance (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            agent_id   TEXT REFERENCES agents(chat_id),
            report_date TEXT NOT NULL,
            contacted  INTEGER DEFAULT 0,
            responses  INTEGER DEFAULT 0,
            demos      INTEGER DEFAULT 0,
            won        INTEGER DEFAULT 0,
            lost       INTEGER DEFAULT 0,
            UNIQUE(agent_id, report_date)
        );
        """)
    logger.info("CRM database initialised")


# ── Agents ────────────────────────────────────────────────────────────────────

def upsert_agent(chat_id: str, name: str):
    with _conn() as con:
        con.execute(
            "INSERT INTO agents(chat_id, name) VALUES(?,?) "
            "ON CONFLICT(chat_id) DO UPDATE SET name=excluded.name",
            (str(chat_id), name),
        )


def get_agents(status: str = "active") -> List[Dict]:
    with _conn() as con:
        rows = con.execute(
            "SELECT * FROM agents WHERE status=?", (status,)
        ).fetchall()
    return [dict(r) for r in rows]


def set_agent_status(chat_id: str, status: str):
    with _conn() as con:
        con.execute("UPDATE agents SET status=? WHERE chat_id=?", (status, str(chat_id)))


# ── Leads ─────────────────────────────────────────────────────────────────────

def insert_leads(leads: List[Dict]) -> int:
    """Bulk-insert leads (deduplicated by name+phone). Returns count inserted."""
    inserted = 0
    with _conn() as con:
        for lead in leads:
            existing = con.execute(
                "SELECT id FROM leads WHERE name=? AND (phone=? OR (phone IS NULL AND ?=''))",
                (lead.get("name", ""), lead.get("phone", ""), lead.get("phone", "")),
            ).fetchone()
            if existing:
                continue
            con.execute(
                """INSERT INTO leads
                   (name,phone,address,city,niche,score,intent,opportunity,hook,source)
                   VALUES(?,?,?,?,?,?,?,?,?,?)""",
                (
                    lead.get("name", ""),
                    lead.get("phone", ""),
                    lead.get("address", ""),
                    lead.get("city", ""),
                    lead.get("niche", ""),
                    lead.get("score", 0),
                    lead.get("intent", "LOW"),
                    lead.get("opportunity", ""),
                    lead.get("hook", ""),
                    lead.get("source", ""),
                ),
            )
            inserted += 1
    return inserted


def get_leads(stage: str = None, agent_id: str = None, limit: int = 20) -> List[Dict]:
    clauses, params = [], []
    if stage:
        clauses.append("stage=?"); params.append(stage)
    if agent_id:
        clauses.append("agent_id=?"); params.append(str(agent_id))
    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    with _conn() as con:
        rows = con.execute(
            f"SELECT * FROM leads {where} ORDER BY score DESC, created_at DESC LIMIT ?",
            params + [limit],
        ).fetchall()
    return [dict(r) for r in rows]


def get_lead(lead_id: int) -> Optional[Dict]:
    with _conn() as con:
        row = con.execute("SELECT * FROM leads WHERE id=?", (lead_id,)).fetchone()
    return dict(row) if row else None


def claim_lead(lead_id: int, agent_id: str) -> bool:
    with _conn() as con:
        row = con.execute("SELECT agent_id FROM leads WHERE id=?", (lead_id,)).fetchone()
        if not row:
            return False
        if row["agent_id"] and row["agent_id"] != str(agent_id):
            return False
        con.execute(
            "UPDATE leads SET agent_id=?, claimed_at=datetime('now'), stage='contacted', updated_at=datetime('now') "
            "WHERE id=?",
            (str(agent_id), lead_id),
        )
    return True


def update_lead_stage(lead_id: int, stage: str, notes: str = None):
    with _conn() as con:
        if notes:
            con.execute(
                "UPDATE leads SET stage=?, notes=?, last_contact=datetime('now'), updated_at=datetime('now') WHERE id=?",
                (stage, notes, lead_id),
            )
        else:
            con.execute(
                "UPDATE leads SET stage=?, last_contact=datetime('now'), updated_at=datetime('now') WHERE id=?",
                (stage, lead_id),
            )


def get_pipeline_summary() -> Dict:
    stages = ["new", "contacted", "engaged", "interested", "closing", "won", "lost"]
    with _conn() as con:
        result = {}
        for s in stages:
            count = con.execute("SELECT COUNT(*) FROM leads WHERE stage=?", (s,)).fetchone()[0]
            result[s] = count
    return result


def get_unclaimed_leads(limit: int = 10) -> List[Dict]:
    with _conn() as con:
        rows = con.execute(
            "SELECT * FROM leads WHERE stage='new' AND agent_id IS NULL "
            "ORDER BY score DESC LIMIT ?",
            (limit,),
        ).fetchall()
    return [dict(r) for r in rows]


def get_stale_leads(hours: int = 48) -> List[Dict]:
    """Leads that have been contacted but not updated in X hours."""
    with _conn() as con:
        rows = con.execute(
            """SELECT * FROM leads
               WHERE stage NOT IN ('new','won','lost')
               AND (last_contact < datetime('now', ? || ' hours')
                    OR (last_contact IS NULL AND claimed_at < datetime('now', ? || ' hours')))
               ORDER BY score DESC""",
            (f"-{hours}", f"-{hours}"),
        ).fetchall()
    return [dict(r) for r in rows]


# ── Conversations ─────────────────────────────────────────────────────────────

def log_conversation(lead_id: int, agent_id: str, direction: str, message: str):
    with _conn() as con:
        con.execute(
            "INSERT INTO conversations(lead_id,agent_id,direction,message) VALUES(?,?,?,?)",
            (lead_id, str(agent_id), direction, message),
        )


def get_conversation_history(lead_id: int, limit: int = 10) -> List[Dict]:
    with _conn() as con:
        rows = con.execute(
            "SELECT * FROM conversations WHERE lead_id=? ORDER BY ts DESC LIMIT ?",
            (lead_id, limit),
        ).fetchall()
    return [dict(r) for r in reversed(rows)]


# ── Performance ───────────────────────────────────────────────────────────────

def bump_stat(agent_id: str, field: str, amount: int = 1):
    today = date.today().isoformat()
    with _conn() as con:
        con.execute(
            f"INSERT INTO performance(agent_id, report_date, {field}) VALUES(?,?,?) "
            f"ON CONFLICT(agent_id, report_date) DO UPDATE SET {field}={field}+?",
            (str(agent_id), today, amount, amount),
        )


def get_agent_stats(agent_id: str = None, report_date: str = None) -> List[Dict]:
    clauses, params = [], []
    if agent_id:
        clauses.append("agent_id=?"); params.append(str(agent_id))
    if report_date:
        clauses.append("report_date=?"); params.append(report_date)
    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    with _conn() as con:
        rows = con.execute(
            f"SELECT p.*, a.name FROM performance p "
            f"LEFT JOIN agents a ON a.chat_id=p.agent_id "
            f"{where} ORDER BY report_date DESC",
            params,
        ).fetchall()
    return [dict(r) for r in rows]


def get_team_stats_today() -> List[Dict]:
    return get_agent_stats(report_date=date.today().isoformat())

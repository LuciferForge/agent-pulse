"""
db.py — SQLite database layer for Agent Pulse.
WAL mode for concurrent reads. Zero ORM — direct SQL.
"""

import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "data" / "agentpulse.db"


def get_conn() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH), timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=5000")
    return conn


def init_db():
    conn = get_conn()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS owners (
            id TEXT PRIMARY KEY,
            token TEXT UNIQUE NOT NULL,
            email TEXT,
            telegram_chat_id TEXT,
            webhook_url TEXT,
            plan TEXT DEFAULT 'free',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS agents (
            id TEXT PRIMARY KEY,
            owner_id TEXT NOT NULL REFERENCES owners(id),
            name TEXT NOT NULL,
            interval_seconds INTEGER DEFAULT 300,
            grace_seconds INTEGER DEFAULT 600,
            last_ping_at TEXT,
            status TEXT DEFAULT 'new',
            metadata TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS alerts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            agent_id TEXT NOT NULL REFERENCES agents(id),
            alert_type TEXT NOT NULL,
            channel TEXT NOT NULL,
            message TEXT,
            fired_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS pings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            agent_id TEXT NOT NULL REFERENCES agents(id),
            pinged_at TEXT NOT NULL,
            payload TEXT
        );

        CREATE INDEX IF NOT EXISTS idx_agents_owner ON agents(owner_id);
        CREATE INDEX IF NOT EXISTS idx_agents_status ON agents(status);
        CREATE INDEX IF NOT EXISTS idx_pings_agent ON pings(agent_id);
        CREATE INDEX IF NOT EXISTS idx_alerts_agent ON alerts(agent_id);
    """)
    conn.commit()
    conn.close()


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def new_id() -> str:
    return uuid.uuid4().hex[:16]


def new_token() -> str:
    return f"ap_{uuid.uuid4().hex}"


# ─── Owner operations ────────────────────────────────────────────────────────

def create_owner(email: str = None) -> dict:
    conn = get_conn()
    owner = {
        "id": new_id(),
        "token": new_token(),
        "email": email,
        "plan": "free",
        "created_at": now_iso(),
        "updated_at": now_iso(),
    }
    conn.execute(
        "INSERT INTO owners (id, token, email, plan, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?)",
        (owner["id"], owner["token"], owner["email"], owner["plan"], owner["created_at"], owner["updated_at"]),
    )
    conn.commit()
    conn.close()
    return owner


def get_owner_by_token(token: str) -> dict | None:
    conn = get_conn()
    row = conn.execute("SELECT * FROM owners WHERE token = ?", (token,)).fetchone()
    conn.close()
    return dict(row) if row else None


def update_owner_telegram(owner_id: str, chat_id: str):
    conn = get_conn()
    conn.execute(
        "UPDATE owners SET telegram_chat_id = ?, updated_at = ? WHERE id = ?",
        (chat_id, now_iso(), owner_id),
    )
    conn.commit()
    conn.close()


def update_owner_webhook(owner_id: str, url: str):
    conn = get_conn()
    conn.execute(
        "UPDATE owners SET webhook_url = ?, updated_at = ? WHERE id = ?",
        (url, now_iso(), owner_id),
    )
    conn.commit()
    conn.close()


def update_owner_plan(owner_id: str, plan: str):
    conn = get_conn()
    conn.execute(
        "UPDATE owners SET plan = ?, updated_at = ? WHERE id = ?",
        (plan, now_iso(), owner_id),
    )
    conn.commit()
    conn.close()


# ─── Agent operations ─────────────────────────────────────────────────────────

PLAN_LIMITS = {"free": 3, "indie": 20, "team": 9999}


def count_agents(owner_id: str) -> int:
    conn = get_conn()
    row = conn.execute("SELECT COUNT(*) as cnt FROM agents WHERE owner_id = ?", (owner_id,)).fetchone()
    conn.close()
    return row["cnt"]


def create_agent(owner_id: str, name: str, interval: int = 300, grace: int = None) -> dict:
    if grace is None:
        grace = interval * 2
    agent = {
        "id": new_id(),
        "owner_id": owner_id,
        "name": name,
        "interval_seconds": interval,
        "grace_seconds": grace,
        "status": "new",
        "created_at": now_iso(),
        "updated_at": now_iso(),
    }
    conn = get_conn()
    conn.execute(
        """INSERT INTO agents (id, owner_id, name, interval_seconds, grace_seconds, status, created_at, updated_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (agent["id"], agent["owner_id"], agent["name"], agent["interval_seconds"],
         agent["grace_seconds"], agent["status"], agent["created_at"], agent["updated_at"]),
    )
    conn.commit()
    conn.close()
    return agent


def get_agent(agent_id: str) -> dict | None:
    conn = get_conn()
    row = conn.execute("SELECT * FROM agents WHERE id = ?", (agent_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def list_agents(owner_id: str) -> list[dict]:
    conn = get_conn()
    rows = conn.execute("SELECT * FROM agents WHERE owner_id = ? ORDER BY name", (owner_id,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def delete_agent(agent_id: str):
    conn = get_conn()
    conn.execute("DELETE FROM pings WHERE agent_id = ?", (agent_id,))
    conn.execute("DELETE FROM alerts WHERE agent_id = ?", (agent_id,))
    conn.execute("DELETE FROM agents WHERE id = ?", (agent_id,))
    conn.commit()
    conn.close()


def record_ping(agent_id: str, payload: str = None):
    now = now_iso()
    conn = get_conn()
    conn.execute("INSERT INTO pings (agent_id, pinged_at, payload) VALUES (?, ?, ?)",
                 (agent_id, now, payload))
    conn.execute(
        "UPDATE agents SET last_ping_at = ?, status = 'alive', updated_at = ? WHERE id = ?",
        (now, now, agent_id),
    )
    conn.commit()
    conn.close()


def get_overdue_agents() -> list[dict]:
    """Find agents that missed their heartbeat + grace period."""
    conn = get_conn()
    rows = conn.execute("""
        SELECT * FROM agents
        WHERE status IN ('alive', 'new')
        AND last_ping_at IS NOT NULL
        AND (julianday('now') - julianday(last_ping_at)) * 86400 > (interval_seconds + grace_seconds)
    """).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_never_pinged_agents() -> list[dict]:
    """Find agents registered but never pinged, past their first expected ping."""
    conn = get_conn()
    rows = conn.execute("""
        SELECT * FROM agents
        WHERE status = 'new'
        AND last_ping_at IS NULL
        AND (julianday('now') - julianday(created_at)) * 86400 > (interval_seconds + grace_seconds)
    """).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def mark_agent_dead(agent_id: str):
    conn = get_conn()
    conn.execute(
        "UPDATE agents SET status = 'dead', updated_at = ? WHERE id = ?",
        (now_iso(), agent_id),
    )
    conn.commit()
    conn.close()


def record_alert(agent_id: str, alert_type: str, channel: str, message: str):
    conn = get_conn()
    conn.execute(
        "INSERT INTO alerts (agent_id, alert_type, channel, message, fired_at) VALUES (?, ?, ?, ?, ?)",
        (agent_id, alert_type, channel, message, now_iso()),
    )
    conn.commit()
    conn.close()

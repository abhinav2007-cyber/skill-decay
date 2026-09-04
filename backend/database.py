"""
database.py — SQLite schema (§4) + simulated clock (§5).
All tables are created here on first import.
"""

import sqlite3
import os
from contextlib import contextmanager
from datetime import datetime, timezone

DB_PATH = os.path.join(os.path.dirname(__file__), "sda.db")


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH, detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


@contextmanager
def db_conn():
    conn = get_connection()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db():
    """Create all tables if they don't exist yet."""
    with db_conn() as conn:
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS sim_clock (
            id      INTEGER PRIMARY KEY CHECK (id = 1),
            simulated_now TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS quiz_responses (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id     TEXT NOT NULL,
            skill       TEXT NOT NULL,
            sub_topic   TEXT NOT NULL,
            question_id TEXT NOT NULL,
            correct     BOOLEAN NOT NULL,
            timestamp   TEXT NOT NULL,
            cycle_id    TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS sub_topic_state (
            user_id                 TEXT NOT NULL,
            skill                   TEXT NOT NULL,
            sub_topic               TEXT NOT NULL,
            category                TEXT NOT NULL,
            last_used_at            TEXT NOT NULL,
            tracking_mode           TEXT NOT NULL DEFAULT 'cold_start',
            knowledge_probability   REAL,
            observation_count       INTEGER NOT NULL DEFAULT 0,
            decay_score             REAL NOT NULL DEFAULT 0.0,
            recent_accuracy         REAL,
            last_decision_action    TEXT,
            last_decision_reason    TEXT,
            escalated               INTEGER NOT NULL DEFAULT 0,
            updated_at              TEXT NOT NULL,
            PRIMARY KEY (user_id, skill, sub_topic)
        );

        CREATE TABLE IF NOT EXISTS quiz_cycles (
            cycle_id    TEXT PRIMARY KEY,
            user_id     TEXT NOT NULL,
            skill       TEXT NOT NULL,
            sub_topic   TEXT NOT NULL,
            questions   TEXT NOT NULL,
            created_at  TEXT NOT NULL,
            consumed    INTEGER NOT NULL DEFAULT 0
        );
        """)

    _seed_sim_clock()


def _seed_sim_clock():
    """Initialise the simulated clock to 'now' if it has never been set."""
    with db_conn() as conn:
        row = conn.execute("SELECT simulated_now FROM sim_clock WHERE id=1").fetchone()
        if row is None:
            now_iso = datetime.now(timezone.utc).isoformat()
            conn.execute(
                "INSERT INTO sim_clock (id, simulated_now) VALUES (1, ?)", (now_iso,)
            )


# ── Simulated clock helpers (§5) ───────────────────────────────────────────────

def get_simulated_now() -> datetime:
    """Return the current simulated 'now' as a UTC-aware datetime."""
    with db_conn() as conn:
        row = conn.execute("SELECT simulated_now FROM sim_clock WHERE id=1").fetchone()
        return datetime.fromisoformat(row["simulated_now"])


def advance_simulated_time(days: float) -> datetime:
    """Advance the clock by `days` days. Returns the new simulated_now."""
    from datetime import timedelta
    current = get_simulated_now()
    new_now = current + timedelta(days=days)
    new_iso = new_now.isoformat()
    with db_conn() as conn:
        conn.execute("UPDATE sim_clock SET simulated_now=? WHERE id=1", (new_iso,))
    return new_now

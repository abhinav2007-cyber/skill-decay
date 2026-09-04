"""
database.py — SQLite setup, ORM models, session factory, and table creation.
Implements the exact schema from §4 + simulated clock from §5.
"""

import os
from datetime import datetime, timezone
from sqlalchemy import (
    create_engine, Column, Text, Boolean, Float, Integer,
    DateTime, JSON, String, UniqueConstraint
)
from sqlalchemy.orm import declarative_base, sessionmaker, Session
from contextlib import contextmanager

# ── Database location ──────────────────────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "sda.db")
DATABASE_URL = f"sqlite:///{DB_PATH}"

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False},  # needed for SQLite + FastAPI
    echo=False,
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


# ── ORM Models (§4 schema) ─────────────────────────────────────────────────────

class SimClock(Base):
    """Single-row simulated clock. §5: all 'now' reads come from here."""
    __tablename__ = "sim_clock"
    id = Column(Integer, primary_key=True, default=1)
    simulated_now = Column(DateTime, nullable=False)


class QuizResponse(Base):
    """Append-only source of truth for pyBKT. §4: quiz_responses."""
    __tablename__ = "quiz_responses"
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Text, nullable=False, index=True)
    skill = Column(Text, nullable=False)
    sub_topic = Column(Text, nullable=False)
    question_id = Column(Text, nullable=False)
    correct = Column(Boolean, nullable=False)
    timestamp = Column(DateTime, nullable=False)
    cycle_id = Column(Text, nullable=False)


class SubTopicState(Base):
    """One row per (user_id, skill, sub_topic). Upserted after every recalculation. §4."""
    __tablename__ = "sub_topic_state"
    user_id = Column(Text, primary_key=True)
    skill = Column(Text, primary_key=True)
    sub_topic = Column(Text, primary_key=True)
    category = Column(Text, nullable=False)
    last_used_at = Column(DateTime, nullable=True)
    tracking_mode = Column(Text, nullable=False, default="cold_start")
    knowledge_probability = Column(Float, nullable=True)
    observation_count = Column(Integer, nullable=False, default=0)
    decay_score = Column(Float, nullable=False, default=0.0)
    recent_accuracy = Column(Float, nullable=True)
    last_decision_action = Column(Text, nullable=True)
    last_decision_reason = Column(Text, nullable=True)
    escalated = Column(Boolean, nullable=False, default=False)
    updated_at = Column(DateTime, nullable=False)


class QuizCycle(Base):
    """One row per generated quiz. §4: quiz_cycles."""
    __tablename__ = "quiz_cycles"
    cycle_id = Column(Text, primary_key=True)
    user_id = Column(Text, nullable=False, index=True)
    skill = Column(Text, nullable=False)
    sub_topic = Column(Text, nullable=False)
    questions = Column(JSON, nullable=False)   # full questions incl. correct answers (server-side only)
    created_at = Column(DateTime, nullable=False)
    consumed = Column(Boolean, nullable=False, default=False)


# ── Table creation ─────────────────────────────────────────────────────────────

def create_tables():
    """Create all tables if they don't exist."""
    Base.metadata.create_all(bind=engine)


# ── Session helpers ────────────────────────────────────────────────────────────

@contextmanager
def get_db_session() -> Session:
    """Context manager for DB sessions — always commits or rolls back cleanly."""
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def get_db():
    """FastAPI dependency — yields a DB session."""
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


# ── Simulated clock helpers (§5) ───────────────────────────────────────────────

def _default_simulated_now() -> datetime:
    """Initial simulated_now: a fixed reference date for reproducible demos."""
    return datetime(2025, 1, 15, 12, 0, 0)  # deterministic demo start


def get_simulated_now(db: Session) -> datetime:
    """Read the current simulated clock time."""
    row = db.query(SimClock).filter(SimClock.id == 1).first()
    if row is None:
        now = _default_simulated_now()
        db.add(SimClock(id=1, simulated_now=now))
        db.commit()
        return now
    return row.simulated_now


def advance_simulated_clock(db: Session, days: float) -> datetime:
    """
    Move the simulated clock forward by `days`.
    §5 constraint: must NOT touch observation_count or tracking_mode.
    """
    from datetime import timedelta
    row = db.query(SimClock).filter(SimClock.id == 1).first()
    if row is None:
        row = SimClock(id=1, simulated_now=_default_simulated_now())
        db.add(row)
    row.simulated_now = row.simulated_now + timedelta(days=days)
    db.commit()
    db.refresh(row)
    return row.simulated_now


def init_db():
    """Create tables and seed the simulated clock + initial sub-topic states."""
    create_tables()
    # Seed clock and initial states inside a fresh session
    from backend.domain import all_sub_topics, DEMO_USER_ID

    with get_db_session() as db:
        # Seed clock
        if db.query(SimClock).count() == 0:
            now = _default_simulated_now()
            db.add(SimClock(id=1, simulated_now=now))
            db.flush()
        else:
            now = get_simulated_now(db)

        # Seed SubTopicState rows for demo user
        for skill, sub_topic, category in all_sub_topics():
            existing = db.query(SubTopicState).filter_by(
                user_id=DEMO_USER_ID, skill=skill, sub_topic=sub_topic
            ).first()
            if existing is None:
                last_used = now
                db.add(SubTopicState(
                    user_id=DEMO_USER_ID,
                    skill=skill,
                    sub_topic=sub_topic,
                    category=category,
                    last_used_at=last_used,
                    tracking_mode="cold_start",
                    knowledge_probability=None,
                    observation_count=0,
                    decay_score=0.0,
                    recent_accuracy=None,
                    escalated=False,
                    updated_at=now,
                ))

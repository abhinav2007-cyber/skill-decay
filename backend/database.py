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
    connect_args={"check_same_thread": False, "timeout": 30},  # needed for SQLite + FastAPI concurrency
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
    assessment_type = Column(Text, nullable=False, default="standard")  # "standard", "baseline", "targeted_test", "recovery_test"
    source_skill = Column(Text, nullable=True) # Used if this is a cross-topic generated test
    target_subtopic = Column(Text, nullable=True)
    questions = Column(JSON, nullable=False)   # full questions incl. correct answers (server-side only)
    created_at = Column(DateTime, nullable=False)
    consumed = Column(Boolean, nullable=False, default=False)


class Skill(Base):
    """Dynamic skills added by the user."""
    __tablename__ = "skills"
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Text, nullable=False, index=True)
    skill_name = Column(Text, nullable=False)
    created_at = Column(DateTime, nullable=False)
    source = Column(Text, nullable=False, default="user")
    confirmed = Column(Boolean, nullable=False, default=False)


class SkillSubTopic(Base):
    """Dynamic sub-topics for skills."""
    __tablename__ = "skill_subtopics"
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Text, nullable=False, index=True)
    skill_name = Column(Text, nullable=False)
    sub_topic_key = Column(Text, nullable=False)
    label = Column(Text, nullable=False)
    category = Column(Text, nullable=False)
    created_at = Column(DateTime, nullable=False)


class DeletedSkill(Base):
    """Tracks skills deleted by the user (including core skills)."""
    __tablename__ = "deleted_skills"
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Text, nullable=False, index=True)
    skill_name = Column(Text, nullable=False)
    deleted_at = Column(DateTime, nullable=False)


class QuestionBank(Base):
    """Official 50-question question bank table loaded from assessment document."""
    __tablename__ = "question_bank"
    id = Column(Integer, primary_key=True, autoincrement=True)
    question_num = Column(Integer, unique=True, nullable=False)
    subject = Column(Text, nullable=False, index=True)
    sub_topic = Column(Text, nullable=False, index=True)
    category = Column(Text, nullable=False)
    question = Column(Text, nullable=False)
    option_a = Column(Text, nullable=False)
    option_b = Column(Text, nullable=False)
    option_c = Column(Text, nullable=False)
    option_d = Column(Text, nullable=False)
    correct_option = Column(String(5), nullable=False)  # "A", "B", "C", or "D"
    concept_explanation = Column(Text, nullable=False)


class CalendarEvent(Base):
    """
    SDA Calendar & Adaptive Future Timetable Events.
    Stores historical tests/practice as well as generated future adaptive study events.
    """
    __tablename__ = "calendar_events"
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Text, nullable=False, index=True)
    skill = Column(Text, nullable=False)
    sub_topic = Column(Text, nullable=False)
    event_type = Column(Text, nullable=False)  # "TEST" | "PRACTICE" | "REFRESH" | "RECOVERY"
    title = Column(Text, nullable=False)
    description = Column(Text, nullable=True)
    scheduled_date = Column(Text, nullable=False, index=True)  # "YYYY-MM-DD"
    scheduled_time = Column(Text, nullable=False)  # "06:00 PM"
    status = Column(Text, nullable=False, default="UPCOMING")  # "UPCOMING" | "COMPLETED" | "MISSED" | "CANCELLED"
    source = Column(Text, nullable=False, default="SDA")  # "SDA" | "USER"
    decision_action = Column(Text, nullable=True)  # "TEST_NOW", "RECOMMEND", "ESCALATE", "WAIT"
    decision_reason = Column(Text, nullable=True)
    created_at = Column(DateTime, nullable=False)
    completed_at = Column(DateTime, nullable=True)
    related_cycle_id = Column(Text, nullable=True)
    # Context signals at scheduling
    trigger_freshness = Column(Float, nullable=True)
    trigger_mastery = Column(Float, nullable=True)
    trigger_weakness = Column(Float, nullable=True)
    trigger_urgency = Column(Float, nullable=True)



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
    # Create IST timezone (+05:30)
    from datetime import timezone, timedelta
    ist = timezone(timedelta(hours=5, minutes=30))
    return datetime(2025, 1, 15, 12, 0, 0, tzinfo=ist)  # deterministic demo start in IST
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

        # Seed QuestionBank from official 50-question assessment dataset
        from backend.seed_questions import QUESTIONS_50
        for q in QUESTIONS_50:
            existing_q = db.query(QuestionBank).filter_by(question_num=q["question_num"]).first()
            if existing_q is None:
                db.add(QuestionBank(
                    question_num=q["question_num"],
                    subject=q["subject"],
                    sub_topic=q["sub_topic"],
                    category=q["category"],
                    question=q["question"],
                    option_a=q["option_a"],
                    option_b=q["option_b"],
                    option_c=q["option_c"],
                    option_d=q["option_d"],
                    correct_option=q["correct_option"],
                    concept_explanation=q["concept_explanation"],
                ))
            else:
                # Update existing row with official contents
                existing_q.subject = q["subject"]
                existing_q.sub_topic = q["sub_topic"]
                existing_q.category = q["category"]
                existing_q.question = q["question"]
                existing_q.option_a = q["option_a"]
                existing_q.option_b = q["option_b"]
                existing_q.option_c = q["option_c"]
                existing_q.option_d = q["option_d"]
                existing_q.correct_option = q["correct_option"]
                existing_q.concept_explanation = q["concept_explanation"]
        db.flush()


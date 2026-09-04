"""
future_scheduler.py — Adaptive Study Timetable Generator for SDA Calendar.

Integrates:
  - Database (quiz_responses, quiz_cycles, calendar_events, sub_topic_state)
  - Signal Engine (decay_score, freshness, recent_accuracy, pyBKT mastery)
  - Featherless Decision Agent (priority actions & rationale)
  - Adaptive date & learning window scheduler (0-14 days based on urgency)
"""

import logging
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from sqlalchemy.orm import Session

from backend.database import (
    CalendarEvent, QuizResponse, QuizCycle, SubTopicState, get_simulated_now
)
from backend.domain import all_sub_topics, DEMO_USER_ID, get_category
from backend.services.signal_engine import get_signal_bundle
from backend.services.decision_agent import run_decision_agent

logger = logging.getLogger(__name__)

LEARNING_WINDOWS = ["06:00 PM", "02:00 PM", "08:00 AM", "08:00 PM"]


def sync_historical_events(db: Session, user_id: str):
    """
    Sync all completed assessments and past activities from quiz_responses/quiz_cycles
    into the calendar_events table so the Calendar reflects complete ground-truth history.
    """
    cycles = db.query(QuizCycle).filter_by(user_id=user_id).all()
    for c in cycles:
        responses = db.query(QuizResponse).filter_by(user_id=user_id, cycle_id=c.cycle_id).all()
        if not responses:
            continue

        # Check if already synced
        existing = db.query(CalendarEvent).filter_by(
            user_id=user_id, related_cycle_id=c.cycle_id
        ).first()

        total = len(responses)
        correct = sum(1 for r in responses if r.correct)
        accuracy = round((correct / total) * 100) if total > 0 else 0
        latest_time = responses[-1].timestamp if responses else c.created_at

        title = f"{c.skill} — {c.sub_topic.replace('_', ' ').title()} Assessment"
        desc = f"Completed diagnostic test ({correct}/{total} correct, {accuracy}% accuracy)."

        if existing:
            existing.status = "COMPLETED"
            existing.completed_at = latest_time
            existing.title = title
            existing.description = desc
        else:
            event = CalendarEvent(
                user_id=user_id,
                skill=c.skill,
                sub_topic=c.sub_topic,
                event_type="TEST",
                title=title,
                description=desc,
                scheduled_date=latest_time.strftime("%Y-%m-%d"),
                scheduled_time=latest_time.strftime("%I:%M %p"),
                status="COMPLETED",
                source="SDA",
                decision_action="TEST_NOW",
                decision_reason=f"Diagnostic assessment completed with {accuracy}% accuracy.",
                created_at=c.created_at,
                completed_at=latest_time,
                related_cycle_id=c.cycle_id,
            )
            db.add(event)
    db.flush()


def generate_adaptive_timetable(db: Session, user_id: str, recalculate: bool = False) -> List[Dict[str, Any]]:
    """
    Generate or recalculate future timetable based on current Signal Engine & pyBKT states.
    Uses Featherless Decision Agent recommendations to determine action types and reasons,
    then schedules them onto dates prioritized by urgency.
    """
    now = get_simulated_now(db)
    sync_historical_events(db, user_id)

    # 1. Fetch current signal bundle
    signal_bundle = get_signal_bundle(db, user_id)

    # 2. If recalculating, cancel prior upcoming SDA events that are now obsolete
    if recalculate:
        db.query(CalendarEvent).filter(
            CalendarEvent.user_id == user_id,
            CalendarEvent.status == "UPCOMING",
            CalendarEvent.source == "SDA",
        ).update({"status": "CANCELLED"})
        db.flush()

    # 3. Call Featherless Decision Agent to evaluate priority actions per sub-topic
    decisions = []
    try:
        decisions = run_decision_agent(signal_bundle, user_id)
    except Exception as exc:
        logger.error("Decision Agent call failed during timetable generation: %s", exc)

    decision_map = {d["subtopic"]: d for d in decisions if "subtopic" in d}

    # 4. Analyze each sub-topic's multi-dimensional signals
    candidates = []
    for skill, subtopics in signal_bundle.items():
        for sub_topic, data in subtopics.items():
            if "error" in data:
                continue

            kt = data.get("knowledge_tracking", {})
            decay_info = data.get("decay", {})
            quiz_info = data.get("quiz", {})
            escalated = data.get("escalated", False)

            mastery_prob = kt.get("knowledge_probability")
            decay = decay_info.get("decay_score", 0.0)
            freshness = max(0.0, round(1.0 - decay, 2))
            mastery = mastery_prob if mastery_prob is not None else freshness
            weakness = max(0.0, round(1.0 - mastery, 2))
            days_since = decay_info.get("days_since_last_use", 0.0)

            # Check decision from agent
            dec = decision_map.get(sub_topic, {})
            agent_action = dec.get("action", "WAIT")
            agent_reason = dec.get("reason", "")

            # Determine intervention type based on section 11 rules:
            # A. High decay + low mastery -> TEST
            # B. High decay + high mastery -> REFRESH or TEST
            # C. Low mastery + acceptable freshness -> PRACTICE
            # D. High weakness -> targeted PRACTICE / RECOVERY
            # E. Healthy skill + low urgency -> WAIT
            event_type = None
            urgency_level = 0  # 3=critical, 2=high, 1=moderate

            if escalated or agent_action == "ESCALATE":
                event_type = "RECOVERY"
                urgency_level = 3
                if not agent_reason:
                    agent_reason = f"Escalated priority: Critical decay ({round(decay*100)}%) requires immediate recovery."
            elif agent_action == "TEST_NOW" or (decay >= 0.65 and weakness >= 0.5):
                event_type = "TEST"
                urgency_level = 3 if decay >= 0.75 else 2
                if not agent_reason:
                    agent_reason = f"High decay ({round(decay*100)}%) and weakness ({round(weakness*100)}%) require verification."
            elif agent_action == "RECOMMEND" or (weakness >= 0.55):
                event_type = "PRACTICE"
                urgency_level = 2
                if not agent_reason:
                    agent_reason = f"Moderate weakness ({round(weakness*100)}%) detected; practice recommended."
            elif decay >= 0.50:
                event_type = "REFRESH"
                urgency_level = 1
                if not agent_reason:
                    agent_reason = f"Freshness is declining ({round(freshness*100)}%); quick refresh advised."

            if event_type:
                candidates.append({
                    "skill": skill,
                    "sub_topic": sub_topic,
                    "event_type": event_type,
                    "urgency_level": urgency_level,
                    "decay": decay,
                    "freshness": freshness,
                    "mastery": mastery,
                    "weakness": weakness,
                    "days_since": days_since,
                    "action": agent_action,
                    "reason": agent_reason,
                })

    # Sort candidates by urgency descending
    candidates.sort(key=lambda x: (x["urgency_level"], x["decay"], x["weakness"]), reverse=True)

    # 5. Place on calendar spread across dates (0 to 14 days) avoiding collisions
    scheduled_events = []
    day_offset_tracker = 1  # start tomorrow from simulated now

    for cand in candidates:
        # Determine day offset based on urgency:
        # Very high (urgency 3): +1 to +3 days
        # High (urgency 2): +3 to +6 days
        # Moderate (urgency 1): +7 to +12 days
        if cand["urgency_level"] == 3:
            planned_day = now + timedelta(days=max(1, day_offset_tracker))
            day_offset_tracker += 2
        elif cand["urgency_level"] == 2:
            planned_day = now + timedelta(days=max(3, day_offset_tracker))
            day_offset_tracker += 2
        else:
            planned_day = now + timedelta(days=max(6, day_offset_tracker))
            day_offset_tracker += 3

        scheduled_date_str = planned_day.strftime("%Y-%m-%d")

        # Check for existing upcoming duplicate
        existing = db.query(CalendarEvent).filter_by(
            user_id=user_id,
            skill=cand["skill"],
            sub_topic=cand["sub_topic"],
            event_type=cand["event_type"],
            status="UPCOMING"
        ).first()

        if existing:
            # Already planned, update triggers
            existing.decision_reason = cand["reason"]
            existing.trigger_freshness = cand["freshness"]
            existing.trigger_mastery = cand["mastery"]
            existing.trigger_weakness = cand["weakness"]
            scheduled_events.append(existing)
            continue

        # Choose time window (default 6:00 PM)
        time_slot = LEARNING_WINDOWS[0]
        # Check if that slot is taken on this date
        slot_taken = db.query(CalendarEvent).filter_by(
            user_id=user_id,
            scheduled_date=scheduled_date_str,
            scheduled_time=time_slot,
            status="UPCOMING"
        ).first()
        if slot_taken:
            time_slot = LEARNING_WINDOWS[1]

        sub_title = cand["sub_topic"].replace("_", " ").title()
        title = f"{cand['skill']} — {sub_title} {cand['event_type'].title()}"

        new_event = CalendarEvent(
            user_id=user_id,
            skill=cand["skill"],
            sub_topic=cand["sub_topic"],
            event_type=cand["event_type"],
            title=title,
            description=f"{cand['event_type'].title()} session scheduled by SDA. {cand['reason']}",
            scheduled_date=scheduled_date_str,
            scheduled_time=time_slot,
            status="UPCOMING",
            source="SDA",
            decision_action=cand["action"],
            decision_reason=cand["reason"],
            created_at=now,
            trigger_freshness=cand["freshness"],
            trigger_mastery=cand["mastery"],
            trigger_weakness=cand["weakness"],
            trigger_urgency=cand["decay"],
        )
        db.add(new_event)
        scheduled_events.append(new_event)

    db.commit()
    return get_calendar_bundle(db, user_id)


def get_calendar_bundle(db: Session, user_id: str) -> Dict[str, Any]:
    """
    Returns full calendar package:
      - All events (history + upcoming)
      - Summary metrics (Next 7 days tests, practice, high risk, estimated minutes)
      - Practice History list
      - Upcoming Plan list
    """
    sync_historical_events(db, user_id)
    now = get_simulated_now(db)
    now_str = now.strftime("%Y-%m-%d")

    events = db.query(CalendarEvent).filter_by(user_id=user_id).order_by(
        CalendarEvent.scheduled_date.asc(), CalendarEvent.scheduled_time.asc()
    ).all()

    history = []
    upcoming = []
    all_events_payload = []

    # 7-day cutoff for summary
    in_7_days = (now + timedelta(days=7)).strftime("%Y-%m-%d")
    upcoming_tests_7d = 0
    upcoming_practice_7d = 0
    high_risk_count = 0
    est_minutes = 0

    for ev in events:
        # Check if an upcoming event is in the past -> mark MISSED
        if ev.status == "UPCOMING" and ev.scheduled_date < now_str:
            ev.status = "MISSED"
            db.flush()

        item = {
            "id": ev.id,
            "skill": ev.skill,
            "sub_topic": ev.sub_topic,
            "event_type": ev.event_type,
            "title": ev.title,
            "description": ev.description,
            "scheduled_date": ev.scheduled_date,
            "scheduled_time": ev.scheduled_time,
            "status": ev.status,
            "source": ev.source,
            "decision_action": ev.decision_action,
            "decision_reason": ev.decision_reason,
            "created_at": ev.created_at.isoformat() if ev.created_at else None,
            "completed_at": ev.completed_at.isoformat() if ev.completed_at else None,
            "related_cycle_id": ev.related_cycle_id,
            "trigger_freshness": ev.trigger_freshness,
            "trigger_mastery": ev.trigger_mastery,
            "trigger_weakness": ev.trigger_weakness,
            "trigger_urgency": ev.trigger_urgency,
        }
        all_events_payload.append(item)

        if ev.status in ("COMPLETED", "MISSED"):
            history.append(item)
        elif ev.status == "UPCOMING":
            upcoming.append(item)
            if now_str <= ev.scheduled_date <= in_7_days:
                if ev.event_type == "TEST":
                    upcoming_tests_7d += 1
                    est_minutes += 15
                else:
                    upcoming_practice_7d += 1
                    est_minutes += 20
                if (ev.trigger_urgency or 0) >= 0.7 or ev.event_type == "RECOVERY":
                    high_risk_count += 1

    # Sort history descending (newest first)
    history.sort(key=lambda x: (x["scheduled_date"], x["scheduled_time"]), reverse=True)

    return {
        "user_id": user_id,
        "simulated_now": now.isoformat(),
        "summary": {
            "upcoming_tests": upcoming_tests_7d,
            "practice_sessions": upcoming_practice_7d,
            "high_risk_skills": high_risk_count,
            "estimated_learning_minutes": est_minutes if est_minutes > 0 else 35,
        },
        "all_events": all_events_payload,
        "history": history,
        "upcoming_plan": upcoming,
    }

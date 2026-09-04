"""
main.py — FastAPI application with all §13 endpoints.

Endpoints:
  GET  /skills                  — all 10 sub-topics with current signal bundles
  POST /cycle                   — LangGraph invocation 1
  POST /answer                  — LangGraph invocation 2
  POST /advance_time            — move simulated clock (§5)
  GET  /strength-report         — §10.2 stats + §10.3 AI summary
  GET  /debug/{user_id}/{skill}/{sub_topic} — dev inspection

Single hardcoded demo user: user_id = "demo_user"
No auth. No multiple databases.
"""

import logging
import os
from dotenv import load_dotenv
load_dotenv()
from datetime import datetime
from typing import Optional

from fastapi import FastAPI, HTTPException, Depends
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

# Setup logging before imports that use it
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s — %(message)s",
)
logger = logging.getLogger(__name__)

from backend.database import (
    get_db, init_db, get_simulated_now, advance_simulated_clock,
    SubTopicState, QuizResponse, QuizCycle
)
from backend.domain import DEMO_USER_ID
from backend.services.signal_engine import get_signal_bundle, recalculate_and_persist_state
from backend.services.grading import GradingError
from backend.graph.feedback_engine import run_cycle, run_answer
from backend.services.strength_report import get_strength_report, generate_ai_summary

# ── App setup ─────────────────────────────────────────────────────────────────

app = FastAPI(
    title="Skill Decay Alerts (SDA)",
    description="Agentic skill decay detection and remediation system",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],   # dev-only; restrict in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def startup():
    """Initialize DB tables and seed initial state."""
    logger.info("SDA startup: initializing database...")
    init_db()
    logger.info("SDA startup: ready.")


# ── Request / Response models ─────────────────────────────────────────────────

class AdvanceTimeRequest(BaseModel):
    days: float = Field(..., gt=0, description="Number of simulated days to advance")


class AnswerRequest(BaseModel):
    subtopic: str
    selected_option: str
    question_id: str
    cycle_id: str


class CycleRequest(BaseModel):
    subtopic: Optional[str] = None


# ── Endpoints (§13) ───────────────────────────────────────────────────────────

class QuizSubmitRequest(BaseModel):
    subject: str
    sub_topic: str
    cycle_id: str
    answers: list[dict]  # [{"question_id": "...", "selected_option": "..."}]


@app.get("/skills")
def get_skills_endpoint(db: Session = Depends(get_db)):
    """
    §13: GET /skills — all 10 sub-topics with their current signal bundles.
    Calls signal_engine.get_signal_bundle for demo_user.
    """
    try:
        bundle = get_signal_bundle(db, DEMO_USER_ID)
        return bundle
    except Exception as exc:
        logger.error("GET /skills error: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))


@app.get("/test/catalog")
def get_test_catalog(db: Session = Depends(get_db)):
    """
    Returns subjects, sub-topics, question counts and metadata directly from the database.
    """
    from backend.database import QuestionBank
    from backend.domain import all_sub_topics

    catalog = []
    for skill, sub_topic, category in all_sub_topics():
        count = db.query(QuestionBank).filter_by(subject=skill, sub_topic=sub_topic).count()
        catalog.append({
            "subject": skill,
            "sub_topic": sub_topic,
            "category": category,
            "total_questions": count,
        })
    return {
        "catalog": catalog,
        "total_bank_questions": db.query(QuestionBank).count()
    }


@app.get("/test/questions")
def get_test_questions(subject: str, subtopic: str, db: Session = Depends(get_db)):
    """
    Fetch questions for active test page directly from QuestionBank database table.
    Creates a QuizCycle and returns safe questions (correct answers kept strictly server-side).
    """
    import uuid
    from backend.database import QuestionBank
    from datetime import datetime

    cycle_id = str(uuid.uuid4())
    
    # 1. Query database QuestionBank for exact matches
    db_questions = (
        db.query(QuestionBank)
        .filter_by(subject=subject, sub_topic=subtopic)
        .order_by(QuestionBank.question_num)
        .all()
    )

    # Fallback by subject match if needed
    if not db_questions:
        db_questions = (
            db.query(QuestionBank)
            .filter_by(subject=subject)
            .order_by(QuestionBank.question_num)
            .all()
        )
    if not db_questions:
        db_questions = db.query(QuestionBank).order_by(QuestionBank.question_num).limit(5).all()

    questions_full = []
    safe_questions = []
    for q in db_questions:
        q_id = f"qb_{q.question_num}"
        # Server-side full data including correct answers
        q_full = {
            "question_id": q_id,
            "question_num": q.question_num,
            "question": q.question,
            "options": [q.option_a, q.option_b, q.option_c, q.option_d],
            "correct_answer": q.correct_option,
            "explanation": q.concept_explanation,
        }
        questions_full.append(q_full)

        # Frontend safe data without correct answer or concept explanation
        safe_questions.append({
            "question_id": q_id,
            "question_num": q.question_num,
            "question": q.question,
            "options": [q.option_a, q.option_b, q.option_c, q.option_d],
        })

    now = get_simulated_now(db)
    cycle = QuizCycle(
        cycle_id=cycle_id,
        user_id=DEMO_USER_ID,
        skill=subject,
        sub_topic=subtopic,
        questions=questions_full,
        created_at=now,
        consumed=False
    )
    db.add(cycle)
    db.commit()

    return {
        "cycle_id": cycle_id,
        "subject": subject,
        "sub_topic": subtopic,
        "total_questions": len(safe_questions),
        "questions": safe_questions
    }



@app.post("/test/submit")
def post_submit_test(req: QuizSubmitRequest, db: Session = Depends(get_db)):
    """
    Submit full test, grade all questions, update state & run Featherless agent.
    Delegates to run_full_test_submission.
    """
    from backend.graph.feedback_engine import run_full_test_submission
    return run_full_test_submission(
        db=db,
        user_id=DEMO_USER_ID,
        subject=req.subject,
        sub_topic=req.sub_topic,
        cycle_id=req.cycle_id,
        answers=req.answers
    )



@app.post("/cycle")
def post_cycle_endpoint(request: CycleRequest = None, db: Session = Depends(get_db)):
    """
    §13: POST /cycle — Invocation 1 (decide + act).
    Optional body: {"subtopic": "syntax_and_core_libraries"} to target a specific sub-topic.
    """
    subtopic = request.subtopic if request else None
    try:
        result = run_cycle(db, user_id=DEMO_USER_ID)
        return result
    except Exception as exc:
        logger.error("POST /cycle error: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))


@app.post("/answer")
def post_answer_endpoint(request: AnswerRequest, db: Session = Depends(get_db)):
    """
    §13: POST /answer — Invocation 2 (grade + decide + act).
    Accepts user's quiz response, validates cycle_id, grades answer,
    appends to quiz_responses, recalculates pyBKT/signals, runs Decision Agent + Action Layer.
    """
    try:
        result = run_answer(
            db=db,
            user_id=DEMO_USER_ID,
            sub_topic=request.subtopic,
            question_id=request.question_id,
            selected_option=request.selected_option,
            cycle_id=request.cycle_id,
        )
        return result
    except GradingError as exc:
        logger.warning("POST /answer validation error: %s", exc)
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        logger.error("POST /answer error: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))


@app.post("/advance_time")
def post_advance_time_endpoint(request: AdvanceTimeRequest, db: Session = Depends(get_db)):
    """
    §13: POST /advance_time — advance simulated clock by `days` days.
    §5 constraint: updates simulated_now, re-evaluates usage decay scores across all 10 sub-topics.
    Does NOT touch observation_count or tracking_mode.
    """
    try:
        new_now = advance_simulated_clock(db, request.days)

        # Re-evaluate signals for all sub-topics with the new simulated time
        states = db.query(SubTopicState).filter_by(user_id=DEMO_USER_ID).all()
        updated = []
        for s in states:
            recalculate_and_persist_state(db, DEMO_USER_ID, s.skill, s.sub_topic, s.category)
            updated.append(s.sub_topic)

        return {
            "status": "ok",
            "days_advanced": request.days,
            "new_simulated_now": new_now.isoformat(),
            "updated_decay_scores": updated,
        }

    except Exception as exc:
        logger.error("POST /advance_time error: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))


@app.get("/strength-report")
def get_strength_report_endpoint(force: bool = False, db: Session = Depends(get_db)):
    """
    §13: GET /strength-report — §10.2 stats + §10.3 AI summary.
    Accepts ?force=true to explicitly refresh AI summary.
    """
    try:
        stats = get_strength_report(db, DEMO_USER_ID)
        ai_summary = generate_ai_summary(stats, force=force)
        return {
            "user_id": DEMO_USER_ID,
            "stats": stats,
            "ai_summary": ai_summary,
        }
    except Exception as exc:
        logger.error("GET /strength-report error: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))


@app.get("/test/history")
def get_test_history_endpoint(db: Session = Depends(get_db)):
    """
    Returns all submitted test reports with timestamps (date and time),
    scores, accuracy, subject/sub-topic, question details, and knowledge updates.
    """
    try:
        from backend.database import QuizCycle, QuizResponse, SubTopicState

        # Fetch all completed quiz cycles
        cycles = (
            db.query(QuizCycle)
            .filter_by(user_id=DEMO_USER_ID)
            .order_by(QuizCycle.created_at.desc())
            .all()
        )

        test_reports = []
        for c in cycles:
            # Query all graded responses for this cycle
            responses = (
                db.query(QuizResponse)
                .filter_by(user_id=DEMO_USER_ID, cycle_id=c.cycle_id)
                .order_by(QuizResponse.id.asc())
                .all()
            )

            # Only include cycles that have recorded assessment responses
            if not responses:
                continue

            total_q = len(responses)
            correct_count = sum(1 for r in responses if r.correct)
            accuracy = round((correct_count / total_q) * 100) if total_q > 0 else 0

            # Latest subtopic state for context
            st_state = (
                db.query(SubTopicState)
                .filter_by(user_id=DEMO_USER_ID, skill=c.skill, sub_topic=c.sub_topic)
                .first()
            )

            # Format timestamps
            dt = responses[-1].timestamp if responses else c.created_at
            formatted_date = dt.strftime("%b %d, %Y")
            formatted_time = dt.strftime("%I:%M %p")
            iso_timestamp = dt.isoformat()

            test_reports.append({
                "cycle_id": c.cycle_id,
                "subject": c.skill,
                "sub_topic": c.sub_topic,
                "date": formatted_date,
                "time": formatted_time,
                "timestamp": iso_timestamp,
                "total_questions": total_q,
                "correct_count": correct_count,
                "incorrect_count": total_q - correct_count,
                "accuracy_pct": accuracy,
                "passed": accuracy >= 60,
                "mastery_mode": st_state.tracking_mode if st_state else "cold_start",
                "knowledge_probability": st_state.knowledge_probability if st_state else None,
                "decay_score": st_state.decay_score if st_state else 0.0,
                "questions_breakdown": [
                    {
                        "question_id": r.question_id,
                        "correct": r.correct,
                    }
                    for r in responses
                ]
            })

        return {
            "user_id": DEMO_USER_ID,
            "total_tests_taken": len(test_reports),
            "reports": test_reports
        }
    except Exception as exc:
        logger.error("GET /test/history error: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))


# ── Calendar & Adaptive Timetable Endpoints ─────────────────────────────────────

@app.get("/calendar")
def get_calendar_endpoint(db: Session = Depends(get_db)):
    """
    GET /calendar — Returns full calendar bundle: historical + upcoming events,
    7-day summary metrics, practice history, and upcoming plan.
    """
    try:
        from backend.services.future_scheduler import get_calendar_bundle
        return get_calendar_bundle(db, DEMO_USER_ID)
    except Exception as exc:
        logger.error("GET /calendar error: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))


@app.get("/calendar/history")
def get_calendar_history_endpoint(db: Session = Depends(get_db)):
    """
    GET /calendar/history — Returns completed and missed events.
    """
    try:
        from backend.services.future_scheduler import get_calendar_bundle
        bundle = get_calendar_bundle(db, DEMO_USER_ID)
        return {"history": bundle["history"]}
    except Exception as exc:
        logger.error("GET /calendar/history error: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))


@app.get("/calendar/upcoming")
def get_calendar_upcoming_endpoint(db: Session = Depends(get_db)):
    """
    GET /calendar/upcoming — Returns future scheduled events.
    """
    try:
        from backend.services.future_scheduler import get_calendar_bundle
        bundle = get_calendar_bundle(db, DEMO_USER_ID)
        return {"upcoming_plan": bundle["upcoming_plan"]}
    except Exception as exc:
        logger.error("GET /calendar/upcoming error: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))


@app.post("/calendar/generate-plan")
def post_generate_plan_endpoint(db: Session = Depends(get_db)):
    """
    POST /calendar/generate-plan — Generates future timetable from current signals.
    """
    try:
        from backend.services.future_scheduler import generate_adaptive_timetable
        return generate_adaptive_timetable(db, DEMO_USER_ID, recalculate=False)
    except Exception as exc:
        logger.error("POST /calendar/generate-plan error: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))


@app.post("/calendar/recalculate")
def post_recalculate_plan_endpoint(db: Session = Depends(get_db)):
    """
    POST /calendar/recalculate — Recalculates future timetable and removes obsolete plans.
    """
    try:
        from backend.services.future_scheduler import generate_adaptive_timetable
        return generate_adaptive_timetable(db, DEMO_USER_ID, recalculate=True)
    except Exception as exc:
        logger.error("POST /calendar/recalculate error: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))


@app.post("/calendar/events/{event_id}/complete")
def post_complete_event_endpoint(event_id: int, db: Session = Depends(get_db)):
    """
    POST /calendar/events/{id}/complete — Marks event completed and records timestamp.
    """
    try:
        from backend.database import CalendarEvent, get_simulated_now
        ev = db.query(CalendarEvent).filter_by(id=event_id, user_id=DEMO_USER_ID).first()
        if not ev:
            raise HTTPException(status_code=404, detail="Calendar event not found")
        ev.status = "COMPLETED"
        ev.completed_at = get_simulated_now(db)
        db.commit()
        return {"status": "ok", "event_id": event_id, "state": "COMPLETED"}
    except Exception as exc:
        logger.error("POST /calendar/events/complete error: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))


@app.get("/calendar/events/{event_id}")
def get_calendar_event_endpoint(event_id: int, db: Session = Depends(get_db)):
    """
    GET /calendar/events/{id} — Returns event details.
    """
    try:
        from backend.database import CalendarEvent
        ev = db.query(CalendarEvent).filter_by(id=event_id, user_id=DEMO_USER_ID).first()
        if not ev:
            raise HTTPException(status_code=404, detail="Calendar event not found")
        return {
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
    except Exception as exc:
        logger.error("GET /calendar/events/{id} error: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))


@app.post("/calendar/events/{event_id}/start-test")
def post_start_test_for_event(event_id: int, db: Session = Depends(get_db)):
    """
    POST /calendar/events/{id}/start-test — Activates/links a test cycle to a scheduled test event.
    """
    try:
        from backend.database import CalendarEvent
        ev = db.query(CalendarEvent).filter_by(id=event_id, user_id=DEMO_USER_ID).first()
        if not ev:
            raise HTTPException(status_code=404, detail="Calendar event not found")
        # Load questions for this subtopic
        res = get_test_questions(subject=ev.skill, subtopic=ev.sub_topic, db=db)
        ev.related_cycle_id = res["cycle_id"]
        db.commit()
        return res
    except Exception as exc:
        logger.error("POST /calendar/events/start-test error: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))




# ── Add New Skill Endpoints ───────────────────────────────────────────────────

class SkillAnalyzeRequest(BaseModel):
    skill_name: str


class AddSkillSubTopic(BaseModel):
    key: str
    label: str
    category: str  # "procedural" | "conceptual"


class AddSkillRequest(BaseModel):
    skill: str         # normalized skill name
    sub_topics: list[AddSkillSubTopic]


@app.post("/skills/analyze")
def post_analyze_skill(request: SkillAnalyzeRequest, db: Session = Depends(get_db)):
    """
    POST /skills/analyze — Call Featherless AI to analyze a user-entered skill name.
    Returns suggested sub-topics, categories, and assessment areas.
    DOES NOT write anything to the database — purely analytical.
    """
    try:
        from backend.services.skill_analyzer import analyze_skill
        skill_name = (request.skill_name or "").strip()
        if not skill_name:
            raise HTTPException(status_code=400, detail="skill_name must not be empty")
        if len(skill_name) > 120:
            raise HTTPException(status_code=400, detail="skill_name too long (max 120 chars)")

        result = analyze_skill(skill_name)
        return result

    except HTTPException:
        raise
    except Exception as exc:
        logger.error("POST /skills/analyze error: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))


@app.post("/skills/add")
def post_add_skill(request: AddSkillRequest, db: Session = Depends(get_db)):
    """
    POST /skills/add — Save a confirmed new skill and its sub-topics to the database.

    Creates SubTopicState rows for each sub-topic with cold_start tracking mode.
    The skill immediately enters the SDA pipeline (Signal Engine, pyBKT, Decision Agent).

    Returns HTTP 409 if the skill already exists for the user.
    """
    try:
        skill = (request.skill or "").strip()
        if not skill:
            raise HTTPException(status_code=400, detail="skill name must not be empty")
        if not request.sub_topics:
            raise HTTPException(status_code=400, detail="At least one sub-topic is required")

        # ── Duplicate check: is there already ANY state row for this skill? ──
        existing = (
            db.query(SubTopicState)
            .filter_by(user_id=DEMO_USER_ID, skill=skill)
            .first()
        )
        if existing:
            raise HTTPException(
                status_code=409,
                detail=f"Skill '{skill}' already exists. Remove it first or choose a different name."
            )

        now = get_simulated_now(db)
        
        from backend.database import Skill, SkillSubTopic
        
        # 1. Add to Skills
        new_skill = Skill(
            user_id=DEMO_USER_ID,
            skill_name=skill,
            created_at=now,
            confirmed=True
        )
        db.add(new_skill)
        
        added_sub_topics = []

        for st in request.sub_topics:
            key = (st.key or "").strip().lower().replace(" ", "_")
            label = (st.label or "").strip()
            category = st.category.lower() if st.category.lower() in ("procedural", "conceptual") else "conceptual"

            if not key or not label:
                continue

            # Check for duplicate sub-topic key within this skill
            existing_st = db.query(SubTopicState).filter_by(
                user_id=DEMO_USER_ID, skill=skill, sub_topic=key
            ).first()
            if existing_st:
                continue
                
            # 2. Add to SkillSubTopic
            db.add(SkillSubTopic(
                user_id=DEMO_USER_ID,
                skill_name=skill,
                sub_topic_key=key,
                label=label,
                category=category,
                created_at=now
            ))

            db.add(SubTopicState(
                user_id=DEMO_USER_ID,
                skill=skill,
                sub_topic=key,
                category=category,
                last_used_at=now,          # treat "just added" as fresh
                tracking_mode="cold_start",
                knowledge_probability=None,
                observation_count=0,
                decay_score=0.0,
                recent_accuracy=None,
                last_decision_action=None,
                last_decision_reason=None,
                escalated=False,
                updated_at=now,
            ))
            added_sub_topics.append({"key": key, "label": label, "category": category})

        if not added_sub_topics:
            raise HTTPException(status_code=400, detail="No valid sub-topics to add")

        db.commit()
        logger.info("[add_skill] Added skill '%s' with %d sub-topics for %s",
                    skill, len(added_sub_topics), DEMO_USER_ID)

        return {
            "status": "ok",
            "skill": skill,
            "user_id": DEMO_USER_ID,
            "sub_topics_added": added_sub_topics,
            "tracking_mode": "cold_start",
            "message": f"Skill '{skill}' added successfully with {len(added_sub_topics)} sub-topics. It is now tracked by the SDA Signal Engine.",
        }

    except HTTPException:
        raise
    except Exception as exc:
        logger.error("POST /skills/add error: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))


@app.delete("/skills/{skill_name}")
def delete_skill_endpoint(skill_name: str, db: Session = Depends(get_db)):
    """
    DELETE /skills/{skill_name} — Delete a skill (core or custom) and all associated data.
    """
    try:
        from sqlalchemy import func
        from backend.database import Skill, SkillSubTopic, SubTopicState, QuizResponse, QuizCycle, DeletedSkill, get_simulated_now
        
        normalized = (skill_name or "").strip()
        now = get_simulated_now(db)

        # 1. Record in DeletedSkill so even core hardcoded skills stay deleted
        already_deleted = db.query(DeletedSkill).filter(
            DeletedSkill.user_id == DEMO_USER_ID,
            func.lower(DeletedSkill.skill_name) == normalized.lower()
        ).first()
        if not already_deleted:
            db.add(DeletedSkill(user_id=DEMO_USER_ID, skill_name=normalized, deleted_at=now))
        
        # 2. Delete from Skill table
        db.query(Skill).filter(
            Skill.user_id == DEMO_USER_ID,
            func.lower(Skill.skill_name) == normalized.lower()
        ).delete(synchronize_session=False)

        # 3. Delete from SkillSubTopic table
        db.query(SkillSubTopic).filter(
            SkillSubTopic.user_id == DEMO_USER_ID,
            func.lower(SkillSubTopic.skill_name) == normalized.lower()
        ).delete(synchronize_session=False)

        # 4. Delete from SubTopicState table
        db.query(SubTopicState).filter(
            SubTopicState.user_id == DEMO_USER_ID,
            func.lower(SubTopicState.skill) == normalized.lower()
        ).delete(synchronize_session=False)

        # 5. Delete from QuizResponse & QuizCycle
        db.query(QuizResponse).filter(
            QuizResponse.user_id == DEMO_USER_ID,
            func.lower(QuizResponse.skill) == normalized.lower()
        ).delete(synchronize_session=False)

        db.query(QuizCycle).filter(
            QuizCycle.user_id == DEMO_USER_ID,
            func.lower(QuizCycle.skill) == normalized.lower()
        ).delete(synchronize_session=False)
        
        db.commit()
        logger.info("[delete_skill] Deleted skill '%s' for %s", normalized, DEMO_USER_ID)
        return {"status": "ok", "message": f"Skill '{normalized}' deleted successfully."}
    except Exception as exc:
        db.rollback()
        logger.error("DELETE /skills/%s error: %s", skill_name, exc)
        raise HTTPException(status_code=500, detail=str(exc))


@app.post("/skills/baseline/generate")
def post_generate_baseline(request: AddSkillRequest, db: Session = Depends(get_db)):
    """
    POST /skills/baseline/generate
    Generates 5-6 baseline questions using Featherless AI and creates a QuizCycle.
    """
    try:
        from backend.services.skill_analyzer import generate_baseline_assessment
        import uuid
        
        skill = (request.skill or "").strip()
        if not skill or not request.sub_topics:
            raise HTTPException(status_code=400, detail="Skill and sub_topics required")
            
        # Call AI to generate baseline test
        result = generate_baseline_assessment(skill, [st.dict() for st in request.sub_topics], 6)
        questions = result.get("questions", [])
        
        if not questions:
            raise HTTPException(status_code=500, detail="Failed to generate baseline assessment")
            
        cycle_id = str(uuid.uuid4())
        now = get_simulated_now(db)
        
        # Save QuizCycle
        cycle = QuizCycle(
            cycle_id=cycle_id,
            user_id=DEMO_USER_ID,
            skill=skill,
            sub_topic="mixed_baseline", # multiple sub-topics in one test
            assessment_type="baseline",
            questions=questions,
            created_at=now,
            consumed=False
        )
        db.add(cycle)
        db.commit()
        
        # Return safe questions
        safe_questions = [
            {
                "question_id": q["question_id"],
                "question_num": q["question_num"],
                "subject": q["subject"],
                "sub_topic": q["sub_topic"],
                "question": q["question"],
                "options": q["options"]
            }
            for q in questions
        ]
        
        return {
            "cycle_id": cycle_id,
            "subject": skill,
            "sub_topic": "mixed_baseline",
            "assessment_type": "baseline",
            "total_questions": len(safe_questions),
            "questions": safe_questions
        }
        
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("POST /skills/add error: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))


@app.get("/debug/{user_id}/{skill}/{sub_topic}")

def get_debug(
    user_id: str,
    skill: str,
    sub_topic: str,
    db: Session = Depends(get_db),
):
    """
    §13: GET /debug/{user_id}/{skill}/{sub_topic} — dev-only inspection.
    Returns observation count, recent responses, tracking mode, knowledge estimate,
    decay score, usage signal, recent accuracy, escalated flag, full bundle.
    """
    try:
        state = db.query(SubTopicState).filter_by(
            user_id=user_id, skill=skill, sub_topic=sub_topic
        ).first()

        if state is None:
            raise HTTPException(
                status_code=404,
                detail=f"No state found for {user_id}/{skill}/{sub_topic}"
            )

        # Recent responses
        recent_responses = (
            db.query(QuizResponse)
            .filter_by(user_id=user_id, skill=skill, sub_topic=sub_topic)
            .order_by(QuizResponse.timestamp.desc())
            .limit(10)
            .all()
        )
        responses_data = [
            {
                "question_id": r.question_id,
                "correct": r.correct,
                "timestamp": r.timestamp.isoformat(),
                "cycle_id": r.cycle_id,
            }
            for r in recent_responses
        ]

        # Build full signal bundle for this single sub-topic
        from backend.services.signal_engine import _build_bundle
        from backend.database import get_simulated_now
        now = get_simulated_now(db)
        bundle = _build_bundle(state, now)

        return {
            "user_id": user_id,
            "skill": skill,
            "sub_topic": sub_topic,
            "tracking_mode": state.tracking_mode,
            "observation_count": state.observation_count,
            "knowledge_probability": state.knowledge_probability,
            "decay_score": state.decay_score,
            "recent_accuracy": state.recent_accuracy,
            "escalated": state.escalated,
            "last_decision_action": state.last_decision_action,
            "last_decision_reason": state.last_decision_reason,
            "last_used_at": state.last_used_at.isoformat() if state.last_used_at else None,
            "updated_at": state.updated_at.isoformat(),
            "recent_responses": responses_data,
            "full_bundle": bundle,
        }

    except HTTPException:
        raise
    except Exception as exc:
        logger.error("GET /debug error: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.main:app", host="0.0.0.0", port=8000, reload=True)

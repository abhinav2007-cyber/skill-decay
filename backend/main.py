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


@app.post("/cycle")
def post_cycle_endpoint(request: CycleRequest = None, db: Session = Depends(get_db)):
    """
    §13: POST /cycle — Invocation 1 (decide + act).
    Optional body: {"subtopic": "syntax_and_core_libraries"} to target a specific sub-topic.
    """
    subtopic = request.subtopic if request else None
    try:
        result = run_cycle(db, user_id=DEMO_USER_ID, target_subtopic=subtopic)
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
            subtopic=request.subtopic,
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

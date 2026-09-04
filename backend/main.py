"""
<<<<<<< HEAD
main.py — FastAPI application (§13).

Endpoints:
  GET  /skills           — all 10 sub-topics with current signal bundles (§6.4)
  POST /cycle            — invocation 1 (decide + act)
  POST /answer           — invocation 2 (grade + decide + act)
  POST /advance_time     — move simulated clock (§5)
  GET  /strength-report  — deterministic stats + AI summary
  GET  /debug/{user_id}/{skill}/{sub_topic} — dev inspection

Single hardcoded demo user (demo_user). No auth.
=======
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
>>>>>>> 87b73f4 (feat: complete Skill Decay Alerts dashboard, quiz integration, strength report tab, and backend SDA Signal Engine)
"""

import logging
import os
<<<<<<< HEAD
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from backend.database import init_db, advance_simulated_time, get_simulated_now, db_conn
from backend.domain import DEMO_USER_ID, ALL_SUB_TOPICS, SKILLS
from backend.engines.signal_engine import get_signal_bundle, recalculate_signals_for_subtopic
from backend.engines.grading_engine import (
    GradingError,
    get_strength_report_stats,
    get_ai_analysis,
)
from backend.graph.feedback_graph import run_cycle, run_answer

# ── Logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


# ── Lifespan ──────────────────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("SDA backend starting — initialising database…")
    init_db()
    # Pre-warm sub_topic_state for demo user so GET /skills works immediately
    for skill, sub_topics in SKILLS.items():
        for sub_topic, category in sub_topics.items():
            recalculate_signals_for_subtopic(DEMO_USER_ID, skill, sub_topic, category)
    logger.info("SDA backend ready.")
    yield
    logger.info("SDA backend shutting down.")


app = FastAPI(
    title="Skill Decay Alerts API",
    description="Adaptive skill-decay detection and decision agent.",
    version="1.0.0",
    lifespan=lifespan,
=======
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
>>>>>>> 87b73f4 (feat: complete Skill Decay Alerts dashboard, quiz integration, strength report tab, and backend SDA Signal Engine)
)

app.add_middleware(
    CORSMiddleware,
<<<<<<< HEAD
    allow_origins=["*"],
=======
    allow_origins=["*"],   # dev-only; restrict in production
    allow_credentials=True,
>>>>>>> 87b73f4 (feat: complete Skill Decay Alerts dashboard, quiz integration, strength report tab, and backend SDA Signal Engine)
    allow_methods=["*"],
    allow_headers=["*"],
)


<<<<<<< HEAD
# ── Request/Response models ───────────────────────────────────────────────────

class AdvanceTimeRequest(BaseModel):
    days: float
=======
@app.on_event("startup")
def startup():
    """Initialize DB tables and seed initial state."""
    logger.info("SDA startup: initializing database...")
    init_db()
    logger.info("SDA startup: ready.")


# ── Request / Response models ─────────────────────────────────────────────────

class AdvanceTimeRequest(BaseModel):
    days: float = Field(..., gt=0, description="Number of simulated days to advance")
>>>>>>> 87b73f4 (feat: complete Skill Decay Alerts dashboard, quiz integration, strength report tab, and backend SDA Signal Engine)


class AnswerRequest(BaseModel):
    subtopic: str
    question_id: str
    selected_option: str
    cycle_id: str


<<<<<<< HEAD
# ── Error handler ─────────────────────────────────────────────────────────────

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error("Unhandled exception on %s: %s", request.url.path, exc)
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error", "error": str(exc)},
    )


# ── Endpoints ─────────────────────────────────────────────────────────────────

@app.get("/skills", summary="All 10 sub-topics with current signal bundles")
async def get_skills():
    """
    Returns all 10 sub-topics with their current signal bundles (§6.4).
    Mastery scores change visibly after POST /advance_time without changing tracking_mode.
    """
    try:
        bundle = get_signal_bundle(DEMO_USER_ID)
        return {"user_id": DEMO_USER_ID, "skills": bundle}
    except Exception as exc:
        logger.error("GET /skills failed: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))


@app.post("/cycle", summary="Run decision cycle (Invocation 1)")
async def post_cycle():
    """
    Invocation 1: update_signals → decide → route_decision → act.
    Returns decision(s) + reasoning + generated quiz (Q text + options only) or resource text.
    """
    try:
        result = await run_cycle(DEMO_USER_ID)
        return {"user_id": DEMO_USER_ID, **result}
    except Exception as exc:
        logger.error("POST /cycle failed: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))


@app.post("/answer", summary="Submit answer (Invocation 2: grade + re-decide)")
async def post_answer(body: AnswerRequest):
    """
    Invocation 2: grade → update_signals → decide → route_decision → act.
    Validates cycle_id and question_id before grading (§10.1).
    Returns updated state + new decision.
    """
    try:
        result = await run_answer(
            user_id=DEMO_USER_ID,
            cycle_id=body.cycle_id,
            question_id=body.question_id,
            selected_option=body.selected_option,
        )
        if result.get("error_information") and "GradingError" in str(
            result.get("error_information", "")
        ):
            raise HTTPException(status_code=400, detail=result["error_information"])
        return {"user_id": DEMO_USER_ID, **result}
    except GradingError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("POST /answer failed: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))


@app.post("/advance_time", summary="Advance the simulated clock (§5)")
async def post_advance_time(body: AdvanceTimeRequest):
    """
    Moves the simulated clock forward by `days` days.
    Changes decay_score (visible in GET /skills) but does NOT change
    observation_count or tracking_mode (§5 guarantee).
    """
    if body.days <= 0:
        raise HTTPException(status_code=400, detail="days must be positive")
    new_now = advance_simulated_time(body.days)
    # Recalculate decay scores for the demo user so GET /skills reflects the new time
    for skill, sub_topics in SKILLS.items():
        for sub_topic, category in sub_topics.items():
            recalculate_signals_for_subtopic(DEMO_USER_ID, skill, sub_topic, category)
    return {
        "advanced_days": body.days,
        "new_simulated_now": new_now.isoformat(),
    }


@app.get("/strength-report", summary="Per-skill/sub-topic mastery + AI summary")
async def get_strength_report():
    """
    §10.2 deterministic stats + §10.3 AI-generated analysis.
    Independent of the decide/act loop.
    """
    try:
        stats = get_strength_report_stats(DEMO_USER_ID)
        ai_summary = await get_ai_analysis(stats)
=======
# ── Endpoints ─────────────────────────────────────────────────────────────────

@app.get("/")
def serve_frontend():
    return FileResponse("frontend/index.html")


@app.get("/skills")
def get_skills(db: Session = Depends(get_db)):
    """
    §13: GET /skills — all 10 sub-topics with current signal bundles.
    Signals are recalculated fresh on each call from simulated_now.
    """
    try:
        bundles = get_signal_bundle(db, DEMO_USER_ID)
        now = get_simulated_now(db)
        return {
            "user_id": DEMO_USER_ID,
            "simulated_now": now.isoformat(),
            "skills": bundles,
        }
    except Exception as exc:
        logger.error("GET /skills error: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))


@app.post("/cycle")
def post_cycle(db: Session = Depends(get_db)):
    """
    §13: POST /cycle — LangGraph invocation 1.
    Returns decisions + reasoning + quiz (question text/options only) or resource text.
    """
    try:
        final_state = run_cycle(db, DEMO_USER_ID)

        if final_state.get("workflow_status") == "error":
            return {
                "status": "error",
                "error": final_state.get("error_information", "Unknown error"),
                "decisions": [],
                "actions": {},
            }

        # Format response
        decisions = final_state.get("agent_decisions", [])
        action_results = final_state.get("action_results", {})
        now = get_simulated_now(db)

        return {
            "status": "complete",
            "simulated_now": now.isoformat(),
            "user_id": DEMO_USER_ID,
            "decisions": decisions,
            "actions": action_results,
        }

    except Exception as exc:
        logger.error("POST /cycle error: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))


@app.post("/answer")
def post_answer(request: AnswerRequest, db: Session = Depends(get_db)):
    """
    §13: POST /answer — LangGraph invocation 2.
    Grades the answer and runs a new decide → act cycle on updated signals.
    """
    try:
        final_state = run_answer(
            db=db,
            user_id=DEMO_USER_ID,
            sub_topic=request.subtopic,
            question_id=request.question_id,
            selected_option=request.selected_option,
            cycle_id=request.cycle_id,
        )

        if final_state.get("workflow_status") == "error":
            error_info = final_state.get("error_information", "Unknown error")
            # Pass through grading-specific error codes
            if "CYCLE_NOT_FOUND" in error_info or "CYCLE_ALREADY_CONSUMED" in error_info or "INVALID_QUESTION_ID" in error_info:
                raise HTTPException(status_code=400, detail=error_info)
            return {
                "status": "error",
                "error": error_info,
                "grade_result": None,
                "decisions": [],
                "actions": {},
            }

        now = get_simulated_now(db)
        return {
            "status": "complete",
            "simulated_now": now.isoformat(),
            "user_id": DEMO_USER_ID,
            "grade_result":  final_state.get("grade_result"),
            "decisions":     final_state.get("agent_decisions", []),
            "actions":       final_state.get("action_results", {}),
        }

    except GradingError as exc:
        logger.warning("POST /answer grading error: %s (code=%s)", exc, exc.code)
        raise HTTPException(status_code=400, detail={"code": exc.code, "message": str(exc)})
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("POST /answer unexpected error: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))


@app.post("/advance_time")
def post_advance_time(request: AdvanceTimeRequest, db: Session = Depends(get_db)):
    """
    §13: POST /advance_time — move the simulated clock forward.
    §5 constraint: MUST NOT touch observation_count or tracking_mode.
    Only decay_score changes (indirectly via new simulated_now).
    """
    try:
        new_now = advance_simulated_clock(db, request.days)

        # Recalculate decay scores for all sub-topics (uses new simulated_now)
        # §5: only decay_score is affected; tracking_mode and observation_count are NOT touched
        from backend.domain import all_sub_topics
        updated = []
        for skill, sub_topic, category in all_sub_topics():
            state = db.query(SubTopicState).filter_by(
                user_id=DEMO_USER_ID, skill=skill, sub_topic=sub_topic
            ).first()
            if state:
                from backend.services.signal_engine import decay_score as calc_decay
                last_used = state.last_used_at or new_now
                days_since = max(0.0, (new_now - last_used).total_seconds() / 86400.0)
                # ONLY update decay_score — never tracking_mode or observation_count
                state.decay_score = calc_decay(days_since, category)
                state.updated_at = new_now
                updated.append({
                    "skill": skill,
                    "sub_topic": sub_topic,
                    "decay_score": state.decay_score,
                    # Confirm these are UNCHANGED (for transparency)
                    "tracking_mode_unchanged": state.tracking_mode,
                    "observation_count_unchanged": state.observation_count,
                })
        db.flush()

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
>>>>>>> 87b73f4 (feat: complete Skill Decay Alerts dashboard, quiz integration, strength report tab, and backend SDA Signal Engine)
        return {
            "user_id": DEMO_USER_ID,
            "stats": stats,
            "ai_summary": ai_summary,
        }
    except Exception as exc:
<<<<<<< HEAD
        logger.error("GET /strength-report failed: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))


@app.get(
    "/debug/{user_id}/{skill}/{sub_topic}",
    summary="Dev-only signal inspection",
)
async def get_debug(user_id: str, skill: str, sub_topic: str):
    """
    Dev-only: full inspection of observation count, recent responses, tracking mode,
    knowledge estimate, decay score, usage signal, recent accuracy, escalated flag, full bundle.
    """
    # Find category
    category = SKILLS.get(skill, {}).get(sub_topic)
    if category is None:
        raise HTTPException(
            status_code=404,
            detail=f"Unknown skill='{skill}' sub_topic='{sub_topic}'",
        )

    try:
        state = recalculate_signals_for_subtopic(user_id, skill, sub_topic, category)

        with db_conn() as conn:
            responses = conn.execute(
                """SELECT correct, timestamp, question_id, cycle_id
                   FROM quiz_responses
                   WHERE user_id=? AND skill=? AND sub_topic=?
                   ORDER BY timestamp DESC LIMIT 20""",
                (user_id, skill, sub_topic),
            ).fetchall()
            recent_responses = [dict(r) for r in responses]

        # Build the signal bundle entry for this sub-topic
        full_bundle = get_signal_bundle(user_id)
        bundle_entry = full_bundle.get(skill, {}).get(sub_topic, {})
=======
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
>>>>>>> 87b73f4 (feat: complete Skill Decay Alerts dashboard, quiz integration, strength report tab, and backend SDA Signal Engine)

        return {
            "user_id": user_id,
            "skill": skill,
            "sub_topic": sub_topic,
<<<<<<< HEAD
            "observation_count": state.get("observation_count", 0),
            "tracking_mode": state.get("tracking_mode"),
            "knowledge_probability": state.get("knowledge_probability"),
            "decay_score": state.get("decay_score"),
            "recent_accuracy": state.get("recent_accuracy"),
            "escalated": bool(state.get("escalated", 0)),
            "last_decision_action": state.get("last_decision_action"),
            "last_decision_reason": state.get("last_decision_reason"),
            "recent_responses": recent_responses,
            "full_signal_bundle": bundle_entry,
        }
    except Exception as exc:
        logger.error("GET /debug failed: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.main:app", host="0.0.0.0", port=8000, reload=True)
=======
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
>>>>>>> 87b73f4 (feat: complete Skill Decay Alerts dashboard, quiz integration, strength report tab, and backend SDA Signal Engine)

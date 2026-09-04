"""
main.py — FastAPI application (§13).

Endpoints:
  GET  /skills           — all 10 sub-topics with current signal bundles (§6.4)
  POST /cycle            — invocation 1 (decide + act)
  POST /answer           — invocation 2 (grade + decide + act)
  POST /advance_time     — move simulated clock (§5)
  GET  /strength-report  — deterministic stats + AI summary
  GET  /debug/{user_id}/{skill}/{sub_topic} — dev inspection

Single hardcoded demo user (demo_user). No auth.
"""

import logging
import os
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
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Request/Response models ───────────────────────────────────────────────────

class AdvanceTimeRequest(BaseModel):
    days: float


class AnswerRequest(BaseModel):
    subtopic: str
    question_id: str
    selected_option: str
    cycle_id: str


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
        return {
            "user_id": DEMO_USER_ID,
            "stats": stats,
            "ai_summary": ai_summary,
        }
    except Exception as exc:
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

        return {
            "user_id": user_id,
            "skill": skill,
            "sub_topic": sub_topic,
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

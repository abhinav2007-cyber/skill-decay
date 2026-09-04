"""
signal_engine.py — Deterministic decay/usage logic + pyBKT knowledge estimate.

Responsibility boundary (§2):
  - Calculates decay_score, recent_accuracy, usage recency
  - Calls pybkt_service for knowledge_probability
  - Returns per-sub-topic signal bundles (§6.4)
  MUST NOT: make TEST/WAIT/RECOMMEND/ESCALATE decisions
"""

import logging
from datetime import datetime, timedelta
from typing import Optional
from sqlalchemy.orm import Session

from backend.database import (
    SubTopicState, QuizResponse, get_simulated_now
)
from backend.domain import all_sub_topics, DEMO_USER_ID

logger = logging.getLogger(__name__)

# ── §6.1 Decay constants — tune ONLY here ─────────────────────────────────────
# Alternative to consider: exponential decay with a floor (e.g. retention never
# drops below 0.05) to keep ESCALATE from triggering on very old but irrelevant skills.
DECAY_HALF_LIFE_DAYS: dict[str, float] = {
    "procedural": 14.0,   # fast decay — 14-day half-life (per §6.1)
    "conceptual":  45.0,  # slow decay — 45-day half-life (per §6.1)
}

# §6.3 BKT threshold — tune ONLY here
MIN_BKT_OBSERVATIONS: int = 5

# §6.2 Accuracy window — tune ONLY here
RECENT_ACCURACY_WINDOW: int = 5

# Trend thresholds (§6.2)
TREND_IMPROVEMENT_THRESHOLD: float = 0.15   # +15pp = improving
TREND_DECLINE_THRESHOLD: float     = -0.15  # -15pp = declining


def decay_score(days_since_last_use: float, category: str) -> float:
    """
    Returns a value in [0, 1]; 0 = fresh, 1 = fully decayed (asymptotic).
    §6.1 formula — implement exactly.
    """
    half_life = DECAY_HALF_LIFE_DAYS[category]
    retention = 0.5 ** (days_since_last_use / half_life)
    return round(1 - retention, 4)


def _compute_recent_accuracy(
    responses: list[QuizResponse],
    window: int = RECENT_ACCURACY_WINDOW,
) -> Optional[float]:
    """
    §6.2: accuracy over the last `window` graded responses, or all if fewer exist.
    Single definition used everywhere — do NOT redefine elsewhere.
    """
    if not responses:
        return None
    recent = sorted(responses, key=lambda r: r.timestamp)[-window:]
    return round(sum(1 for r in recent if r.correct) / len(recent), 4)


def _compute_trend(responses: list[QuizResponse]) -> str:
    """
    §6.2 trend: compare most recent 3 vs. 3 before that.
    improving / declining / stable / insufficient_data.
    """
    if len(responses) < 4:
        return "insufficient_data"
    sorted_r = sorted(responses, key=lambda r: r.timestamp)
    recent_3 = sorted_r[-3:]
    prior_3  = sorted_r[-6:-3] if len(sorted_r) >= 6 else sorted_r[:-3]
    if not prior_3:
        return "insufficient_data"
    acc_recent = sum(1 for r in recent_3 if r.correct) / len(recent_3)
    acc_prior  = sum(1 for r in prior_3  if r.correct) / len(prior_3)
    delta = acc_recent - acc_prior
    if delta >= TREND_IMPROVEMENT_THRESHOLD:
        return "improving"
    if delta <= TREND_DECLINE_THRESHOLD:
        return "declining"
    return "stable"


def _get_responses(db: Session, user_id: str, skill: str, sub_topic: str) -> list[QuizResponse]:
    """Fetch all responses for (user, skill, sub_topic) ordered chronologically."""
    return (
        db.query(QuizResponse)
        .filter_by(user_id=user_id, skill=skill, sub_topic=sub_topic)
        .order_by(QuizResponse.timestamp)
        .all()
    )


def recalculate_and_persist_state(
    db: Session, user_id: str, skill: str, sub_topic: str, category: str
) -> SubTopicState:
    """
    Recalculate all signals for one (user, skill, sub_topic) and upsert SubTopicState.
    Returns the updated state row.

    §5: reads simulated_now — never datetime.now().
    §6.3: decides tracking_mode; never fabricates knowledge_probability outside 'bkt'.
    """
    from backend.services.pybkt_service import estimate_knowledge  # local import avoids circular

    now = get_simulated_now(db)

    # Fetch or create the state row
    state = db.query(SubTopicState).filter_by(
        user_id=user_id, skill=skill, sub_topic=sub_topic
    ).first()

    if state is None:
        state = SubTopicState(
            user_id=user_id,
            skill=skill,
            sub_topic=sub_topic,
            category=category,
            last_used_at=now,
            tracking_mode="cold_start",
            knowledge_probability=None,
            observation_count=0,
            decay_score=0.0,
            recent_accuracy=None,
            escalated=False,
            updated_at=now,
        )
        db.add(state)
        db.flush()

    # Fetch responses
    responses = _get_responses(db, user_id, skill, sub_topic)
    obs_count = len(responses)

    # ── Tracking mode (§6.3) — monotonically increases as data grows ──────────
    if obs_count == 0:
        mode = "cold_start"
    elif obs_count < MIN_BKT_OBSERVATIONS:
        mode = "decay_fallback"
    else:
        mode = "bkt"

    # ── pyBKT knowledge estimate — only in 'bkt' mode ─────────────────────────
    knowledge_prob: Optional[float] = None
    if mode == "bkt":
        try:
            knowledge_prob = estimate_knowledge(user_id, skill, sub_topic, responses)
        except Exception as exc:
            logger.error(
                "pyBKT estimation failed for %s/%s/%s: %s",
                user_id, skill, sub_topic, exc
            )
            knowledge_prob = None  # fallback: keep null, don't crash

    # ── Decay score (§6.1) ────────────────────────────────────────────────────
    last_used = state.last_used_at or now
    days_since = max(0.0, (now - last_used).total_seconds() / 86400.0)
    d_score = decay_score(days_since, category)

    # ── Recent accuracy (§6.2) ────────────────────────────────────────────────
    recent_acc: Optional[float] = None
    if mode in ("decay_fallback", "bkt"):
        recent_acc = _compute_recent_accuracy(responses)

    # ── Upsert ────────────────────────────────────────────────────────────────
    state.tracking_mode       = mode
    state.knowledge_probability = knowledge_prob
    state.observation_count   = obs_count
    state.decay_score         = d_score
    state.recent_accuracy     = recent_acc
    state.updated_at          = now
    # NOTE: escalated flag is NOT touched here — only Decision Agent sets/clears it

    db.flush()
    return state


def _build_bundle(state: SubTopicState, now: datetime) -> dict:
    """Build the §6.4 signal bundle dict from a state row."""
    last_used = state.last_used_at or now
    days_since = max(0.0, (now - last_used).total_seconds() / 86400.0)

    bundle = {
        "skill":    state.skill,
        "sub_topic": state.sub_topic,
        "category": state.category,
        "knowledge_tracking": {
            "mode":                 state.tracking_mode,
            "knowledge_probability": state.knowledge_probability,  # None outside 'bkt'
            "observation_count":    state.observation_count,
        },
        "decay": {
            "days_since_last_use": round(days_since, 2),
            "decay_score":         state.decay_score,
        },
        "usage": {
            "recent_usage": days_since <= 7,  # proxy: used within last 7 sim-days
        },
        "quiz": {
            "recent_accuracy": state.recent_accuracy,
        },
        "escalated": state.escalated,
    }
    return bundle


def get_signal_bundle(db: Session, user_id: str) -> dict:
    """
    §6.5: Returns all 10 sub-topics' signal bundles keyed by skill -> sub_topic.
    Recalculates all signals fresh before returning.
    """
    now = get_simulated_now(db)
    result: dict[str, dict] = {}
    for skill, sub_topic, category in all_sub_topics(db, user_id):
        try:
            state = recalculate_and_persist_state(db, user_id, skill, sub_topic, category)
            bundle = _build_bundle(state, now)
        except Exception as exc:
            logger.error("Signal bundle failed for %s/%s: %s", skill, sub_topic, exc)
            bundle = {
                "skill": skill, "sub_topic": sub_topic, "category": category,
                "error": str(exc),
            }
        result.setdefault(skill, {})[sub_topic] = bundle

    return result


def get_trend_for_subtopic(db: Session, user_id: str, skill: str, sub_topic: str) -> str:
    """Return trend string for the Strength Report (§6.2)."""
    responses = _get_responses(db, user_id, skill, sub_topic)
    return _compute_trend(responses)

"""
signal_engine.py — Signal Engine (§6).

Responsibilities (per §2 boundary table):
  - Decay formula (§6.1)
  - Recent-accuracy window (§6.2) — single definition, used everywhere
  - pyBKT integration with sparse-data fallback (§6.3)
  - Assembles the signal bundle (§6.4)
  - Persists results to sub_topic_state
  - get_signal_bundle(user_id) → full 10-sub-topic bundle

Must NOT make TEST/WAIT/RECOMMEND/ESCALATE decisions — that is the Decision Agent's job.
"""

import logging
from datetime import datetime, timedelta, timezone

from backend.database import db_conn, get_simulated_now
from backend.domain import ALL_SUB_TOPICS, SKILLS, DEMO_USER_ID
from backend.services import bkt_service
from backend.services.bkt_service import MIN_BKT_OBSERVATIONS, get_tracking_mode

logger = logging.getLogger(__name__)

# ── §6.1 Decay constants ───────────────────────────────────────────────────────
# Tune here only — §6.1 says these are the concrete starting point.
# Alternative note: 7/30 day half-lives would model faster procedural decay.
DECAY_HALF_LIFE_DAYS: dict[str, int] = {
    "procedural": 14,  # fast decay
    "conceptual": 45,  # slow decay
}

# Hardcoded last_used_at offsets for the demo (§12: live GitHub OAuth is OOS).
# Values chosen to produce a range of decay scores for demo visibility.
_LAST_USED_OFFSETS_DAYS: dict[str, dict[str, int]] = {
    "Python": {"syntax_and_core_libraries": 5, "oop_and_design_patterns": 10},
    "Java": {"syntax_and_collections": 20, "oop_and_jvm_concepts": 30},
    "DBMS": {"sql_queries_and_joins": 3, "normalization_and_transactions": 60},
    "Machine Learning": {"model_apis_and_libraries": 12, "algorithms_and_theory": 90},
    "DSA": {"implementation_and_syntax": 7, "complexity_and_problem_solving": 45},
}


def decay_score(days_since_last_use: float, category: str) -> float:
    """
    §6.1 — Returns a value in [0, 1]; 0 = fresh, 1 = fully decayed (asymptotic).
    Uses exponential decay with category-specific half-lives.
    """
    half_life = DECAY_HALF_LIFE_DAYS[category]
    retention = 0.5 ** (days_since_last_use / half_life)
    return round(1 - retention, 4)


# ── §6.2 Recent-accuracy window (single definition) ───────────────────────────
RECENT_ACCURACY_WINDOW = 5  # last N graded responses per (user, skill, sub_topic)
TREND_WINDOW = 3            # compare last-3 vs prior-3 for trend direction


def _get_ordered_responses(conn, user_id: str, skill: str, sub_topic: str) -> list[dict]:
    """Return all quiz_responses for (user, skill, sub_topic), chronological order."""
    rows = conn.execute(
        """SELECT correct, timestamp FROM quiz_responses
           WHERE user_id=? AND skill=? AND sub_topic=?
           ORDER BY timestamp ASC""",
        (user_id, skill, sub_topic),
    ).fetchall()
    return [{"correct": bool(r["correct"]), "timestamp": r["timestamp"]} for r in rows]


def _recent_accuracy(responses: list[dict]) -> float | None:
    """§6.2 — accuracy over the last RECENT_ACCURACY_WINDOW responses."""
    if not responses:
        return None
    window = responses[-RECENT_ACCURACY_WINDOW:]
    return round(sum(1 for r in window if r["correct"]) / len(window), 4)


def _compute_trend(responses: list[dict]) -> str:
    """
    §6.2 — Compare accuracy of last-3 vs prior-3.
    improving  : rose by ≥15 pp
    declining  : fell by ≥15 pp
    stable     : within ±15 pp
    insufficient_data : fewer than 4 total responses
    """
    if len(responses) < 4:
        return "insufficient_data"
    recent = responses[-TREND_WINDOW:]
    prior = responses[-(2 * TREND_WINDOW):-TREND_WINDOW]
    if not prior:
        return "insufficient_data"
    acc_recent = sum(1 for r in recent if r["correct"]) / len(recent)
    acc_prior = sum(1 for r in prior if r["correct"]) / len(prior)
    diff = acc_recent - acc_prior
    if diff >= 0.15:
        return "improving"
    elif diff <= -0.15:
        return "declining"
    return "stable"


def _get_or_create_state(conn, user_id: str, skill: str, sub_topic: str, category: str) -> dict:
    """Fetch sub_topic_state row, creating it with defaults if absent."""
    row = conn.execute(
        "SELECT * FROM sub_topic_state WHERE user_id=? AND skill=? AND sub_topic=?",
        (user_id, skill, sub_topic),
    ).fetchone()
    if row:
        return dict(row)
    # Create default row; last_used_at is mock-derived from the hardcoded offsets
    sim_now = get_simulated_now()
    offset_days = _LAST_USED_OFFSETS_DAYS.get(skill, {}).get(sub_topic, 30)
    last_used = (sim_now - timedelta(days=offset_days)).isoformat()
    now_iso = sim_now.isoformat()
    conn.execute(
        """INSERT INTO sub_topic_state
           (user_id, skill, sub_topic, category, last_used_at, tracking_mode,
            knowledge_probability, observation_count, decay_score, recent_accuracy,
            last_decision_action, last_decision_reason, escalated, updated_at)
           VALUES (?,?,?,?,?,'cold_start',NULL,0,0.0,NULL,NULL,NULL,0,?)""",
        (user_id, skill, sub_topic, category, last_used, now_iso),
    )
    return {
        "user_id": user_id, "skill": skill, "sub_topic": sub_topic,
        "category": category, "last_used_at": last_used,
        "tracking_mode": "cold_start", "knowledge_probability": None,
        "observation_count": 0, "decay_score": 0.0, "recent_accuracy": None,
        "last_decision_action": None, "last_decision_reason": None,
        "escalated": 0, "updated_at": now_iso,
    }


def recalculate_signals_for_subtopic(
    user_id: str, skill: str, sub_topic: str, category: str
) -> dict:
    """
    Recalculate all signals for one (user, skill, sub_topic) and upsert sub_topic_state.
    Returns the updated state row as a dict.

    §5: Uses get_simulated_now() for 'now' — never datetime.now().
    §11.5: pyBKT failure → falls back to decay_fallback mode, logs error, does not crash.
    """
    sim_now = get_simulated_now()

    with db_conn() as conn:
        state = _get_or_create_state(conn, user_id, skill, sub_topic, category)
        responses = _get_ordered_responses(conn, user_id, skill, sub_topic)
        obs_count = len(responses)

        # ── Decay (§6.1) ──────────────────────────────────────────────────────
        last_used_dt = datetime.fromisoformat(state["last_used_at"])
        if last_used_dt.tzinfo is None:
            last_used_dt = last_used_dt.replace(tzinfo=timezone.utc)
        days_since = (sim_now - last_used_dt).total_seconds() / 86400
        decay = decay_score(days_since, category)

        # ── Tracking mode (§6.3) ──────────────────────────────────────────────
        mode = get_tracking_mode(obs_count)

        # ── pyBKT (§6.3) ──────────────────────────────────────────────────────
        knowledge_prob: float | None = None
        if mode == "bkt":
            try:
                knowledge_prob = bkt_service.estimate_knowledge_probability(
                    user_id, sub_topic, responses
                )
            except Exception as e:
                # §11.5: pyBKT failure → graceful fallback
                logger.error(
                    "pyBKT failed for user=%s sub_topic=%s — falling back to decay_fallback: %s",
                    user_id, sub_topic, e
                )
                mode = "decay_fallback"
                knowledge_prob = None

        # ── Recent accuracy (§6.2) ────────────────────────────────────────────
        rec_acc = _recent_accuracy(responses) if responses else None

        # ── Upsert sub_topic_state ─────────────────────────────────────────────
        # §5: advance_simulated_time must NOT touch observation_count or tracking_mode.
        # Here we explicitly set them from real response data every recalculation.
        now_iso = sim_now.isoformat()
        conn.execute(
            """INSERT INTO sub_topic_state
               (user_id, skill, sub_topic, category, last_used_at, tracking_mode,
                knowledge_probability, observation_count, decay_score, recent_accuracy,
                last_decision_action, last_decision_reason, escalated, updated_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
               ON CONFLICT(user_id, skill, sub_topic) DO UPDATE SET
                 tracking_mode=excluded.tracking_mode,
                 knowledge_probability=excluded.knowledge_probability,
                 observation_count=excluded.observation_count,
                 decay_score=excluded.decay_score,
                 recent_accuracy=excluded.recent_accuracy,
                 updated_at=excluded.updated_at""",
            (
                user_id, skill, sub_topic, category,
                state["last_used_at"],  # last_used_at is mock; not changed here
                mode, knowledge_prob, obs_count, decay, rec_acc,
                state.get("last_decision_action"), state.get("last_decision_reason"),
                int(state.get("escalated", 0)), now_iso,
            ),
        )

        # Re-read the row to return authoritative state
        updated = dict(conn.execute(
            "SELECT * FROM sub_topic_state WHERE user_id=? AND skill=? AND sub_topic=?",
            (user_id, skill, sub_topic),
        ).fetchone())

    return updated


def _build_bundle_entry(state: dict, responses: list[dict]) -> dict:
    """
    §6.4 — Assemble one sub-topic's signal bundle from the state row + response list.
    """
    sim_now = get_simulated_now()
    last_used_dt = datetime.fromisoformat(state["last_used_at"])
    if last_used_dt.tzinfo is None:
        last_used_dt = last_used_dt.replace(tzinfo=timezone.utc)
    days_since = round((sim_now - last_used_dt).total_seconds() / 86400, 2)

    bundle: dict = {
        "skill": state["skill"],
        "sub_topic": state["sub_topic"],
        "category": state["category"],
        "knowledge_tracking": {
            "mode": state["tracking_mode"],
            "knowledge_probability": state["knowledge_probability"],
            "observation_count": state["observation_count"],
        },
        "decay": {
            "days_since_last_use": days_since,
            "decay_score": state["decay_score"],
        },
        "usage": {
            "recent_usage": days_since <= 7,  # considered "recent" within 7 days
        },
        "quiz": {
            "recent_accuracy": state["recent_accuracy"],
        },
        "escalated": bool(state.get("escalated", 0)),
        "last_decision_action": state.get("last_decision_action"),
        "last_decision_reason": state.get("last_decision_reason"),
    }
    return bundle


def get_signal_bundle(user_id: str) -> dict:
    """
    §6.5 — Returns all 10 sub-topics' signal bundles for the user,
    keyed by skill → sub_topic.

    Recalculates signals for every sub-topic before assembling the bundle.
    """
    result: dict[str, dict] = {}

    for skill, sub_topics in SKILLS.items():
        result[skill] = {}
        for sub_topic, category in sub_topics.items():
            state = recalculate_signals_for_subtopic(user_id, skill, sub_topic, category)
            with db_conn() as conn:
                responses = _get_ordered_responses(conn, user_id, skill, sub_topic)
            bundle_entry = _build_bundle_entry(state, responses)
            result[skill][sub_topic] = bundle_entry

    return result

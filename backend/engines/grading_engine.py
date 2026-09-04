"""
grading_engine.py — Grading (§10.1) and Strength Report (§10.2 + §10.3).

§10.1 Grading + question_id validation:
  - Validates cycle_id exists and is not consumed
  - Validates question_id belongs to the cycle
  - Writes a quiz_responses row
  - Marks the cycle consumed

§10.2 Strength Report — deterministic stats only (no LLM here)
§10.3 AI-generated analysis — Featherless.ai call #3 (distinct from calls #1 and #2)
"""

import json
import logging
from datetime import datetime, timezone
from typing import Optional

from backend.database import db_conn, get_simulated_now
from backend.domain import SKILLS
from backend.engines.signal_engine import (
    _recent_accuracy,
    _compute_trend,
    _get_ordered_responses,
    recalculate_signals_for_subtopic,
)
from backend.services.featherless_client import featherless_chat

logger = logging.getLogger(__name__)


class GradingError(Exception):
    """Controlled grading error (§11.5) — should result in a 400 response, not a 500."""


def grade_response(
    user_id: str,
    cycle_id: str,
    question_id: str,
    selected_option: str,
) -> dict:
    """
    §10.1 — Grade a single question response.

    Steps (exactly as specified):
    1. Look up quiz_cycles by cycle_id; reject if not found or consumed.
    2. Confirm question_id exists in that cycle's questions.
    3. Grade against stored correct answer.
    4. Write quiz_responses row (with cycle_id).
    5. Mark quiz_cycles.consumed = TRUE.

    Returns: {correct, correct_answer, explanation, sub_topic, skill}
    Raises GradingError on validation failures.
    """
    with db_conn() as conn:
        # Step 1: validate cycle
        cycle_row = conn.execute(
            "SELECT * FROM quiz_cycles WHERE cycle_id=? AND user_id=?",
            (cycle_id, user_id),
        ).fetchone()
        if cycle_row is None:
            raise GradingError(
                f"cycle_id '{cycle_id}' not found for user '{user_id}'. "
                "Ensure you are using the cycle_id returned by POST /cycle."
            )
        if cycle_row["consumed"]:
            raise GradingError(
                f"cycle_id '{cycle_id}' has already been graded (consumed=TRUE). "
                "A quiz cycle can only be submitted once."
            )

        # Step 2: validate question_id
        questions = json.loads(cycle_row["questions"])
        question = next(
            (q for q in questions if q["question_id"] == question_id), None
        )
        if question is None:
            raise GradingError(
                f"question_id '{question_id}' does not belong to cycle '{cycle_id}'. "
                "This may be a stale/mismatched question_id from an old cycle."
            )

        # Step 3: grade
        correct_answer = question["correct_answer"]
        is_correct = (selected_option.strip().upper() == correct_answer.strip().upper())

        # Step 4: write quiz_response
        skill = cycle_row["skill"]
        sub_topic = cycle_row["sub_topic"]
        now_iso = get_simulated_now().isoformat()
        conn.execute(
            """INSERT INTO quiz_responses
               (user_id, skill, sub_topic, question_id, correct, timestamp, cycle_id)
               VALUES (?,?,?,?,?,?,?)""",
            (user_id, skill, sub_topic, question_id, int(is_correct), now_iso, cycle_id),
        )

        # Step 5: mark cycle consumed
        conn.execute(
            "UPDATE quiz_cycles SET consumed=1 WHERE cycle_id=?", (cycle_id,)
        )

    # After grading, recalculate signals for the affected sub-topic
    category = SKILLS.get(skill, {}).get(sub_topic, "conceptual")
    recalculate_signals_for_subtopic(user_id, skill, sub_topic, category)

    return {
        "correct": is_correct,
        "correct_answer": correct_answer,
        "explanation": question.get("explanation", ""),
        "skill": skill,
        "sub_topic": sub_topic,
        "selected_option": selected_option,
    }


# ── §10.2 Deterministic strength report stats ─────────────────────────────────

def _effective_mastery(state_row: dict) -> float:
    """
    §10.2 — Effective mastery for one sub-topic:
      - If tracking_mode == 'bkt': use knowledge_probability
      - Otherwise: use 1 - decay_score as a proxy.
    Modeling note (as required by §10.2): 1-decay_score is NOT equivalent to BKT's
    knowledge_probability. It is the best available signal when BKT hasn't had enough
    data, capturing only time-based decay without learning history.
    """
    if state_row.get("tracking_mode") == "bkt" and state_row.get("knowledge_probability") is not None:
        return float(state_row["knowledge_probability"])
    # Fallback proxy: 1 - decay_score (see §10.2 modeling note)
    return round(1.0 - float(state_row.get("decay_score", 0.0)), 4)


def get_strength_report_stats(user_id: str) -> dict:
    """
    §10.2 — Per-skill and per-sub-topic mastery %, category, trend.
    Skill-level mastery = average of its two sub-topics' effective mastery.
    """
    report: dict = {"skills": {}, "sub_topics": {}}

    with db_conn() as conn:
        for skill, sub_topics in SKILLS.items():
            sub_mastery_values = []
            for sub_topic, category in sub_topics.items():
                # Get current state row
                state_row = conn.execute(
                    "SELECT * FROM sub_topic_state WHERE user_id=? AND skill=? AND sub_topic=?",
                    (user_id, skill, sub_topic),
                ).fetchone()
                if state_row is None:
                    # Sub-topic has no state yet — cold start
                    mastery = 0.5  # neutral prior
                    trend = "insufficient_data"
                    obs_count = 0
                    tracking_mode = "cold_start"
                else:
                    state_dict = dict(state_row)
                    mastery = _effective_mastery(state_dict)
                    responses = _get_ordered_responses(conn, user_id, skill, sub_topic)
                    trend = _compute_trend(responses)
                    obs_count = state_dict.get("observation_count", 0)
                    tracking_mode = state_dict.get("tracking_mode", "cold_start")

                sub_mastery_values.append(mastery)
                report["sub_topics"][f"{skill}/{sub_topic}"] = {
                    "skill": skill,
                    "sub_topic": sub_topic,
                    "category": category,
                    "mastery_pct": round(mastery * 100, 1),
                    "trend": trend,
                    "observation_count": obs_count,
                    "tracking_mode": tracking_mode,
                }

            skill_mastery = round(sum(sub_mastery_values) / len(sub_mastery_values) * 100, 1)
            report["skills"][skill] = {"mastery_pct": skill_mastery}

    return report


# ── §10.3 AI-generated analysis (Featherless.ai call #3) ─────────────────────

ANALYSIS_SYSTEM_PROMPT = """You are a learning analytics advisor. You receive mastery statistics 
for a professional learner's skill sub-topics. Your job is to write a short analyst-style summary 
(3-5 sentences) identifying:
1. The weakest skill area(s) — name the specific sub-topic, its mastery %, and trend.
2. What this means for the learner's professional readiness.
3. A concrete first step to address the gap.

Do NOT make up statistics. Only reference the data you are given.
Write in plain language. Do not use headers, bullet points, or markdown.
"""


async def get_ai_analysis(stats: dict) -> str:
    """
    §10.3 — Generate AI-powered analyst summary.
    Featherless.ai call #3 — separate from Decision Agent (#1) and Action Layer (#2).
    """
    messages = [
        {"role": "system", "content": ANALYSIS_SYSTEM_PROMPT},
        {
            "role": "user",
            "content": (
                "Here are the learner's current mastery statistics:\n\n"
                + json.dumps(stats, indent=2)
                + "\n\nProvide an analyst-style summary of the weakest areas and recommended first step."
            ),
        },
    ]
    try:
        text = await featherless_chat(
            messages, call_site="strength_report_analysis", max_tokens=600
        )
        return text.strip()
    except Exception as exc:
        logger.error("Strength report AI analysis failed: %s", exc)
        return (
            "AI analysis temporarily unavailable. "
            f"Lowest mastery areas from stats: "
            + ", ".join(
                f"{k} ({v['mastery_pct']}%)"
                for k, v in sorted(
                    stats.get("sub_topics", {}).items(),
                    key=lambda x: x[1].get("mastery_pct", 100),
                )[:3]
            )
        )

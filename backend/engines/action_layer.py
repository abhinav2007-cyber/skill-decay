"""
action_layer.py — Agent Action Layer (§8), Featherless.ai call #2.

Responsibilities (distinct from Decision Agent):
  - Given a decided action for a sub-topic, generate content:
      TEST_NOW  → 2-3 MCQs (question, options, correct_answer, explanation)
      RECOMMEND → 2-3 sentence targeted explanation/pointer
      WAIT      → no generation
      ESCALATE  → no generation; sets escalated flag in DB
  - Assigns question_ids unique within cycle_id
  - Stores quizzes server-side in quiz_cycles (with correct answers)
  - Returns only question text + options (no correct answers) to caller

Must NOT make the TEST/WAIT/RECOMMEND/ESCALATE decision — that is the Decision Agent's job.
"""

import json
import logging
import re
import uuid
from datetime import datetime, timezone
from typing import Any

from backend.database import db_conn, get_simulated_now
from backend.services.featherless_client import featherless_chat
from backend.engines.decision_agent import MAX_RECOMMEND_PER_CYCLE

logger = logging.getLogger(__name__)

# ── Quiz generation system prompt ─────────────────────────────────────────────
QUIZ_SYSTEM_PROMPT = """You are an expert quiz generator for technical skill assessment.
Generate 2-3 multiple-choice questions for the given skill sub-topic.

Each question must be:
- Practically meaningful (not trivial)
- Clear and unambiguous
- Have exactly 4 options (A, B, C, D)
- Have exactly one correct answer

Respond with ONLY a valid JSON array — no markdown, no explanation outside the JSON.
Format:
[
  {
    "question": "<question text>",
    "options": {"A": "...", "B": "...", "C": "...", "D": "..."},
    "correct_answer": "A",
    "explanation": "<one-line explanation of why this is correct>"
  }
]
"""

# ── Resource recommendation system prompt ─────────────────────────────────────
RECOMMEND_SYSTEM_PROMPT = """You are an expert learning advisor for technical skills.
Given a skill sub-topic, provide a 2-3 sentence targeted refresher explanation or learning pointer.
Be specific: name the exact concept to review, suggest a concrete resource type (e.g., "review the official Python docs on context managers"), and explain why this specific gap matters in practice.
Respond with ONLY a plain-text paragraph — no JSON, no bullet points, no headers.
"""


def _extract_json_array(text: str) -> list | None:
    """Strip markdown fences and extract first JSON array from text."""
    text = re.sub(r"```(?:json)?", "", text).strip()
    start = text.find("[")
    end = text.rfind("]")
    if start == -1 or end == -1:
        return None
    try:
        return json.loads(text[start : end + 1])
    except json.JSONDecodeError:
        return None


async def _generate_quiz(
    skill: str, sub_topic: str, category: str, cycle_id: str
) -> dict | None:
    """
    Generate MCQs via Featherless.ai.
    Returns a dict with keys: questions_for_client, questions_full
    or None on failure.
    """
    messages = [
        {"role": "system", "content": QUIZ_SYSTEM_PROMPT},
        {
            "role": "user",
            "content": (
                f"Skill: {skill}\n"
                f"Sub-topic: {sub_topic.replace('_', ' ')}\n"
                f"Category: {category} (procedural = syntax/implementation; conceptual = theory/design)\n"
                f"Generate 2-3 targeted MCQ questions for this sub-topic."
            ),
        },
    ]
    try:
        response_text = await featherless_chat(
            messages, call_site="action_layer_quiz", max_tokens=1500
        )
        raw = _extract_json_array(response_text)
        if not raw or not isinstance(raw, list):
            logger.error("Quiz generation for %s returned non-parseable JSON", sub_topic)
            return None

        # Assign question_ids and split into full (with answers) vs client (without)
        questions_full = []
        questions_for_client = []
        for n, q in enumerate(raw):
            qid = f"{sub_topic}_{cycle_id}_{n}"
            full_q = {
                "question_id": qid,
                "question": q.get("question", ""),
                "options": q.get("options", {}),
                "correct_answer": q.get("correct_answer", ""),
                "explanation": q.get("explanation", ""),
            }
            client_q = {
                "question_id": qid,
                "question": q.get("question", ""),
                "options": q.get("options", {}),
                # correct_answer and explanation intentionally omitted
            }
            questions_full.append(full_q)
            questions_for_client.append(client_q)

        return {
            "questions_for_client": questions_for_client,
            "questions_full": questions_full,
        }
    except Exception as exc:
        logger.error("Quiz generation failed for %s/%s: %s", skill, sub_topic, exc)
        return None


async def _generate_recommendation(skill: str, sub_topic: str, category: str) -> str | None:
    """Generate a 2-3 sentence resource recommendation via Featherless.ai."""
    messages = [
        {"role": "system", "content": RECOMMEND_SYSTEM_PROMPT},
        {
            "role": "user",
            "content": (
                f"Skill: {skill}\n"
                f"Sub-topic: {sub_topic.replace('_', ' ')}\n"
                f"Category: {category}\n"
                f"Provide a targeted 2-3 sentence refresher pointer."
            ),
        },
    ]
    try:
        response_text = await featherless_chat(
            messages, call_site="action_layer_recommend", max_tokens=400
        )
        return response_text.strip()
    except Exception as exc:
        logger.error("Recommendation generation failed for %s/%s: %s", skill, sub_topic, exc)
        return None


def _set_escalated(user_id: str, skill: str, sub_topic: str, value: bool):
    """Set or clear the escalated flag in sub_topic_state."""
    with db_conn() as conn:
        conn.execute(
            """UPDATE sub_topic_state SET escalated=? WHERE user_id=? AND skill=? AND sub_topic=?""",
            (int(value), user_id, skill, sub_topic),
        )


def _save_quiz_cycle(
    cycle_id: str, user_id: str, skill: str, sub_topic: str, questions_full: list
):
    """Persist the quiz cycle to quiz_cycles table."""
    with db_conn() as conn:
        conn.execute(
            """INSERT INTO quiz_cycles (cycle_id, user_id, skill, sub_topic, questions, created_at, consumed)
               VALUES (?,?,?,?,?,?,0)""",
            (
                cycle_id,
                user_id,
                skill,
                sub_topic,
                json.dumps(questions_full),
                get_simulated_now().isoformat(),
            ),
        )


async def execute_actions(
    user_id: str,
    decisions: list[dict],
    signal_bundle: dict,
) -> list[dict]:
    """
    §8 — Execute actions decided by the Decision Agent for each sub-topic.

    Parameters
    ----------
    user_id   : the user
    decisions : list of {subtopic, action, reason} from the Decision Agent
    signal_bundle : the full bundle (to look up skill/category per sub-topic)

    Returns
    -------
    list of action results, one per sub-topic:
      {subtopic, action, reason, quiz (if TEST_NOW), recommendation (if RECOMMEND)}

    §8.1 caps: at most 3 quiz calls, at most 3 recommendation calls.
    A failure on one sub-topic's call must NOT abort other sub-topics' results.
    """
    # Build a lookup: sub_topic → {skill, category}
    subtopic_meta: dict[str, dict] = {}
    for skill, sub_topics in signal_bundle.items():
        for sub_topic, entry in sub_topics.items():
            subtopic_meta[sub_topic] = {
                "skill": skill,
                "category": entry["category"],
            }

    results = []
    quiz_calls_made = 0
    recommend_calls_made = 0

    for decision in decisions:
        sub_topic = decision["subtopic"]
        action = decision["action"]
        reason = decision["reason"]
        meta = subtopic_meta.get(sub_topic, {"skill": "Unknown", "category": "conceptual"})
        skill = meta["skill"]
        category = meta["category"]

        result_entry: dict = {
            "subtopic": sub_topic,
            "skill": skill,
            "action": action,
            "reason": reason,
        }

        if action == "TEST_NOW":
            if quiz_calls_made < 3:
                quiz_calls_made += 1
                cycle_id = str(uuid.uuid4())
                quiz_data = await _generate_quiz(skill, sub_topic, category, cycle_id)
                if quiz_data:
                    _save_quiz_cycle(cycle_id, user_id, skill, sub_topic, quiz_data["questions_full"])
                    result_entry["cycle_id"] = cycle_id
                    result_entry["quiz"] = quiz_data["questions_for_client"]
                    # Clear escalated flag if it was set (§9: de-escalate once addressed)
                    _set_escalated(user_id, skill, sub_topic, False)
                else:
                    result_entry["error"] = "Quiz generation failed — quiz not available"
            else:
                # §8.1 cap: downgrade excess TEST_NOW (already capped by decision agent,
                # but defensive check here for RECOMMEND)
                result_entry["action"] = "WAIT"
                result_entry["reason"] = (
                    f"[§8.1 cap: max {3} quiz calls reached; downgraded from TEST_NOW]"
                )

        elif action == "RECOMMEND":
            if recommend_calls_made < MAX_RECOMMEND_PER_CYCLE:
                recommend_calls_made += 1
                rec_text = await _generate_recommendation(skill, sub_topic, category)
                if rec_text:
                    result_entry["recommendation"] = rec_text
                    # Clear escalated flag if it was set
                    _set_escalated(user_id, skill, sub_topic, False)
                else:
                    result_entry["recommendation"] = (
                        "[Recommendation generation failed — please review this sub-topic manually.]"
                    )
            else:
                # §8.1 cap exceeded for RECOMMEND
                result_entry["recommendation"] = (
                    f"[§8.1 cap: max {MAX_RECOMMEND_PER_CYCLE} recommendation calls reached; "
                    f"placeholder: review {sub_topic.replace('_', ' ')} independently.]"
                )
                _set_escalated(user_id, skill, sub_topic, False)

        elif action == "ESCALATE":
            # §9: set escalated flag, no generation
            _set_escalated(user_id, skill, sub_topic, True)
            result_entry["escalated"] = True

        elif action == "WAIT":
            pass  # no generation

        else:
            # §11.3: unrecognized action → controlled error, never executed
            logger.error(
                "Unrecognized action '%s' for sub_topic '%s' — treating as WAIT", action, sub_topic
            )
            result_entry["action"] = "WAIT"
            result_entry["error"] = f"Unrecognized action '{action}' — controlled fallback to WAIT"

        # Persist the decision to sub_topic_state
        _update_last_decision(user_id, skill, sub_topic, action, reason)
        results.append(result_entry)

    return results


def _update_last_decision(
    user_id: str, skill: str, sub_topic: str, action: str, reason: str
):
    """Persist last_decision_action and last_decision_reason to sub_topic_state."""
    with db_conn() as conn:
        conn.execute(
            """UPDATE sub_topic_state
               SET last_decision_action=?, last_decision_reason=?
               WHERE user_id=? AND skill=? AND sub_topic=?""",
            (action, reason, user_id, skill, sub_topic),
        )

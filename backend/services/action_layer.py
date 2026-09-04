"""
action_layer.py — LLM call #2: Agent Action Layer (Featherless.ai).

Responsibility boundary (§2):
  - TEST_NOW → generate 2-3 MCQs with question_id, options, correct answer, explanation
  - RECOMMEND → generate 2-3 sentence targeted resource pointer
  - WAIT → no generation call
  - ESCALATE → no generation call (§8)
  MUST NOT: make the TEST/WAIT/RECOMMEND/ESCALATE decision.

§8.1 per-call: 20s timeout, up to 3 key rotations.
§8.1 cap: TEST_NOW calls ≤ 3, RECOMMEND calls ≤ 3. Excess → placeholder.
"""

import json
import logging
import uuid

from backend.services.featherless_client import chat_complete, FeatherlessAllKeysFailedError

logger = logging.getLogger(__name__)

MAX_TEST_NOW_CALLS: int = 3    # §8.1 cap on quiz generation calls per cycle
MAX_RECOMMEND_CALLS: int = 3   # §8.1 cap on recommend generation calls per cycle


def _generate_quiz(
    skill: str,
    sub_topic: str,
    category: str,
    cycle_id: str,
    signal_summary: str,
) -> list[dict]:
    """
    Generate 2-3 MCQs for the given sub-topic via Featherless.ai.
    Returns list of question dicts including correct_answer (stored server-side only).
    Each question gets a unique question_id: f"{sub_topic}_{cycle_id}_{n}"
    """
    system_prompt = f"""You are an expert technical quiz generator for skill assessment.
Generate exactly 3 multiple-choice questions (MCQs) to assess a learner's knowledge of:
  Skill: {skill}
  Sub-topic: {sub_topic} (type: {category})

Signal context (for difficulty calibration): {signal_summary}

OUTPUT FORMAT: Respond ONLY with a valid JSON array (no markdown):
[
  {{
    "question": "question text here",
    "options": ["A) ...", "B) ...", "C) ...", "D) ..."],
    "correct_answer": "A) ...",
    "explanation": "one-line explanation of why this is correct"
  }},
  ...
]

Rules:
- Questions must be specific and non-trivial
- Exactly 4 options per question (A through D)
- correct_answer must match one of the options exactly
- No ambiguous or trick questions
- Appropriate difficulty: {"procedural" if category == "procedural" else "conceptual"} knowledge
"""

    try:
        raw = chat_complete(
            messages=[{"role": "system", "content": system_prompt}],
            temperature=0.4,
            max_tokens=1500,
            call_site="action_layer_quiz",
        )

        # Parse JSON
        text = raw.strip()
        start = text.find("[")
        end = text.rfind("]")
        if start != -1 and end != -1 and end > start:
            text = text[start:end+1]
        elif text.startswith("```"):
            lines = text.split("\n")
            text = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])

        questions_raw = json.loads(text)
        if not isinstance(questions_raw, list):
            raise ValueError("Expected JSON array")

        # Assign question_ids and validate structure
        questions = []
        for n, q in enumerate(questions_raw[:3]):  # max 3
            question_id = f"{sub_topic}_{cycle_id}_{n}"
            questions.append({
                "question_id":    question_id,
                "question":       str(q.get("question", "")),
                "options":        list(q.get("options", [])),
                "correct_answer": str(q.get("correct_answer", "")),
                "explanation":    str(q.get("explanation", "")),
            })

        return questions

    except FeatherlessAllKeysFailedError as exc:
        logger.error("Quiz generation failed (all keys): %s", exc)
        return []
    except Exception as exc:
        logger.error("Quiz generation parse/call error: %s", exc)
        return []


def _generate_recommendation(
    skill: str,
    sub_topic: str,
    category: str,
    signal_summary: str,
) -> str:
    """
    Generate a 2-3 sentence targeted learning resource pointer via Featherless.ai.
    Returns plain text. No quiz generation.
    """
    system_prompt = f"""You are an expert learning advisor for software professionals.
A learner's skill signals indicate they need targeted review of:
  Skill: {skill}
  Sub-topic: {sub_topic} (type: {category})
  Signal context: {signal_summary}

Generate a concise 2-3 sentence learning recommendation that:
1. Names a specific, concrete resource (book chapter, official docs section, specific tutorial)
2. Explains WHY this sub-topic needs review based on the signals
3. Suggests a specific hands-on exercise or practice pattern

Respond in plain English only — no JSON, no headers, just the recommendation paragraph."""

    try:
        text = chat_complete(
            messages=[{"role": "system", "content": system_prompt}],
            temperature=0.5,
            max_tokens=300,
            call_site="action_layer_recommend",
        )
        return text.strip()

    except FeatherlessAllKeysFailedError as exc:
        logger.error("Recommendation generation failed (all keys): %s", exc)
        return (
            f"[Recommendation generation failed] Review {skill}/{sub_topic} "
            f"fundamentals — API call failed."
        )
    except Exception as exc:
        logger.error("Recommendation generation error: %s", exc)
        return f"[Recommendation generation error] Review {skill}/{sub_topic}."


def _signal_summary_for_action(bundle: dict) -> str:
    """Build a brief signal summary string for LLM prompts."""
    kt = bundle.get("knowledge_tracking", {})
    decay_info = bundle.get("decay", {})
    quiz_info = bundle.get("quiz", {})
    return (
        f"mode={kt.get('mode','?')}, "
        f"knowledge_prob={kt.get('knowledge_probability','null')}, "
        f"decay_score={decay_info.get('decay_score','?')} "
        f"({decay_info.get('days_since_last_use','?')} days since last use), "
        f"recent_accuracy={quiz_info.get('recent_accuracy','null')}"
    )


def run_action_layer(
    decisions: list[dict],
    signal_bundle: dict,
    db,  # SQLAlchemy session, used to persist quiz_cycles
    user_id: str,
) -> dict:
    """
    For each decision, execute the appropriate action (§8).

    Returns:
        {
            sub_topic: {
                "action": ...,
                "reason": ...,
                "quiz": [front-end safe questions, no correct_answer] | None,
                "cycle_id": str | None,
                "recommendation": str | None,
            }
        }

    §8.1: test_now_calls ≤ 3, recommend_calls ≤ 3 (enforced here, beyond what decision_agent capped)
    A failure on one sub-topic's call must NOT abort other sub-topics.
    """
    from backend.database import QuizCycle
    from datetime import datetime

    # Build a fast lookup: sub_topic → signal bundle
    flat_bundle: dict[str, dict] = {}
    for skill_data in signal_bundle.values():
        for st, bdata in skill_data.items():
            flat_bundle[st] = bdata

    test_now_calls = 0
    recommend_calls = 0
    results: dict = {}

    for decision in decisions:
        sub_topic = decision["subtopic"].strip()
        if "/" in sub_topic:
            sub_topic = sub_topic.split("/")[-1].strip()
        action    = decision["action"]
        reason    = decision["reason"]
        bundle    = flat_bundle.get(sub_topic, {})
        skill     = bundle.get("skill", "Unknown")
        category  = bundle.get("category", "procedural")
        signal_summary = _signal_summary_for_action(bundle)

        entry: dict = {
            "action": action,
            "reason": reason,
            "quiz": None,
            "cycle_id": None,
            "recommendation": None,
        }

        if action == "TEST_NOW":
            if test_now_calls >= MAX_TEST_NOW_CALLS:
                # §8.1 secondary cap: downgrade excess to placeholder
                logger.warning(
                    "TEST_NOW cap (%d) exceeded for %s — returning placeholder",
                    MAX_TEST_NOW_CALLS, sub_topic
                )
                entry["action"] = "WAIT"
                entry["reason"] = (
                    f"[Capped by §8.1: max {MAX_TEST_NOW_CALLS} quiz-generation calls/cycle] "
                    + reason
                )
            else:
                test_now_calls += 1
                cycle_id = str(uuid.uuid4())
                questions = _generate_quiz(skill, sub_topic, category, cycle_id, signal_summary)

                if questions:
                    # Persist to quiz_cycles (including correct answers — server-side only)
                    try:
                        from backend.database import get_simulated_now
                        now = get_simulated_now(db)
                        db.add(QuizCycle(
                            cycle_id=cycle_id,
                            user_id=user_id,
                            skill=skill,
                            sub_topic=sub_topic,
                            questions=questions,  # full questions with answers
                            created_at=now,
                            consumed=False,
                        ))
                        db.flush()
                    except Exception as exc:
                        logger.error("Failed to persist quiz_cycle: %s", exc)

                    # Return questions WITHOUT correct_answer to frontend
                    safe_questions = [
                        {
                            "question_id": q["question_id"],
                            "question":    q["question"],
                            "options":     q["options"],
                        }
                        for q in questions
                    ]
                    entry["quiz"] = safe_questions
                    entry["cycle_id"] = cycle_id
                else:
                    entry["quiz"] = []
                    entry["cycle_id"] = cycle_id
                    entry["action"] = "TEST_NOW"
                    entry["reason"] = reason + " [Quiz generation failed — please retry]"

        elif action == "RECOMMEND":
            if recommend_calls >= MAX_RECOMMEND_CALLS:
                # §8.1 secondary cap on recommend calls
                logger.warning(
                    "RECOMMEND cap (%d) exceeded for %s — returning placeholder",
                    MAX_RECOMMEND_CALLS, sub_topic
                )
                entry["recommendation"] = (
                    f"[Recommendation generation deferred — max {MAX_RECOMMEND_CALLS} "
                    f"calls/cycle reached] Review {skill}/{sub_topic} when you have time."
                )
            else:
                recommend_calls += 1
                entry["recommendation"] = _generate_recommendation(
                    skill, sub_topic, category, signal_summary
                )

        elif action == "ESCALATE":
            # §8: no generation call; just flag it — escalated=TRUE set by graph
            pass

        elif action == "WAIT":
            # §8: no generation call
            pass

        results[sub_topic] = entry

    return results

"""
decision_agent.py — LLM call #1: Decision Agent (Featherless.ai).

Responsibility boundary (§2):
  - Reads the full 10-sub-topic signal bundle
  - Decides action + reason per sub-topic, weighing all sub-topics against each other
  - Returns structured JSON array
  MUST NOT: generate quizzes/resources; recalculate signals; be the only decision-maker

§7.1 Cap: at most 3 sub-topics can receive TEST_NOW per cycle. Stated in prompt
  AND enforced in backend as a secondary guard.
§7 Retry: on malformed JSON, retry once; if still malformed → WAIT fallback.
§7 Routing: downstream routing is on `action` field only, never on `reason` text.
"""

import json
import logging
from typing import Optional

from backend.services.featherless_client import chat_complete, FeatherlessAllKeysFailedError

logger = logging.getLogger(__name__)

# §7.1: Max simultaneous TEST_NOW actions per cycle
MAX_TEST_NOW_PER_CYCLE: int = 3
# §8.1: Max RECOMMEND generation calls per cycle
MAX_RECOMMEND_PER_CYCLE: int = 3

VALID_ACTIONS = {"TEST_NOW", "WAIT", "RECOMMEND", "ESCALATE"}


def _build_decision_prompt(signal_bundle: dict, escalated_subtopics: list[str]) -> str:
    """Build the system + user message for the Decision Agent."""

    # Flatten bundle for LLM consumption
    bundle_lines = []
    for skill, subtopics in signal_bundle.items():
        for sub_topic, data in subtopics.items():
            if "error" in data:
                continue
            kt = data.get("knowledge_tracking", {})
            decay_info = data.get("decay", {})
            quiz_info = data.get("quiz", {})
            escalated = data.get("escalated", False)
            parts = [
                f"[{skill} / {sub_topic}] (category: {data.get('category','?')})",
                f"  mode={kt.get('mode','?')}",
                f"  knowledge_prob={kt.get('knowledge_probability','null')}",
                f"  obs_count={kt.get('observation_count',0)}",
                f"  decay_score={decay_info.get('decay_score','?')} (days_since={decay_info.get('days_since_last_use','?')})",
                f"  recent_usage={data.get('usage',{}).get('recent_usage',False)}",
                f"  recent_accuracy={quiz_info.get('recent_accuracy','null')}",
            ]
            if escalated:
                parts.append(
                    "  *** ESCALATED from prior cycle — weight as higher priority "
                    "unless evidence has clearly improved ***"
                )
            bundle_lines.append("\n".join(parts))

    bundle_text = "\n\n".join(bundle_lines)

    system_prompt = f"""You are the Decision Agent for Skill Decay Alerts (SDA), an agentic system that helps professionals maintain their technical skills.

Your job is to analyze a learner's sub-topic signal bundle and decide what action to take for EACH sub-topic. You must weigh all sub-topics against each other to prioritize — do NOT threshold-check each sub-topic independently.

ACTIONS available per sub-topic:
- TEST_NOW: the learner should take a quiz immediately (high decay OR low knowledge OR escalated)
- WAIT: signals are acceptable; no action needed now
- RECOMMEND: suggest a targeted learning resource (moderate concern but not urgent enough to test)
- ESCALATE: critical decay/low mastery that has been ignored; flag for priority attention

CRITICAL CONSTRAINT: You may select at most {MAX_TEST_NOW_PER_CYCLE} sub-topics for TEST_NOW per cycle.
If you identify more than {MAX_TEST_NOW_PER_CYCLE} candidates for TEST_NOW, select the {MAX_TEST_NOW_PER_CYCLE} most urgent and assign WAIT or RECOMMEND to the rest.
State your ranking reasoning explicitly.

ESCALATED sub-topics (marked ***) were flagged in a prior cycle and received no improvement. Weight them as higher priority unless their signals clearly show recent improvement.

OUTPUT FORMAT: Respond ONLY with a valid JSON array (no markdown, no commentary) like:
[
  {{"subtopic": "syntax_and_core_libraries", "action": "TEST_NOW", "reason": "high decay (0.87) and no recent usage in 3 days; most urgent of all sub-topics"}},
  ...
]

Each element must have exactly: "subtopic" (string), "action" (one of TEST_NOW/WAIT/RECOMMEND/ESCALATE), "reason" (plain English, 1-2 sentences explaining the decision in context of the whole bundle).
"""

    user_prompt = f"""Here is the full 10-sub-topic signal bundle for this learner:

{bundle_text}

Analyze all sub-topics together. Decide action + reason for each. Return ONLY the JSON array."""

    return system_prompt, user_prompt


def _parse_decision_response(raw: str) -> Optional[list[dict]]:
    """Parse and validate the LLM's JSON response. Returns None if invalid."""
    try:
        # Extract JSON array substring if present
        text = raw.strip()
        start = text.find("[")
        end = text.rfind("]")
        if start != -1 and end != -1 and end > start:
            text = text[start:end+1]
        elif text.startswith("```"):
            lines = text.split("\n")
            text = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])

        parsed = json.loads(text)
        if not isinstance(parsed, list):
            return None
        validated = []
        for item in parsed:
            if not isinstance(item, dict):
                continue
            action = item.get("action", "").strip().upper()
            if action not in VALID_ACTIONS:
                continue
            st = str(item.get("subtopic", "")).strip()
            if "/" in st:
                st = st.split("/")[-1].strip()
            validated.append({
                "subtopic": st,
                "action": action,
                "reason": str(item.get("reason", "")),
            })
        return validated if validated else None
    except (json.JSONDecodeError, Exception) as exc:
        logger.warning("Decision Agent JSON parse failed: %s. Raw was: %r", exc, raw[:300])
        return None


def _apply_test_now_cap(decisions: list[dict]) -> list[dict]:
    """
    §7.1: Cap TEST_NOW at MAX_TEST_NOW_PER_CYCLE.
    Keep the first N in returned order (model was instructed to rank).
    Downgrade excess to WAIT with amended reason.
    """
    test_now_count = 0
    result = []
    for d in decisions:
        if d["action"] == "TEST_NOW":
            if test_now_count < MAX_TEST_NOW_PER_CYCLE:
                test_now_count += 1
                result.append(d)
            else:
                # Downgrade: exceeds cap
                result.append({
                    "subtopic": d["subtopic"],
                    "action": "WAIT",
                    "reason": (
                        f"[Downgraded from TEST_NOW by §7.1 cap (max {MAX_TEST_NOW_PER_CYCLE}/cycle)] "
                        + d["reason"]
                    ),
                })
        else:
            result.append(d)
    return result


def run_decision_agent(
    signal_bundle: dict,
    user_id: str,
) -> list[dict]:
    """
    Run the Decision Agent (LLM call #1).

    Returns list of {subtopic, action, reason} dicts — one per sub-topic.
    On complete failure, returns WAIT for all sub-topics with reason='decision_agent_failure'.
    """
    # Collect escalated sub-topics for prompt context
    escalated = [
        st
        for skill_data in signal_bundle.values()
        for st, bundle in skill_data.items()
        if bundle.get("escalated", False)
    ]

    system_prompt, user_prompt = _build_decision_prompt(signal_bundle, escalated)

    decisions: Optional[list[dict]] = None

    for attempt in range(2):  # §7: retry once on malformed JSON
        try:
            raw = chat_complete(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.2,
                max_tokens=1024,
                call_site="decision_agent",
            )
            decisions = _parse_decision_response(raw)
            if decisions is not None:
                break
            logger.warning(
                "Decision Agent attempt %d/%d: malformed JSON, %s",
                attempt + 1, 2, "retrying" if attempt == 0 else "falling back"
            )
        except FeatherlessAllKeysFailedError as exc:
            logger.error("Decision Agent: all keys failed: %s", exc)
            decisions = None
            break

    if decisions is None:
        # §7 fallback: WAIT for every sub-topic, log the failure
        logger.error(
            "Decision Agent: returning WAIT fallback for all sub-topics (parse failure or API error)"
        )
        decisions = [
            {
                "subtopic": st,
                "action": "WAIT",
                "reason": "decision_agent_parse_failure",
            }
            for skill_data in signal_bundle.values()
            for st in skill_data
        ]

    # §7.1 cap enforcement (secondary guard — model was already instructed)
    decisions = _apply_test_now_cap(decisions)

    return decisions

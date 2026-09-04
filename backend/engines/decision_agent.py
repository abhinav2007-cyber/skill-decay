"""
decision_agent.py — Decision Agent (§7), Featherless.ai call #1.

Responsibilities:
  - Receives the full 10-sub-topic signal bundle
  - Calls Featherless.ai (distinct call site from action_layer and strength_report)
  - Returns structured JSON: [{subtopic, action, reason}, ...]
  - Enforces the §7.1 cap of 3 simultaneous TEST_NOW actions
  - On malformed JSON: retries once, then falls back to WAIT for failed entries
  - Never crashes the graph (§11.5)

Must NOT generate quizzes or resources — that is the Agent Action Layer's job.
"""

import json
import logging
import re
from typing import Any

from backend.services.featherless_client import featherless_chat

logger = logging.getLogger(__name__)

VALID_ACTIONS = {"TEST_NOW", "WAIT", "RECOMMEND", "ESCALATE"}
# §7.1: cap on simultaneous TEST_NOW actions per cycle
MAX_TEST_NOW_PER_CYCLE = 3
# Same cap for RECOMMEND generation calls (§8.1)
MAX_RECOMMEND_PER_CYCLE = 3

SYSTEM_PROMPT = """You are an adaptive learning agent called Skill Decay Alerts (SDA).
You receive a bundle of signals for 10 skill sub-topics belonging to a professional learner.

Your job: decide ONE action for EACH sub-topic, reasoning across all sub-topics relative to each other.
Do NOT threshold-check each sub-topic independently — weigh them against each other and prioritize.

Available actions:
- TEST_NOW: Learner needs an immediate quiz. Use when decay is high AND evidence is weak/stale.
- RECOMMEND: Learner needs a refresher resource/explanation. Use for moderate risk where a quiz would be premature.
- WAIT: No urgent action needed. Use when signals are healthy or very recently addressed.
- ESCALATE: Learner's skill has critically decayed and they haven't engaged despite prior alerts. Reserve for the worst cases.

IMPORTANT CONSTRAINT: You may assign TEST_NOW to AT MOST 3 sub-topics in this response.
Prioritize which 3 matter most — do not spread TEST_NOW across more than 3, even if multiple sub-topics look risky.

If a sub-topic has escalated=true in its bundle, weight it as higher priority unless its signals have clearly improved.

Respond with ONLY a valid JSON array — no markdown, no explanation outside the JSON.
Each element must have exactly these fields:
  {"subtopic": "<sub_topic_key>", "action": "<ACTION>", "reason": "<plain English explanation>"}

Example:
[
  {"subtopic": "sql_queries_and_joins", "action": "TEST_NOW", "reason": "Decay score 0.82 with only 2 recent answers; procedural skill degrades fastest."},
  {"subtopic": "oop_and_design_patterns", "action": "WAIT", "reason": "Knowledge probability 0.78 and recently used — no urgent action."}
]
"""


def _extract_json_array(text: str) -> list | None:
    """Attempt to extract a JSON array from possibly-markdown-wrapped LLM output."""
    # Strip markdown code fences
    text = re.sub(r"```(?:json)?", "", text).strip()
    # Find first '[' and last ']'
    start = text.find("[")
    end = text.rfind("]")
    if start == -1 or end == -1:
        return None
    try:
        return json.loads(text[start : end + 1])
    except json.JSONDecodeError:
        return None


def _validate_decisions(raw: list) -> tuple[list[dict], list[str]]:
    """
    Validate each decision entry. Returns (valid_decisions, failed_subtopics).
    Ensures action is in VALID_ACTIONS.
    """
    valid = []
    failed = []
    seen_subtopics = set()
    for item in raw:
        try:
            if not isinstance(item, dict):
                raise ValueError("not a dict")
            st = str(item.get("subtopic", "")).strip()
            action = str(item.get("action", "")).strip().upper()
            reason = str(item.get("reason", "")).strip()
            if not st or action not in VALID_ACTIONS:
                raise ValueError(f"invalid subtopic='{st}' or action='{action}'")
            if st in seen_subtopics:
                continue  # deduplicate
            seen_subtopics.add(st)
            valid.append({"subtopic": st, "action": action, "reason": reason})
        except Exception as exc:
            logger.warning("Decision entry validation failed: %s — %s", item, exc)
            failed.append(str(item.get("subtopic", "unknown")))
    return valid, failed


def _apply_test_now_cap(decisions: list[dict]) -> list[dict]:
    """
    §7.1 — Keep at most MAX_TEST_NOW_PER_CYCLE TEST_NOW actions.
    The Decision Agent is instructed to self-limit, but we enforce the cap
    server-side as a hard guarantee. Excess TEST_NOW actions are downgraded to WAIT.
    """
    test_now_count = 0
    result = []
    for d in decisions:
        if d["action"] == "TEST_NOW":
            if test_now_count < MAX_TEST_NOW_PER_CYCLE:
                test_now_count += 1
                result.append(d)
            else:
                # Downgrade and amend reason
                result.append({
                    "subtopic": d["subtopic"],
                    "action": "WAIT",
                    "reason": (
                        f"[Cap applied: §7.1 limits TEST_NOW to {MAX_TEST_NOW_PER_CYCLE} "
                        f"per cycle; original decision was TEST_NOW with reason: {d['reason']}]"
                    ),
                })
        else:
            result.append(d)
    return result


async def run_decision_agent(signal_bundle: dict) -> list[dict]:
    """
    §7 — Run the Decision Agent against the full signal bundle.

    Parameters
    ----------
    signal_bundle : the nested dict from get_signal_bundle() (§6.5 shape)

    Returns
    -------
    list of {subtopic, action, reason} — one per sub-topic that could be parsed;
    sub-topics that failed to parse fall back to WAIT with a diagnostic reason.
    """
    # Flatten the nested bundle into a list for the prompt
    flat_bundle = []
    for skill, sub_topics in signal_bundle.items():
        for sub_topic, entry in sub_topics.items():
            flat_bundle.append({
                "skill": skill,
                **entry,  # includes all §6.4 fields + escalated
            })

    user_message = (
        "Here is the current signal bundle for the learner's 10 sub-topics:\n\n"
        + json.dumps(flat_bundle, indent=2)
        + "\n\nDecide the action for EACH sub-topic. Return a JSON array as described."
    )

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_message},
    ]

    raw_decisions: list | None = None
    last_error: Exception | None = None

    # One attempt + one retry on malformed JSON (§7)
    for attempt in range(2):
        try:
            response_text = await featherless_chat(
                messages, call_site="decision_agent", max_tokens=2000
            )
            raw_decisions = _extract_json_array(response_text)
            if raw_decisions is not None:
                break
            logger.warning(
                "Decision Agent attempt %d returned non-parseable JSON: %s",
                attempt + 1,
                response_text[:300],
            )
        except Exception as exc:
            logger.error("Decision Agent call failed on attempt %d: %s", attempt + 1, exc)
            last_error = exc
            break  # Don't retry on full API failure, only on parse failure

    # All sub-topics that appear in the bundle
    all_subtopics = [
        entry["sub_topic"]
        for sub_topics in signal_bundle.values()
        for entry in sub_topics.values()
    ]

    if raw_decisions is None:
        # Total failure — fall back WAIT for every sub-topic
        logger.error(
            "Decision Agent failed entirely (parse failure or API error). "
            "Falling back to WAIT for all sub-topics."
        )
        return [
            {
                "subtopic": st,
                "action": "WAIT",
                "reason": "decision_agent_parse_failure",
            }
            for st in all_subtopics
        ]

    valid_decisions, failed_subtopics = _validate_decisions(raw_decisions)

    # Add WAIT fallback for any sub-topic not covered by valid decisions
    covered = {d["subtopic"] for d in valid_decisions}
    for st in all_subtopics:
        if st not in covered:
            valid_decisions.append({
                "subtopic": st,
                "action": "WAIT",
                "reason": "decision_agent_parse_failure",
            })

    # Apply §7.1 TEST_NOW cap
    capped = _apply_test_now_cap(valid_decisions)

    logger.info(
        "Decision Agent: %d valid decisions, %d TEST_NOW (after cap)",
        len(capped),
        sum(1 for d in capped if d["action"] == "TEST_NOW"),
    )
    return capped

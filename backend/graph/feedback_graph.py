"""
feedback_graph.py — LangGraph Feedback Engine (§11).

The graph is the orchestrator. It does NOT reimplement decay, BKT, or decision logic.
It calls the other components and owns state, node sequencing, routing, and persistence.

Two invocation patterns (§11.1):
  Invocation 1 — POST /cycle:
    update_signals → decide → route_decision → act

  Invocation 2 — POST /answer (after grading):
    grade → update_signals → decide → route_decision → act

Each invocation is a complete, synchronous graph run. No mid-graph pause, no interrupt().
"""

import json
import logging
from typing import Any, Literal, Optional
from typing_extensions import TypedDict

from langgraph.graph import StateGraph, END

from backend.engines import signal_engine, decision_agent, action_layer, grading_engine

logger = logging.getLogger(__name__)


# ── Graph state schema (§11.2) ─────────────────────────────────────────────────
class SDAState(TypedDict, total=False):
    user_id: str
    skill: Optional[str]     # set only for invocation 2's grade node
    sub_topic: Optional[str] # set only for invocation 2's grade node

    # Payload for invocation 2
    question_id: Optional[str]
    selected_option: Optional[str]
    cycle_id: Optional[str]

    # §11.2 state fields
    current_signals: dict        # §6.4 bundle shape, verbatim
    agent_decisions: list        # [{subtopic, action, reason}, ...]
    action_results: list         # [{subtopic, action, reason, quiz?, recommendation?}, ...]
    grade_result: Optional[dict] # grading outcome

    workflow_status: str         # "ok" | "error"
    error_information: Optional[str]

    # Internal routing
    _invocation_type: str        # "cycle" | "answer"


# ── Nodes ─────────────────────────────────────────────────────────────────────

async def node_update_signals(state: SDAState) -> dict:
    """
    update_signals node (§11.3) — calls Signal Engine only.
    Never reimplements decay or BKT.
    """
    user_id = state.get("user_id", "demo_user")
    logger.info("[graph] update_signals for user=%s", user_id)
    try:
        bundle = signal_engine.get_signal_bundle(user_id)
        return {"current_signals": bundle, "workflow_status": "ok"}
    except Exception as exc:
        logger.error("[graph] update_signals failed: %s", exc)
        return {
            "workflow_status": "error",
            "error_information": f"Signal Engine failure: {exc}",
            "current_signals": {},
        }


async def node_decide(state: SDAState) -> dict:
    """
    decide node (§11.3) — calls Decision Agent only. Never a second decision LLM.
    """
    user_id = state.get("user_id", "demo_user")
    bundle = state.get("current_signals", {})
    logger.info("[graph] decide for user=%s", user_id)

    if state.get("workflow_status") == "error":
        logger.warning("[graph] Skipping decide due to upstream error")
        return {}

    try:
        decisions = await decision_agent.run_decision_agent(bundle)
        return {"agent_decisions": decisions}
    except Exception as exc:
        logger.error("[graph] decide node failed: %s", exc)
        return {
            "workflow_status": "error",
            "error_information": f"Decision Agent failure: {exc}",
        }


def node_route_decision(state: SDAState) -> Literal["act", "error_end"]:
    """
    route_decision node (§11.3) — reads workflow_status, branches to act or error_end.
    Unrecognized actions are handled inside action_layer, not here.
    """
    if state.get("workflow_status") == "error":
        return "error_end"
    decisions = state.get("agent_decisions", [])
    if not decisions:
        logger.warning("[graph] No decisions to route — going to error_end")
        return "error_end"
    return "act"


async def node_act(state: SDAState) -> dict:
    """
    act node (§11.3) — calls Agent Action Layer per branch.
    A failure on one sub-topic's call must NOT abort other sub-topics' results.
    """
    user_id = state.get("user_id", "demo_user")
    decisions = state.get("agent_decisions", [])
    bundle = state.get("current_signals", {})
    logger.info("[graph] act node: %d decisions to execute", len(decisions))
    try:
        results = await action_layer.execute_actions(user_id, decisions, bundle)
        return {"action_results": results, "workflow_status": "ok"}
    except Exception as exc:
        logger.error("[graph] act node failed: %s", exc)
        return {
            "workflow_status": "error",
            "error_information": f"Agent Action Layer failure: {exc}",
            "action_results": [],
        }


async def node_grade(state: SDAState) -> dict:
    """
    grade node (§11.3, §10.1) — only present in invocation 2.
    Calls grading_engine, not reimplements it.
    """
    user_id = state.get("user_id", "demo_user")
    cycle_id = state.get("cycle_id")
    question_id = state.get("question_id")
    selected_option = state.get("selected_option")
    logger.info("[graph] grade node for cycle=%s question=%s", cycle_id, question_id)
    try:
        result = grading_engine.grade_response(
            user_id=user_id,
            cycle_id=cycle_id,
            question_id=question_id,
            selected_option=selected_option,
        )
        return {"grade_result": result}
    except grading_engine.GradingError as exc:
        logger.warning("[graph] grade node controlled error: %s", exc)
        return {
            "workflow_status": "error",
            "error_information": str(exc),
        }
    except Exception as exc:
        logger.error("[graph] grade node unexpected error: %s", exc)
        return {
            "workflow_status": "error",
            "error_information": f"Grading failure: {exc}",
        }


async def node_error_end(state: SDAState) -> dict:
    """Terminal node for error paths — ensures clean state, no corrupted actions."""
    logger.error("[graph] Reached error_end: %s", state.get("error_information"))
    return {}


# ── Graph builder ─────────────────────────────────────────────────────────────

def _build_cycle_graph() -> Any:
    """
    Invocation 1 graph: update_signals → decide → route_decision → act | error_end
    """
    g = StateGraph(SDAState)
    g.add_node("update_signals", node_update_signals)
    g.add_node("decide", node_decide)
    g.add_node("act", node_act)
    g.add_node("error_end", node_error_end)

    g.set_entry_point("update_signals")
    g.add_edge("update_signals", "decide")
    g.add_conditional_edges(
        "decide",
        node_route_decision,
        {"act": "act", "error_end": "error_end"},
    )
    g.add_edge("act", END)
    g.add_edge("error_end", END)
    return g.compile()


def _build_answer_graph() -> Any:
    """
    Invocation 2 graph: grade → update_signals → decide → route_decision → act | error_end
    """
    g = StateGraph(SDAState)
    g.add_node("grade", node_grade)
    g.add_node("update_signals", node_update_signals)
    g.add_node("decide", node_decide)
    g.add_node("act", node_act)
    g.add_node("error_end", node_error_end)

    g.set_entry_point("grade")
    g.add_edge("grade", "update_signals")
    g.add_edge("update_signals", "decide")
    g.add_conditional_edges(
        "decide",
        node_route_decision,
        {"act": "act", "error_end": "error_end"},
    )
    g.add_edge("act", END)
    g.add_edge("error_end", END)
    return g.compile()


# Compiled graphs (constructed once)
_cycle_graph = _build_cycle_graph()
_answer_graph = _build_answer_graph()


# ── Public entrypoints ─────────────────────────────────────────────────────────

async def run_cycle(user_id: str) -> dict:
    """
    Invocation 1: POST /cycle.
    Returns action results + agent decisions (with reasoning).
    """
    initial_state: SDAState = {
        "user_id": user_id,
        "workflow_status": "ok",
        "_invocation_type": "cycle",
    }
    final_state = await _cycle_graph.ainvoke(initial_state)
    return _format_output(final_state)


async def run_answer(
    user_id: str,
    cycle_id: str,
    question_id: str,
    selected_option: str,
) -> dict:
    """
    Invocation 2: POST /answer.
    Grades the response, then re-runs decide→act on updated signals.
    """
    initial_state: SDAState = {
        "user_id": user_id,
        "cycle_id": cycle_id,
        "question_id": question_id,
        "selected_option": selected_option,
        "workflow_status": "ok",
        "_invocation_type": "answer",
    }
    final_state = await _answer_graph.ainvoke(initial_state)
    return _format_output(final_state)


def _format_output(state: SDAState) -> dict:
    """Convert graph final state to API-friendly response dict."""
    return {
        "workflow_status": state.get("workflow_status", "unknown"),
        "error_information": state.get("error_information"),
        "action_results": state.get("action_results", []),
        "current_signals": state.get("current_signals", {}),
        "grade_result": state.get("grade_result"),
    }

"""
feedback_engine.py — LangGraph orchestration of the decide → act → observe → re-decide loop.

§11 Architecture:
  - Real, inspectable LangGraph StateGraph (NOT hand-chained function calls)
  - Two distinct invocations:
      Invocation 1 (POST /cycle): update_signals → decide → route_decision → act
      Invocation 2 (POST /answer): grade → update_signals → decide → route_decision → act
  - No mid-graph pause (§11.1): every node returns synchronously
  - LangGraph calls the other components; it does NOT reimplement their logic (§11)

Nodes:
  update_signals  — calls Signal Engine
  decide          — calls Decision Agent (LLM #1)
  route_decision  — reads action, branches
  act             — calls Agent Action Layer (LLM #2)
  grade           — calls grading service (invocation 2 only)
"""

import logging
from typing import Any, Optional, Annotated
from typing_extensions import TypedDict

from langgraph.graph import StateGraph, END
import operator

logger = logging.getLogger(__name__)


# ── State definition (§11.2) ───────────────────────────────────────────────────

class SDAState(TypedDict, total=False):
    """Per-invocation state. Exactly the §11.2 shape."""
    user_id: str
    # Invocation 2 inputs
    sub_topic: Optional[str]
    question_id: Optional[str]
    selected_option: Optional[str]
    cycle_id: Optional[str]

    # Signal Engine output (§6.4 bundle shape, verbatim)
    current_signals: dict

    # Decision Agent output
    agent_decisions: list     # [{subtopic, action, reason}, ...]

    # Action Layer output
    action_results: dict      # {sub_topic: {action, reason, quiz, cycle_id, recommendation}}

    # Grading output (invocation 2)
    grade_result: Optional[dict]

    # Workflow status and error tracking
    workflow_status: str      # "running" | "complete" | "error"
    error_information: Optional[str]


# ── Node implementations ───────────────────────────────────────────────────────

def node_update_signals(state: SDAState, db) -> SDAState:
    """
    §11.3: Calls Signal Engine to recalculate all sub-topic signals.
    MUST NOT reimplement decay or BKT — delegates to signal_engine.py.
    """
    from backend.services.signal_engine import get_signal_bundle

    try:
        signals = get_signal_bundle(db, state["user_id"])
        return {**state, "current_signals": signals, "workflow_status": "running"}
    except Exception as exc:
        logger.error("update_signals node failed: %s", exc)
        return {
            **state,
            "workflow_status": "error",
            "error_information": f"Signal Engine failure: {exc}",
        }


def node_decide(state: SDAState, db) -> SDAState:
    """
    §11.3: Calls Decision Agent (LLM #1).
    MUST NOT be a second decision LLM or make any action itself.
    """
    from backend.services.decision_agent import run_decision_agent
    from backend.database import SubTopicState

    if state.get("workflow_status") == "error":
        return state  # propagate error, skip node

    try:
        signals = state.get("current_signals", {})
        decisions = run_decision_agent(signals, state["user_id"])

        # §9 ESCALATE mechanism: update escalated flag in DB based on decisions
        # De-escalate sub-topics that got an action OTHER than ESCALATE
        # Set escalated=True for sub-topics that got ESCALATE
        for d in decisions:
            sub_topic = d["subtopic"]
            action = d["action"]
            # Find the skill for this sub-topic
            skill = None
            for s, subs in signals.items():
                if sub_topic in subs:
                    skill = s
                    break
            if skill is None:
                continue

            state_row = db.query(SubTopicState).filter_by(
                user_id=state["user_id"], skill=skill, sub_topic=sub_topic
            ).first()
            if state_row is not None:
                if action == "ESCALATE":
                    state_row.escalated = True
                else:
                    state_row.escalated = False  # de-escalate: it was addressed
                # Store last decision
                state_row.last_decision_action = action
                state_row.last_decision_reason = d["reason"]
        db.flush()

        return {**state, "agent_decisions": decisions, "workflow_status": "running"}
    except Exception as exc:
        logger.error("decide node failed: %s", exc)
        return {
            **state,
            "workflow_status": "error",
            "error_information": f"Decision Agent failure: {exc}",
        }


def node_route_decision(state: SDAState) -> str:
    """
    §11.3: Reads action field, returns branch name.
    Unrecognized action → controlled error (never silently default-routed).
    Routing happens on action field ONLY — never on reason text (§7).
    """
    if state.get("workflow_status") == "error":
        return "error_exit"

    decisions = state.get("agent_decisions", [])
    if not decisions:
        return "error_exit"

    # Collect all unique actions in this decision set
    actions = {d["action"] for d in decisions}

    # Route: if any action needs generation → go to act node
    # (act node handles per-sub-topic branching internally)
    if actions & {"TEST_NOW", "RECOMMEND", "ESCALATE", "WAIT"}:
        return "act"

    # Unknown actions → controlled error
    unknown = actions - {"TEST_NOW", "RECOMMEND", "ESCALATE", "WAIT"}
    if unknown:
        logger.error("Unrecognized action(s) in decisions: %s", unknown)
        return "error_exit"

    return "act"


def node_act(state: SDAState, db) -> SDAState:
    """
    §11.3: Calls Agent Action Layer (LLM #2) per branch.
    MUST NOT make the decision itself.
    A failure on one sub-topic's call must not abort others.
    """
    from backend.services.action_layer import run_action_layer

    if state.get("workflow_status") == "error":
        return state

    try:
        results = run_action_layer(
            decisions=state.get("agent_decisions", []),
            signal_bundle=state.get("current_signals", {}),
            db=db,
            user_id=state["user_id"],
        )
        return {**state, "action_results": results, "workflow_status": "complete"}
    except Exception as exc:
        logger.error("act node failed: %s", exc)
        return {
            **state,
            "workflow_status": "error",
            "error_information": f"Agent Action Layer failure: {exc}",
        }


def node_grade(state: SDAState, db) -> SDAState:
    """
    §11.3: Grading node — invocation 2 only.
    Calls grading service, writes quiz_responses row.
    """
    from backend.services.grading import grade_answer, GradingError

    try:
        is_correct, explanation = grade_answer(
            db=db,
            user_id=state["user_id"],
            sub_topic=state.get("sub_topic", ""),
            question_id=state.get("question_id", ""),
            selected_option=state.get("selected_option", ""),
            cycle_id=state.get("cycle_id", ""),
        )
        return {
            **state,
            "grade_result": {
                "correct": is_correct,
                "explanation": explanation,
            },
            "workflow_status": "running",
        }
    except GradingError as exc:
        logger.warning("Grading validation error: %s (code=%s)", exc, exc.code)
        raise  # Re-raise so FastAPI layer can return a 400 with exc.code
    except Exception as exc:
        logger.error("grade node unexpected failure: %s", exc)
        return {
            **state,
            "workflow_status": "error",
            "error_information": f"Grading failure: {exc}",
        }


def node_error_exit(state: SDAState) -> SDAState:
    """Controlled error terminal node — logs and preserves state without corruption."""
    logger.error(
        "Workflow reached error_exit. error_information=%s",
        state.get("error_information")
    )
    return {**state, "workflow_status": "error"}


# ── Graph builders ─────────────────────────────────────────────────────────────

def _build_graph_invocation1(db):
    """
    Invocation 1: update_signals → decide → route_decision → act
    Called by POST /cycle.
    Returns a compiled LangGraph graph.
    """
    graph = StateGraph(SDAState)

    # Register nodes with db bound via closure
    graph.add_node("update_signals", lambda s: node_update_signals(s, db))
    graph.add_node("decide",         lambda s: node_decide(s, db))
    graph.add_node("act",            lambda s: node_act(s, db))
    graph.add_node("error_exit",     node_error_exit)

    # Edges
    graph.set_entry_point("update_signals")
    graph.add_edge("update_signals", "decide")
    graph.add_conditional_edges(
        "decide",
        node_route_decision,
        {
            "act":        "act",
            "error_exit": "error_exit",
        }
    )
    graph.add_edge("act",        END)
    graph.add_edge("error_exit", END)

    return graph.compile()


def _build_graph_invocation2(db):
    """
    Invocation 2: grade → update_signals → decide → route_decision → act
    Called by POST /answer.
    Reads SubTopicState (written by invocation 1 and by grading) as input.
    """
    graph = StateGraph(SDAState)

    graph.add_node("grade",          lambda s: node_grade(s, db))
    graph.add_node("update_signals", lambda s: node_update_signals(s, db))
    graph.add_node("decide",         lambda s: node_decide(s, db))
    graph.add_node("act",            lambda s: node_act(s, db))
    graph.add_node("error_exit",     node_error_exit)

    graph.set_entry_point("grade")
    graph.add_edge("grade",          "update_signals")
    graph.add_edge("update_signals", "decide")
    graph.add_conditional_edges(
        "decide",
        node_route_decision,
        {
            "act":        "act",
            "error_exit": "error_exit",
        }
    )
    graph.add_edge("act",        END)
    graph.add_edge("error_exit", END)

    return graph.compile()


# ── Public API ─────────────────────────────────────────────────────────────────

def run_cycle(db, user_id: str) -> dict:
    """
    §11.1 Invocation 1: update_signals → decide → route_decision → act.
    Returns the final state dict after the graph completes.
    """
    graph = _build_graph_invocation1(db)
    initial_state: SDAState = {
        "user_id": user_id,
        "current_signals": {},
        "agent_decisions": [],
        "action_results": {},
        "grade_result": None,
        "workflow_status": "running",
        "error_information": None,
    }
    logger.info("Starting invocation 1 (cycle) for user=%s", user_id)
    final_state = graph.invoke(initial_state)
    logger.info(
        "Invocation 1 complete for user=%s, status=%s",
        user_id, final_state.get("workflow_status")
    )
    return final_state


def run_answer(
    db,
    user_id: str,
    sub_topic: str,
    question_id: str,
    selected_option: str,
    cycle_id: str,
) -> dict:
    """
    §11.1 Invocation 2: grade → update_signals → decide → route_decision → act.
    Starts fresh, reading SubTopicState written by invocation 1 and grading.

    Raises grading.GradingError on validation failures (caller should return 400).
    """
    graph = _build_graph_invocation2(db)
    initial_state: SDAState = {
        "user_id":         user_id,
        "sub_topic":       sub_topic,
        "question_id":     question_id,
        "selected_option": selected_option,
        "cycle_id":        cycle_id,
        "current_signals": {},
        "agent_decisions": [],
        "action_results": {},
        "grade_result":    None,
        "workflow_status": "running",
        "error_information": None,
    }
    logger.info(
        "Starting invocation 2 (answer) for user=%s sub_topic=%s cycle_id=%s",
        user_id, sub_topic, cycle_id
    )
    final_state = graph.invoke(initial_state)
    logger.info(
        "Invocation 2 complete for user=%s, status=%s",
        user_id, final_state.get("workflow_status")
    )
    return final_state

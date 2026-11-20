"""LangGraph supervisor — routes tasks to workers and enforces kill-switch + approve."""
import asyncio
import logging
from typing import Literal

from langgraph.graph import END, StateGraph

from agents.state import AgentState, TASK_TYPES, initial_state
from agents.workers.smm_agent import smm_node
from agents.workers.messenger_agent import messenger_node
from agents.workers.chat_agent import chat_node
from agents.workers.funnel_agent import funnel_node
from agents.workers.email_agent import email_node
from agents.workers.classifieds_agent import classifieds_node
from agents.workers.fish_platforms_agent import fish_platforms_node
from agents.workers.scout_agent import scout_node

logger = logging.getLogger(__name__)

MAX_ITERATIONS = 10

# Task type → first worker to call
_ROUTE: dict[str, str] = {
    "daily_price": "messenger_agent",
    "weekly_promo": "smm_agent",
    "scout": "scout_agent",
    "chat_reply": "chat_agent",
    "lead_qualify": "funnel_agent",
    "email_send": "email_agent",
    "post_classifieds": "classifieds_agent",
    "post_fish_platform": "fish_platforms_agent",
}

# Global kill-switch
_stopped = False


def stop_all() -> None:
    """Hard stop — supervisor will not dispatch any new worker."""
    global _stopped
    _stopped = True
    logger.warning("KILL-SWITCH activated — all workers halted")


def resume_all() -> None:
    global _stopped
    _stopped = False
    logger.info("Kill-switch cleared — workers resumed")


# ── Supervisor node ──────────────────────────────────────────────────────────

def supervisor_node(state: AgentState) -> AgentState:
    """Decide which worker to call next (or stop)."""
    if _stopped or state["stopped"]:
        logger.warning("Supervisor: kill-switch active — stopping graph")
        return {**state, "next_worker": "__end__"}

    if state["iteration"] >= MAX_ITERATIONS:
        logger.error("Supervisor: max iterations reached — stopping")
        return {**state, "next_worker": "__end__", "errors": state["errors"] + ["max_iterations"]}

    # First call: route by task_type
    if not state["next_worker"] or state["next_worker"] == "__end__":
        worker = _ROUTE.get(state["task_type"])
        if not worker:
            logger.error("Supervisor: unknown task_type=%s", state["task_type"])
            return {**state, "next_worker": "__end__"}
        return {**state, "next_worker": worker, "iteration": state["iteration"] + 1}

    # After a worker ran: check its result
    result = state.get("worker_result", {})
    if result.get("done"):
        return {**state, "next_worker": "__end__"}

    # weekly_promo: smm_agent generates content, then messenger_agent sends it
    if state["task_type"] == "weekly_promo" and state["next_worker"] == "smm_agent":
        if result.get("content_ready"):
            return {**state, "next_worker": "messenger_agent", "iteration": state["iteration"] + 1}

    # Default: worker signals next step or we stop
    next_worker = result.get("next_worker", "__end__")
    return {**state, "next_worker": next_worker, "iteration": state["iteration"] + 1}


# ── Routing condition ────────────────────────────────────────────────────────

def route(state: AgentState) -> Literal[
    "smm_agent", "messenger_agent", "chat_agent", "funnel_agent",
    "email_agent", "classifieds_agent", "fish_platforms_agent", "scout_agent", "__end__"
]:
    return state["next_worker"]  # type: ignore[return-value]


# ── Build graph ───────────────────────────────────────────────────────────────

def build_graph() -> StateGraph:
    g = StateGraph(AgentState)

    g.add_node("supervisor", supervisor_node)
    g.add_node("smm_agent", smm_node)
    g.add_node("messenger_agent", messenger_node)
    g.add_node("chat_agent", chat_node)
    g.add_node("funnel_agent", funnel_node)
    g.add_node("email_agent", email_node)
    g.add_node("classifieds_agent", classifieds_node)
    g.add_node("fish_platforms_agent", fish_platforms_node)
    g.add_node("scout_agent", scout_node)

    g.set_entry_point("supervisor")

    g.add_conditional_edges(
        "supervisor",
        route,
        {
            "smm_agent": "smm_agent",
            "messenger_agent": "messenger_agent",
            "chat_agent": "chat_agent",
            "funnel_agent": "funnel_agent",
            "email_agent": "email_agent",
            "classifieds_agent": "classifieds_agent",
            "fish_platforms_agent": "fish_platforms_agent",
            "scout_agent": "scout_agent",
            "__end__": END,
        },
    )

    # Every worker returns to supervisor for next routing decision
    for worker in [
        "smm_agent", "messenger_agent", "chat_agent", "funnel_agent",
        "email_agent", "classifieds_agent", "fish_platforms_agent", "scout_agent",
    ]:
        g.add_edge(worker, "supervisor")

    return g


# Compiled graph (ready to invoke)
graph = build_graph().compile()


async def run_task(task_type: str, payload: dict) -> AgentState:
    """Entry point for external callers (scheduler, bot commands)."""
    if task_type not in TASK_TYPES:
        raise ValueError(f"Unknown task_type: {task_type}")
    state = initial_state(task_type, payload)
    result = await graph.ainvoke(state)
    return result

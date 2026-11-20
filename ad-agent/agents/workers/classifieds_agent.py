"""Classifieds agent — Форпост, Юла, Авито. Phase 2."""
import logging
from agents.state import AgentState

logger = logging.getLogger(__name__)


async def classifieds_node(state: AgentState) -> AgentState:
    logger.info("classifieds_agent: [STUB — Phase 2]")
    return {
        **state,
        "worker_result": {"done": True, "note": "classifieds_agent not yet implemented"},
    }

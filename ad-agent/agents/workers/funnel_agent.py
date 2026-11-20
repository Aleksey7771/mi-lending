"""Funnel agent — lead qualification and scoring. Phase 3."""
import logging
from agents.state import AgentState

logger = logging.getLogger(__name__)


async def funnel_node(state: AgentState) -> AgentState:
    logger.info("funnel_agent: [STUB — Phase 3]")
    return {
        **state,
        "worker_result": {"done": True, "note": "funnel_agent not yet implemented"},
    }

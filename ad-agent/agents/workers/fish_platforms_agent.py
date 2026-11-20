"""Fish platforms agent — fishnet.ru, fishery.ru, fishplace. Phase 3."""
import logging
from agents.state import AgentState

logger = logging.getLogger(__name__)


async def fish_platforms_node(state: AgentState) -> AgentState:
    logger.info("fish_platforms_agent: [STUB — Phase 3]")
    return {
        **state,
        "worker_result": {"done": True, "note": "fish_platforms_agent not yet implemented"},
    }

"""SMM agent — Instagram, VK, TikTok. Phase 2."""
import logging
from agents.state import AgentState

logger = logging.getLogger(__name__)


async def smm_node(state: AgentState) -> AgentState:
    logger.info("smm_agent: task=%s [STUB — Phase 2]", state["task_type"])
    return {
        **state,
        "worker_result": {"done": True, "note": "smm_agent not yet implemented"},
    }

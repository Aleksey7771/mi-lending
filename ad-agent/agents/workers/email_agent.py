"""Email agent — outbound KP / inbound inbox. Phase 3."""
import logging
from agents.state import AgentState

logger = logging.getLogger(__name__)


async def email_node(state: AgentState) -> AgentState:
    logger.info("email_agent: [STUB — Phase 3]")
    return {
        **state,
        "worker_result": {"done": True, "note": "email_agent not yet implemented"},
    }

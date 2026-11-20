"""Chat agent — replies to client questions in chats. Phase 2."""
import logging
from agents.state import AgentState

logger = logging.getLogger(__name__)


async def chat_node(state: AgentState) -> AgentState:
    logger.info("chat_agent: [STUB — Phase 2]")
    return {
        **state,
        "worker_result": {"done": True, "note": "chat_agent not yet implemented"},
    }

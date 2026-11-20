from typing import Any, TypedDict


TASK_TYPES = {
    "daily_price",       # → messenger_agent
    "weekly_promo",      # → smm_agent → messenger_agent
    "scout",             # → scout_agent
    "chat_reply",        # → chat_agent
    "lead_qualify",      # → funnel_agent
    "email_send",        # → email_agent
    "post_classifieds",  # → classifieds_agent
    "post_fish_platform",# → fish_platforms_agent
}

WORKER_NAMES = {
    "smm_agent",
    "messenger_agent",
    "chat_agent",
    "funnel_agent",
    "email_agent",
    "classifieds_agent",
    "fish_platforms_agent",
    "scout_agent",
}


class AgentState(TypedDict):
    task_type: str           # one of TASK_TYPES
    task_payload: dict       # task-specific data
    worker_result: dict      # result dict from last worker
    next_worker: str         # supervisor routing decision; "__end__" to stop
    stopped: bool            # kill-switch — set by stop_all()
    errors: list[str]        # accumulated non-fatal errors
    iteration: int           # loop guard (max 10)
    require_approve: bool    # True when content needs human approval before publish


def initial_state(task_type: str, payload: dict[str, Any]) -> AgentState:
    return AgentState(
        task_type=task_type,
        task_payload=payload,
        worker_result={},
        next_worker="",
        stopped=False,
        errors=[],
        iteration=0,
        require_approve=True,
    )

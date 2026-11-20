"""LangGraph supervisor for the new business-agent workers."""
import re
from typing import Any, Literal, TypedDict

from langgraph.graph import END, START, StateGraph

from agents.worker_lifecycle import _worker_registry
from agents.workers.stubs import run_stub

Complexity = Literal["simple", "complex"]


class SupervisorState(TypedDict, total=False):
    task: str
    intent: str
    params: dict[str, Any]
    complexity: Complexity
    worker_sequence: list[str]
    worker_results: list[dict[str, Any]]


_INTENT_WORKERS = {
    "capture_lead": "lead",
    "add_lead": "lead",
    "create_order": "order",
    "place_order": "order",
    "create_post": "content",
    "check_consent": "consent",
    "price_query": "pricing",
    "price_trend": "pricing",
}
_MAX_WORKER_STEPS = 5

_TASK_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("lead", re.compile(r"\b(?:добавь|создай|запиши|найди)\s+(?:лид|клиент|контакт)", re.I)),
    ("order", re.compile(r"\b(?:оформи|создай|проверь|измени)\s+заказ", re.I)),
    ("content", re.compile(r"\b(?:напиши|подготовь|сгенерируй|опубликуй)\s+(?:пост|публикац|контент)", re.I)),
    ("consent", re.compile(r"\b(?:проверь|запиши|отзови)\s+согласие", re.I)),
    ("pricing", re.compile(r"\b(?:узнай|проверь|сравни|обнови|покажи)\s+(?:цен|прайс|стоимост)", re.I)),
)


def _plan_workers(task: str, intent: str) -> list[str]:
    matches: list[tuple[int, str]] = []
    for worker, pattern in _TASK_PATTERNS:
        match = pattern.search(task)
        if match:
            matches.append((match.start(), worker))

    planned = [worker for _, worker in sorted(matches)]
    intent_worker = _INTENT_WORKERS.get(intent)
    if not planned:
        return [intent_worker or "general"]
    if intent_worker and intent_worker not in planned:
        planned.insert(0, intent_worker)
    return planned[:_MAX_WORKER_STEPS]


def classify_complexity(task: str, intent: str = "") -> Complexity:
    """Route multi-domain requests to the bounded multi-worker path."""
    return "complex" if len(_plan_workers(task, intent)) > 1 else "simple"


async def _run_single_worker(state: SupervisorState) -> dict[str, Any]:
    worker = state["worker_sequence"][0]
    async with _worker_registry.running():
        result = await _run_worker(worker, state)
    return {"worker_results": [result]}


async def _run_multi_agent_loop(state: SupervisorState) -> dict[str, Any]:
    results = []
    for worker in state["worker_sequence"]:
        async with _worker_registry.running():
            results.append(await _run_worker(worker, state))
    return {"worker_results": results}


async def _run_worker(worker: str, state: SupervisorState) -> dict[str, Any]:
    if worker == "content":
        from agents.workers.content_worker import run_content_worker

        return await run_content_worker(state)
    return await run_stub(worker, state)


def build_supervisor_graph():
    graph = StateGraph(SupervisorState)

    async def supervise(state: SupervisorState) -> dict[str, Any]:
        task = state.get("task", "")
        sequence = _plan_workers(task, state.get("intent", ""))
        complexity: Complexity = "complex" if len(sequence) > 1 else "simple"
        return {
            "worker_sequence": sequence,
            "complexity": complexity,
            "worker_results": [],
        }

    graph.add_node("supervisor", supervise)
    graph.add_node("single_worker", _run_single_worker)
    graph.add_node("multi_agent_loop", _run_multi_agent_loop)
    graph.add_edge(START, "supervisor")
    graph.add_conditional_edges(
        "supervisor",
        lambda state: state["complexity"],
        {"simple": "single_worker", "complex": "multi_agent_loop"},
    )
    graph.add_edge("single_worker", END)
    graph.add_edge("multi_agent_loop", END)
    return graph.compile()


supervisor_graph = build_supervisor_graph()

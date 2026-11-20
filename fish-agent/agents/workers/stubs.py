"""Side-effect-free worker placeholders for the initial supervisor graph."""
from typing import Any


async def run_stub(name: str, state: dict[str, Any]) -> dict[str, Any]:
    return {
        "worker": name,
        "status": "stub",
        "intent": state.get("intent", ""),
        "params": state.get("params", {}),
    }

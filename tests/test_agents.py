import os
import sys
import importlib.util
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest


def live_agent_dependencies_available() -> bool:
    return (
        importlib.util.find_spec("crewai") is not None
        and importlib.util.find_spec("langchain_ollama") is not None
    )


@pytest.mark.skipif(
    not os.getenv("OLLAMA_LIVE_TESTS"),
    reason="Set OLLAMA_LIVE_TESTS=1 to run local Ollama integration tests",
)
@pytest.mark.skipif(
    not live_agent_dependencies_available(),
    reason="Live agent dependencies are not installed",
)
def test_architect_returns_plan():
    from src.agents.architect import run_architect

    plan = run_architect("Write a script that prints the Fibonacci sequence up to 10")
    assert len(plan) > 50
    assert any(str(i) + "." in plan for i in range(1, 5)), "Plan should have numbered steps"

import json
import queue
from unittest.mock import patch

from langchain_core.messages import AIMessage

from src.agents.tool_agent import run_tool_agent
from src.models import ExecutionResult
from src.orchestrator import Orchestrator


def result(status: str, stderr: str = "") -> ExecutionResult:
    return ExecutionResult(status, "ok", stderr, 0 if status == "pass" else 1, 5, "/tmp/a.py")


def edges(workspace, session_id):
    log = workspace / "sessions" / session_id / "execution_log.jsonl"
    rows = [json.loads(line) for line in log.read_text().splitlines()]
    return [(r["from_state"], r["to_state"]) for r in rows if r.get("event_type") == "state_transition"]


def scripted_agent(*, tools, should_stop, **_):
    by_name = {fn.__name__: fn for fn in tools}
    assert "FAIL" in by_name["run_code"]("print(x)")
    assert "print(x)" in by_name["read_attempt"](1)
    assert by_name["search_past_fixes"]("NameError") == "No similar past fixes."
    assert by_name["run_code"]("print(1)").startswith("PASS")
    assert should_stop()


def test_tool_mode_keeps_state_machine_shape(tmp_path):
    with patch("src.orchestrator.run_architect", return_value="plan"), \
            patch("src.orchestrator.run_tool_agent", side_effect=scripted_agent), \
            patch("src.orchestrator.run_qa", side_effect=[result("fail", "NameError"), result("pass")]):
        session = Orchestrator(
            log_queue=queue.Queue(), workspace_dir=str(tmp_path), mode="tools"
        ).run("task", test_code="assert True")

    assert session.status == "completed"
    assert session.final_code == "print(1)"
    assert "assert True" in (tmp_path / "sessions" / session.session_id / "attempt_2.py").read_text()
    assert edges(tmp_path, session.session_id) == [
        ("IDLE", "PLANNING"),
        ("PLANNING", "CODING"),
        ("CODING", "EXECUTING"),
        ("EXECUTING", "RETRYING"),
        ("RETRYING", "CODING"),
        ("CODING", "EXECUTING"),
        ("EXECUTING", "SUCCEEDED"),
    ]


def test_tool_mode_fails_when_model_stops_without_passing(tmp_path):
    with patch("src.orchestrator.run_architect", return_value="plan"), \
            patch("src.orchestrator.run_tool_agent", return_value=None):
        session = Orchestrator(
            log_queue=queue.Queue(), workspace_dir=str(tmp_path), mode="tools"
        ).run("task")
    assert session.status == "failed"


class FakeChat:
    def __init__(self, replies):
        self.replies = iter(replies)
        self.seen = []

    def bind_tools(self, tools):
        self.tool_names = [t.name for t in tools]
        return self

    def invoke(self, messages):
        self.seen.append(list(messages))
        return next(self.replies)


def test_run_tool_agent_executes_model_tool_calls_and_feeds_results_back():
    calls = []

    def run_code(code: str) -> str:
        """Run code."""
        calls.append(code)
        return "FAIL" if len(calls) == 1 else "PASS"

    llm = FakeChat([
        AIMessage("", tool_calls=[{"name": "run_code", "args": {"code": "a"}, "id": "1"}]),
        AIMessage("", tool_calls=[{"name": "nope", "args": {}, "id": "2"}]),
        AIMessage("", tool_calls=[{"name": "run_code", "args": {"code": "b"}, "id": "3"}]),
        AIMessage("should not be reached"),
    ])
    run_tool_agent(
        task="t", plan="p", tools=[run_code], max_turns=10,
        should_stop=lambda: calls[-1:] == ["b"], llm=llm,
    )

    assert calls == ["a", "b"]
    assert llm.tool_names == ["run_code"]
    tool_outputs = [m.content for m in llm.seen[-1] if m.type == "tool"]
    assert tool_outputs == ["FAIL", "Unknown tool: nope"]

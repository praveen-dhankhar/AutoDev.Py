import queue
from unittest.mock import patch

from src.memory import FixMemory, format_fixes
from src.models import ExecutionResult
from src.orchestrator import Orchestrator

VECTORS = {
    "NameError: name 'x' is not defined": [1.0, 0.0],
    "NameError: name 'y' is not defined": [0.9, 0.1],
    "ZeroDivisionError: division by zero": [0.0, 1.0],
}


def fake_embed(text: str) -> list[float]:
    return VECTORS[text]


def failing_embed(text: str) -> list[float]:
    raise OSError("ollama down")


def result(status: str, stderr: str = "") -> ExecutionResult:
    return ExecutionResult(status, "", stderr, 0 if status == "pass" else 1, 5, "/tmp/a.py")


def test_search_returns_most_similar_fix_above_threshold(tmp_path):
    memory = FixMemory(tmp_path / "fixes.jsonl", embed=fake_embed)
    assert memory.add(task="t", error="NameError: name 'x' is not defined", fixed_code="x = 1")
    assert memory.add(task="t", error="ZeroDivisionError: division by zero", fixed_code="if d:")

    hits = memory.search("NameError: name 'y' is not defined")

    assert [h["fixed_code"] for h in hits] == ["x = 1"]
    assert "embedding" not in hits[0]
    assert "x = 1" in format_fixes(hits)


def test_embedding_failure_degrades_to_no_memory(tmp_path):
    memory = FixMemory(tmp_path / "fixes.jsonl", embed=failing_embed)
    assert memory.add(task="t", error="boom", fixed_code="pass") is False
    assert memory.search("boom") == []
    assert format_fixes([]) == ""


def test_orchestrator_stores_fix_then_injects_it_into_next_session(tmp_path):
    error = "NameError: name 'x' is not defined"

    def run(qa_results, coder_mock_kwargs):
        orch = Orchestrator(log_queue=queue.Queue(), workspace_dir=str(tmp_path))
        orch.memory.embed = fake_embed
        with patch("src.orchestrator.run_architect", return_value="plan"), \
                patch("src.orchestrator.run_coder", return_value="print(x)") as coder, \
                patch("src.orchestrator.run_qa", side_effect=qa_results):
            session = orch.run("task")
        coder_mock_kwargs.extend(c.kwargs for c in coder.call_args_list)
        return session

    first_calls: list = []
    session = run([result("fail", error), result("pass")], first_calls)
    assert session.status == "completed"
    assert (tmp_path / "memory" / "fixes.jsonl").exists()

    second_calls: list = []
    run([result("fail", "NameError: name 'y' is not defined"), result("pass")], second_calls)
    assert "Past fix 1" in second_calls[1]["error"]
    assert "Past fix" not in (first_calls[1]["error"] or "")

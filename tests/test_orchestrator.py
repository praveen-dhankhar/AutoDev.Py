import json
import queue
import sys
import threading
from pathlib import Path
from unittest.mock import call, patch

import pytest


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.models import ExecutionResult
from src.orchestrator import Orchestrator


def state_transitions(workspace_dir: Path, session_id: str) -> list[dict]:
    log_path = workspace_dir / "sessions" / session_id / "execution_log.jsonl"
    return [
        json.loads(line)
        for line in log_path.read_text(encoding="utf-8").splitlines()
        if json.loads(line).get("event_type") == "state_transition"
    ]


def transition_edges(workspace_dir: Path, session_id: str) -> list[tuple[str, str]]:
    return [
        (entry["from_state"], entry["to_state"])
        for entry in state_transitions(workspace_dir, session_id)
    ]


def execution_result(
    *,
    status: str,
    stderr: str = "",
    stdout: str = "",
    exit_code: int = 0,
    script_path: str = "/tmp/attempt.py",
) -> ExecutionResult:
    return ExecutionResult(
        status=status,
        stdout=stdout,
        stderr=stderr,
        exit_code=exit_code,
        execution_time_ms=10,
        script_path=script_path,
    )


def test_orchestrator_completes_with_mocked_agents(tmp_path):
    qa_result = execution_result(
        status="pass",
        stdout="hello\n",
        script_path=str(tmp_path / "attempt_1.py"),
    )

    with patch("src.orchestrator.run_architect", return_value="1. Print hello"):
        with patch("src.orchestrator.run_coder", return_value='print("hello")'):
            with patch("src.orchestrator.run_qa", return_value=qa_result):
                session = Orchestrator(
                    log_queue=queue.Queue(),
                    workspace_dir=str(tmp_path),
                ).run(task="print hello")

    assert session.status == "completed"
    assert session.attempt_count == 1
    assert "hello" in session.final_code
    transitions = state_transitions(tmp_path, session.session_id)
    assert all(
        {"event_type", "timestamp", "from_state", "to_state", "reason"} <= entry.keys()
        for entry in transitions
    )
    assert transition_edges(tmp_path, session.session_id) == [
        ("IDLE", "PLANNING"),
        ("PLANNING", "CODING"),
        ("CODING", "EXECUTING"),
        ("EXECUTING", "SUCCEEDED"),
    ]


def test_orchestrator_retries_after_qa_failure_and_then_completes(tmp_path):
    first_failure = execution_result(
        status="fail",
        stderr="NameError: missing_name",
        exit_code=1,
        script_path=str(tmp_path / "attempt_1.py"),
    )
    second_pass = execution_result(
        status="pass",
        stdout="fixed\n",
        script_path=str(tmp_path / "attempt_2.py"),
    )

    with patch("src.orchestrator.run_architect", return_value="1. Print hello"):
        with patch("src.orchestrator.run_coder") as coder_mock:
            coder_mock.side_effect = ['print(missing_name)', 'print("fixed")']
            with patch("src.orchestrator.run_qa") as qa_mock:
                qa_mock.side_effect = [first_failure, second_pass]

                session = Orchestrator(
                    log_queue=queue.Queue(),
                    max_retries=2,
                    workspace_dir=str(tmp_path),
                ).run(task="print hello")

    assert session.status == "completed"
    assert session.attempt_count == 2
    assert session.final_code == 'print("fixed")'
    assert coder_mock.call_args_list == [
        call(plan="1. Print hello", attempt=1, error=None),
        call(plan="1. Print hello", attempt=2, error="NameError: missing_name"),
    ]
    assert transition_edges(tmp_path, session.session_id) == [
        ("IDLE", "PLANNING"),
        ("PLANNING", "CODING"),
        ("CODING", "EXECUTING"),
        ("EXECUTING", "RETRYING"),
        ("RETRYING", "CODING"),
        ("CODING", "EXECUTING"),
        ("EXECUTING", "SUCCEEDED"),
    ]


def test_orchestrator_fails_after_retry_exhausted(tmp_path):
    qa_failures = [
        execution_result(
            status="fail",
            stderr="AssertionError: first failure",
            exit_code=1,
            script_path=str(tmp_path / "attempt_1.py"),
        ),
        execution_result(
            status="fail",
            stderr="AssertionError: second failure",
            exit_code=1,
            script_path=str(tmp_path / "attempt_2.py"),
        ),
    ]

    with patch("src.orchestrator.run_architect", return_value="1. Keep failing"):
        with patch("src.orchestrator.run_coder") as coder_mock:
            coder_mock.side_effect = ["raise AssertionError()", "raise AssertionError()"]
            with patch("src.orchestrator.run_qa") as qa_mock:
                qa_mock.side_effect = qa_failures

                session = Orchestrator(
                    log_queue=queue.Queue(),
                    max_retries=2,
                    workspace_dir=str(tmp_path),
                ).run(task="fail twice")

    assert session.status == "failed"
    assert session.attempt_count == 2
    assert session.final_code is None
    assert coder_mock.call_args_list == [
        call(plan="1. Keep failing", attempt=1, error=None),
        call(
            plan="1. Keep failing",
            attempt=2,
            error="AssertionError: first failure",
        ),
    ]
    transitions = state_transitions(tmp_path, session.session_id)
    assert [(entry["from_state"], entry["to_state"]) for entry in transitions] == [
        ("IDLE", "PLANNING"),
        ("PLANNING", "CODING"),
        ("CODING", "EXECUTING"),
        ("EXECUTING", "RETRYING"),
        ("RETRYING", "CODING"),
        ("CODING", "EXECUTING"),
        ("EXECUTING", "FAILED"),
    ]
    assert transitions[-1]["reason"] == "retry budget exhausted"


def test_orchestrator_stops_when_identical_traceback_repeats_twice(tmp_path):
    repeated_failure = execution_result(
        status="fail",
        stderr="Traceback: same unfixable error",
        exit_code=1,
        script_path=str(tmp_path / "attempt.py"),
    )
    log_queue = queue.Queue()

    with patch("src.orchestrator.run_architect", return_value="1. Keep failing"):
        with patch("src.orchestrator.run_coder") as coder_mock:
            coder_mock.side_effect = [
                "raise RuntimeError('same')",
                "raise RuntimeError('same again')",
                "raise RuntimeError('should not run')",
            ]
            with patch("src.orchestrator.run_qa", return_value=repeated_failure) as qa_mock:
                session = Orchestrator(
                    log_queue=log_queue,
                    max_retries=5,
                    workspace_dir=str(tmp_path),
                ).run(task="fail repeatedly")

    assert session.status == "failed"
    assert session.attempt_count == 2
    assert coder_mock.call_count == 2
    assert qa_mock.call_count == 2
    transitions = state_transitions(tmp_path, session.session_id)
    assert [(entry["from_state"], entry["to_state"]) for entry in transitions] == [
        ("IDLE", "PLANNING"),
        ("PLANNING", "CODING"),
        ("CODING", "EXECUTING"),
        ("EXECUTING", "RETRYING"),
        ("RETRYING", "CODING"),
        ("CODING", "EXECUTING"),
        ("EXECUTING", "FAILED"),
    ]
    assert transitions[-1]["reason"] == "identical traceback repeated twice"
    log_messages = [entry.message for entry in list(log_queue.queue)]
    assert any("Identical traceback repeated twice" in msg for msg in log_messages)


def test_orchestrator_cancel_after_execution_stops_before_retry(tmp_path):
    cancel_event = threading.Event()
    first_failure = execution_result(
        status="fail",
        stderr="NameError: missing_name",
        exit_code=1,
        script_path=str(tmp_path / "attempt_1.py"),
    )

    def cancel_after_qa(script_path, cancel_event=None):
        cancel_event.set()
        return first_failure

    log_queue = queue.Queue()
    with patch("src.orchestrator.run_architect", return_value="1. Print hello"):
        with patch("src.orchestrator.run_coder", return_value="print(missing_name)") as coder_mock:
            with patch("src.orchestrator.run_qa", side_effect=cancel_after_qa) as qa_mock:
                session = Orchestrator(
                    log_queue=log_queue,
                    max_retries=3,
                    workspace_dir=str(tmp_path),
                    cancel_event=cancel_event,
                ).run(task="print hello")

    assert session.status == "cancelled"
    assert session.attempt_count == 1
    assert coder_mock.call_count == 1
    assert qa_mock.call_count == 1
    assert qa_mock.call_args.kwargs["cancel_event"] is cancel_event
    assert transition_edges(tmp_path, session.session_id) == [
        ("IDLE", "PLANNING"),
        ("PLANNING", "CODING"),
        ("CODING", "EXECUTING"),
        ("EXECUTING", "CANCELLED"),
    ]
    assert state_transitions(tmp_path, session.session_id)[-1]["reason"] == (
        "cancel requested during execution"
    )


def test_orchestrator_handles_cancelled_executor_result(tmp_path):
    cancel_result = execution_result(
        status="cancelled",
        stderr="Cancelled: sandbox execution stopped",
        exit_code=-2,
        script_path=str(tmp_path / "attempt_1.py"),
    )

    with patch("src.orchestrator.run_architect", return_value="1. Print hello"):
        with patch("src.orchestrator.run_coder", return_value='print("hello")'):
            with patch("src.orchestrator.run_qa", return_value=cancel_result):
                session = Orchestrator(
                    log_queue=queue.Queue(),
                    max_retries=3,
                    workspace_dir=str(tmp_path),
                ).run(task="print hello")

    assert session.status == "cancelled"
    assert session.attempt_count == 1
    assert transition_edges(tmp_path, session.session_id)[-1] == (
        "EXECUTING",
        "CANCELLED",
    )


@pytest.mark.parametrize(
    "stderr",
    [
        "DockerUnavailable: Docker daemon is not available",
        "SandboxImageUnavailable: Docker image is not ready",
    ],
)
def test_orchestrator_circuit_breaker_stops_on_sandbox_infrastructure_failure(
    tmp_path,
    stderr,
):
    sandbox_failure = execution_result(
        status="fail",
        stderr=stderr,
        exit_code=127,
        script_path=str(tmp_path / "attempt_1.py"),
    )
    log_queue = queue.Queue()

    with patch("src.orchestrator.run_architect", return_value="1. Print hello"):
        with patch("src.orchestrator.run_coder", return_value='print("hello")') as coder_mock:
            with patch("src.orchestrator.run_qa", return_value=sandbox_failure) as qa_mock:
                session = Orchestrator(
                    log_queue=log_queue,
                    max_retries=3,
                    workspace_dir=str(tmp_path),
                ).run(task="print hello")

    assert session.status == "failed"
    assert session.attempt_count == 1
    assert coder_mock.call_count == 1
    assert qa_mock.call_count == 1
    log_messages = [entry.message for entry in list(log_queue.queue)]
    assert any("Circuit breaker stopped the retry loop" in msg for msg in log_messages)
    transitions = state_transitions(tmp_path, session.session_id)
    assert transitions[-1]["to_state"] == "FAILED"
    assert transitions[-1]["reason"] == "non-retriable sandbox infrastructure failure"


def test_orchestrator_fails_when_architect_raises(tmp_path):
    with patch("src.orchestrator.run_architect", side_effect=RuntimeError("llm down")):
        with patch("src.orchestrator.run_coder") as coder_mock:
            session = Orchestrator(
                log_queue=queue.Queue(),
                workspace_dir=str(tmp_path),
            ).run(task="print hello")

    assert session.status == "failed"
    assert session.attempt_count == 0
    coder_mock.assert_not_called()
    assert transition_edges(tmp_path, session.session_id) == [
        ("IDLE", "PLANNING"),
        ("PLANNING", "FAILED"),
    ]


def test_orchestrator_fails_when_coder_raises(tmp_path):
    with patch("src.orchestrator.run_architect", return_value="1. Print hello"):
        with patch("src.orchestrator.run_coder", side_effect=RuntimeError("coder down")):
            with patch("src.orchestrator.run_qa") as qa_mock:
                session = Orchestrator(
                    log_queue=queue.Queue(),
                    workspace_dir=str(tmp_path),
                ).run(task="print hello")

    assert session.status == "failed"
    assert session.attempt_count == 0
    qa_mock.assert_not_called()
    assert transition_edges(tmp_path, session.session_id) == [
        ("IDLE", "PLANNING"),
        ("PLANNING", "CODING"),
        ("CODING", "FAILED"),
    ]

import queue
import sys
from pathlib import Path
from unittest.mock import call, patch

import pytest


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.models import ExecutionResult
from src.orchestrator import Orchestrator


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

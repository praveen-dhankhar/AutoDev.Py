import queue
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.cli import main  # noqa: E402
from src.models import AgentLogEntry, AgentSession  # noqa: E402


def test_cli_version_prints_package_version(capsys):
    with patch.object(sys, "argv", ["pr-agent", "--version"]):
        try:
            main()
        except SystemExit as exc:
            assert exc.code == 0

    output = capsys.readouterr().out
    assert "pr-agent 0.1.0" in output


def test_cli_run_invokes_orchestrator_and_reports_success(tmp_path, capsys):
    session = AgentSession(task="print hello", status="completed", final_code='print("hello")')
    log_queue = queue.Queue()
    log_queue.put(AgentLogEntry(agent="system", message="done", level="success"))

    orchestrator = MagicMock()
    orchestrator.run.return_value = session

    with patch("src.cli.check_ollama_health") as health_mock:
        health_mock.return_value.healthy = True
        with patch("src.cli.queue.Queue", return_value=log_queue):
            with patch("src.cli.Orchestrator", return_value=orchestrator) as orchestrator_cls:
                exit_code = main(
                    [
                        "run",
                        "print hello",
                        "--workspace-dir",
                        str(tmp_path),
                        "--max-retries",
                        "2",
                    ]
                )

    assert exit_code == 0
    orchestrator_cls.assert_called_once_with(
        log_queue=log_queue,
        max_retries=2,
        workspace_dir=str(tmp_path),
        mode="classic",
    )
    orchestrator.run.assert_called_once_with("print hello")
    output = capsys.readouterr().out
    assert "Status: completed" in output
    assert "Final script:" in output


def test_cli_run_returns_nonzero_for_failed_session(tmp_path):
    session = AgentSession(task="fail", status="failed")
    orchestrator = MagicMock()
    orchestrator.run.return_value = session

    with patch("src.cli.check_ollama_health") as health_mock:
        health_mock.return_value.healthy = True
        with patch("src.cli.Orchestrator", return_value=orchestrator):
            exit_code = main(["run", "fail", "--workspace-dir", str(tmp_path), "--quiet"])

    assert exit_code == 1


def test_cli_run_fails_fast_when_ollama_is_unavailable(capsys):
    with patch("src.cli.check_ollama_health") as health_mock:
        health_mock.return_value.healthy = False
        health_mock.return_value.message = "Ollama unavailable"
        exit_code = main(["run", "print hello", "--quiet"])

    assert exit_code == 2
    assert "Ollama unavailable" in capsys.readouterr().err

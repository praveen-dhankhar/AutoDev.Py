import queue
import sys
from pathlib import Path
from unittest.mock import patch


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.orchestrator import Orchestrator


def test_orchestrator_completes_with_mocked_agents(tmp_path):
    with patch("src.orchestrator.run_architect", return_value="1. Print hello"):
        with patch("src.orchestrator.run_coder", return_value='print("hello")'):
            session = Orchestrator(
                log_queue=queue.Queue(),
                workspace_dir=str(tmp_path),
            ).run(task="print hello")

    assert session.status == "completed"
    assert session.attempt_count == 1
    assert "hello" in session.final_code

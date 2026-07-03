import json
import sys
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.session_store import load_sessions  # noqa: E402


def write_log(session_dir: Path, to_state: str) -> None:
    payload = {
        "agent": "system",
        "message": f"STATE EXECUTING -> {to_state}",
        "level": "info",
        "timestamp": "2026-07-03T00:00:00",
        "event_type": "state_transition",
        "from_state": "EXECUTING",
        "to_state": to_state,
        "reason": "test",
    }
    (session_dir / "execution_log.jsonl").write_text(
        json.dumps(payload) + "\n",
        encoding="utf-8",
    )


def test_load_sessions_rehydrates_completed_session(tmp_path):
    session_dir = tmp_path / "sessions" / "abc12345"
    session_dir.mkdir(parents=True)
    (session_dir / "task.txt").write_text("print hello", encoding="utf-8")
    (session_dir / "plan.md").write_text("1. Print hello", encoding="utf-8")
    (session_dir / "attempt_1.py").write_text('print("hello")', encoding="utf-8")
    (session_dir / "final.py").write_text('print("hello")', encoding="utf-8")
    write_log(session_dir, "SUCCEEDED")

    sessions = load_sessions(str(tmp_path))

    assert len(sessions) == 1
    session = sessions[0]
    assert session.session_id == "abc12345"
    assert session.task == "print hello"
    assert session.status == "completed"
    assert session.implementation_plan == "1. Print hello"
    assert session.final_code == 'print("hello")'
    assert session.attempt_count == 1
    assert session.logs[-1].to_state == "SUCCEEDED"


def test_load_sessions_rehydrates_cancelled_session(tmp_path):
    session_dir = tmp_path / "sessions" / "cancel1"
    session_dir.mkdir(parents=True)
    (session_dir / "task.txt").write_text("long run", encoding="utf-8")
    (session_dir / "attempt_1.py").write_text("while True: pass", encoding="utf-8")
    write_log(session_dir, "CANCELLED")

    sessions = load_sessions(str(tmp_path))

    assert len(sessions) == 1
    assert sessions[0].status == "cancelled"

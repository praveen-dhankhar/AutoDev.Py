from __future__ import annotations

import json
from pathlib import Path

from src.models import AgentLogEntry, AgentSession, AttemptRecord


STATE_TO_STATUS = {
    "IDLE": "idle",
    "PLANNING": "planning",
    "CODING": "coding",
    "EXECUTING": "executing",
    "RETRYING": "retrying",
    "SUCCEEDED": "completed",
    "FAILED": "failed",
    "CANCELLED": "cancelled",
}


def load_sessions(workspace_dir: str) -> list[AgentSession]:
    sessions_root = Path(workspace_dir) / "sessions"
    if not sessions_root.exists():
        return []

    sessions = [
        session
        for session_dir in sorted(
            sessions_root.iterdir(),
            key=lambda path: path.stat().st_mtime,
        )
        if session_dir.is_dir()
        if (session := load_session(session_dir)) is not None
    ]
    return sessions


def load_session(session_dir: Path) -> AgentSession | None:
    task_path = session_dir / "task.txt"
    if not task_path.exists():
        return None

    session = AgentSession(
        session_id=session_dir.name,
        task=task_path.read_text(encoding="utf-8"),
    )

    plan_path = session_dir / "plan.md"
    if plan_path.exists():
        session.implementation_plan = plan_path.read_text(encoding="utf-8")

    for attempt_path in sorted(session_dir.glob("attempt_*.py"), key=_attempt_number):
        session.attempts.append(
            AttemptRecord(
                attempt_number=_attempt_number(attempt_path),
                code=attempt_path.read_text(encoding="utf-8"),
                script_path=str(attempt_path.resolve()),
            )
        )

    final_path = session_dir / "final.py"
    if final_path.exists():
        session.final_code = final_path.read_text(encoding="utf-8")

    session.logs = _load_logs(session_dir / "execution_log.jsonl")
    session.status = _infer_status(session, session.logs)
    return session


def _load_logs(log_path: Path) -> list[AgentLogEntry]:
    if not log_path.exists():
        return []

    entries = []
    for line in log_path.read_text(encoding="utf-8").splitlines():
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        entries.append(
            AgentLogEntry(
                agent=payload.get("agent", "system"),
                message=payload.get("message", ""),
                level=payload.get("level", "info"),
                event_type=payload.get("event_type"),
                from_state=payload.get("from_state"),
                to_state=payload.get("to_state"),
                attempt_number=payload.get("attempt_number"),
                reason=payload.get("reason"),
            )
        )
    return entries


def _infer_status(session: AgentSession, logs: list[AgentLogEntry]) -> str:
    for entry in reversed(logs):
        if entry.event_type == "state_transition" and entry.to_state:
            return STATE_TO_STATUS.get(entry.to_state, session.status)

    if session.final_code:
        return "completed"
    if session.attempts:
        return "failed"
    return "idle"


def _attempt_number(path: Path) -> int:
    try:
        return int(path.stem.split("_", maxsplit=1)[1])
    except (IndexError, ValueError):
        return 0

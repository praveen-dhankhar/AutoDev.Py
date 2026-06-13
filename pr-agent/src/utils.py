import json
import os

from src.models import AgentLogEntry, AgentSession


def create_session_dir(session: AgentSession, workspace_dir: str) -> str:
    """Creates /workspace/sessions/{session_id}/ and returns the path."""
    path = os.path.join(workspace_dir, "sessions", session.session_id)
    os.makedirs(path, exist_ok=True)
    with open(os.path.join(path, "task.txt"), "w", encoding="utf-8") as f:
        f.write(session.task)
    return path


def save_attempt_to_disk(session_dir: str, attempt_num: int, code: str) -> str:
    """Writes attempt_{n}.py and returns the absolute script path."""
    filename = f"attempt_{attempt_num}.py"
    path = os.path.join(session_dir, filename)
    with open(path, "w", encoding="utf-8") as f:
        f.write(code)
    return os.path.abspath(path)


def save_plan_to_disk(session_dir: str, plan: str) -> None:
    """Writes plan.md to the session directory."""
    with open(os.path.join(session_dir, "plan.md"), "w", encoding="utf-8") as f:
        f.write(plan)


def save_final_script(session_dir: str, code: str) -> str:
    """Writes final.py and returns its absolute path."""
    path = os.path.join(session_dir, "final.py")
    with open(path, "w", encoding="utf-8") as f:
        f.write(code)
    return os.path.abspath(path)


def append_log_to_jsonl(session_dir: str, entry: AgentLogEntry) -> None:
    """Appends a single log entry to execution_log.jsonl."""
    path = os.path.join(session_dir, "execution_log.jsonl")
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry.to_dict()) + "\n")

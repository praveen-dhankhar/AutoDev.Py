import os
import queue
from datetime import datetime

from src.agents.architect import run_architect
from src.agents.coder import run_coder
from src.agents.qa import run_qa
from src.config import MAX_RETRIES, WORKSPACE_DIR
from src.models import AgentLogEntry, AgentSession, AttemptRecord
from src.utils import (
    append_log_to_jsonl,
    create_session_dir,
    save_attempt_to_disk,
    save_final_script,
    save_plan_to_disk,
)


class Orchestrator:
    def __init__(
        self,
        log_queue: queue.Queue,
        max_retries: int = MAX_RETRIES,
        workspace_dir: str = WORKSPACE_DIR,
    ):
        self.log_queue = log_queue
        self.max_retries = max_retries
        self.workspace_dir = workspace_dir
        self._session_dir = None

    def emit(self, agent: str, message: str, level: str = "info") -> None:
        """Thread-safe log emission to the Streamlit queue."""
        entry = AgentLogEntry(agent=agent, message=message, level=level)
        self.log_queue.put(entry)
        if self._session_dir:
            append_log_to_jsonl(self._session_dir, entry)

    def run(self, task: str) -> AgentSession:
        session = AgentSession(task=task)
        self._session_dir = create_session_dir(session, self.workspace_dir)

        session.status = "planning"
        self.emit("architect", "Analyzing task and creating implementation plan...")
        try:
            plan = run_architect(task)
        except Exception as e:
            session.status = "failed"
            self.emit("system", f"✗ Architect failed: {e}", level="error")
            return session

        session.implementation_plan = plan
        save_plan_to_disk(self._session_dir, plan)
        self.emit("architect", f"Plan ready:\n{plan}", level="success")

        previous_error = None
        for attempt_num in range(1, self.max_retries + 1):
            session.status = "coding"
            self.emit(
                "coder",
                f"Writing code (attempt {attempt_num}/{self.max_retries})...",
            )

            try:
                code = run_coder(
                    plan=plan,
                    attempt=attempt_num,
                    error=previous_error,
                )
            except Exception as e:
                session.status = "failed"
                self.emit("system", f"✗ Coder failed: {e}", level="error")
                return session

            script_path = save_attempt_to_disk(self._session_dir, attempt_num, code)
            self.emit("coder", f"Script saved → attempt_{attempt_num}.py", level="info")

            session.status = "executing"
            self.emit(
                "qa",
                (
                    f"Executing attempt_{attempt_num}.py "
                    f"(timeout: {os.getenv('SUBPROCESS_TIMEOUT', 30)}s)..."
                ),
            )

            result = run_qa(script_path=script_path)

            attempt = AttemptRecord(
                attempt_number=attempt_num,
                code=code,
                script_path=script_path,
                execution_result=result,
            )
            session.attempts.append(attempt)

            if result.status == "pass":
                session.status = "completed"
                session.final_code = code
                session.completed_at = datetime.utcnow()
                save_final_script(self._session_dir, code)
                self.emit(
                    "system",
                    (
                        f"✓ Passed on attempt {attempt_num}! "
                        f"(exit 0, {result.execution_time_ms:.0f}ms)"
                    ),
                    level="success",
                )
                return session

            self.emit(
                "qa",
                (
                    f"✗ Attempt {attempt_num} FAILED "
                    f"(exit {result.exit_code}):\n{result.stderr}"
                ),
                level="error",
            )
            previous_error = result.stderr

            if attempt_num < self.max_retries:
                session.status = "correcting"
                self.emit(
                    "coder",
                    (
                        "Received error context. Fixing for attempt "
                        f"{attempt_num + 1}/{self.max_retries}..."
                    ),
                    level="warning",
                )

        session.status = "failed"
        self.emit(
            "system",
            (
                f"✗ All {self.max_retries} attempts failed. "
                "Task could not be completed."
            ),
            level="error",
        )
        return session

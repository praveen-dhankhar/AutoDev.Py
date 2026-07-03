import os
import queue
import threading
from datetime import datetime
from enum import Enum
from typing import Optional

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


class PipelineState(str, Enum):
    IDLE = "IDLE"
    PLANNING = "PLANNING"
    CODING = "CODING"
    EXECUTING = "EXECUTING"
    RETRYING = "RETRYING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


SESSION_STATUS_BY_STATE = {
    PipelineState.IDLE: "idle",
    PipelineState.PLANNING: "planning",
    PipelineState.CODING: "coding",
    PipelineState.EXECUTING: "executing",
    PipelineState.RETRYING: "retrying",
    PipelineState.SUCCEEDED: "completed",
    PipelineState.FAILED: "failed",
    PipelineState.CANCELLED: "cancelled",
}


NON_RETRIABLE_QA_ERROR_PREFIXES = (
    "DockerUnavailable:",
    "SandboxImageUnavailable:",
)


def is_non_retriable_qa_failure(stderr: str) -> bool:
    return stderr.startswith(NON_RETRIABLE_QA_ERROR_PREFIXES)


class Orchestrator:
    def __init__(
        self,
        log_queue: queue.Queue,
        max_retries: int = MAX_RETRIES,
        workspace_dir: str = WORKSPACE_DIR,
        cancel_event: Optional[threading.Event] = None,
    ):
        self.log_queue = log_queue
        self.max_retries = max_retries
        self.workspace_dir = workspace_dir
        self.cancel_event = cancel_event
        self._session_dir = None
        self._state = PipelineState.IDLE

    def emit(self, agent: str, message: str, level: str = "info") -> None:
        """Thread-safe log emission to the Streamlit queue."""
        entry = AgentLogEntry(agent=agent, message=message, level=level)
        self.log_queue.put(entry)
        if self._session_dir:
            append_log_to_jsonl(self._session_dir, entry)

    def cancel_requested(self) -> bool:
        return self.cancel_event is not None and self.cancel_event.is_set()

    def cancel_session(
        self,
        session: AgentSession,
        *,
        attempt_number: Optional[int] = None,
        reason: str = "cancel requested",
    ) -> AgentSession:
        self.transition(
            session,
            PipelineState.CANCELLED,
            attempt_number=attempt_number,
            reason=reason,
        )
        session.completed_at = datetime.utcnow()
        self.emit("system", "Run cancelled by user.", level="warning")
        return session

    def transition(
        self,
        session: AgentSession,
        to_state: PipelineState,
        *,
        attempt_number: Optional[int] = None,
        reason: str,
    ) -> None:
        from_state = self._state
        self._state = to_state
        session.status = SESSION_STATUS_BY_STATE[to_state]
        entry = AgentLogEntry(
            agent="system",
            message=(
                f"STATE {from_state.value} -> {to_state.value}"
                f" ({reason})"
            ),
            level="info" if to_state is not PipelineState.FAILED else "error",
            event_type="state_transition",
            from_state=from_state.value,
            to_state=to_state.value,
            attempt_number=attempt_number,
            reason=reason,
        )
        self.log_queue.put(entry)
        if self._session_dir:
            append_log_to_jsonl(self._session_dir, entry)

    def run(self, task: str) -> AgentSession:
        self._state = PipelineState.IDLE
        session = AgentSession(task=task)
        self._session_dir = create_session_dir(session, self.workspace_dir)

        self.transition(session, PipelineState.PLANNING, reason="task received")
        if self.cancel_requested():
            return self.cancel_session(session, reason="cancel requested before planning")
        self.emit("architect", "Analyzing task and creating implementation plan...")
        try:
            plan = run_architect(task)
        except Exception as e:
            self.transition(session, PipelineState.FAILED, reason="architect failed")
            self.emit("system", f"✗ Architect failed: {e}", level="error")
            return session

        session.implementation_plan = plan
        save_plan_to_disk(self._session_dir, plan)
        self.emit("architect", f"Plan ready:\n{plan}", level="success")
        if self.cancel_requested():
            return self.cancel_session(session, reason="cancel requested after planning")

        previous_error = None
        repeated_error_count = 0
        for attempt_num in range(1, self.max_retries + 1):
            if self.cancel_requested():
                return self.cancel_session(
                    session,
                    attempt_number=attempt_num,
                    reason="cancel requested before code generation",
                )

            self.transition(
                session,
                PipelineState.CODING,
                attempt_number=attempt_num,
                reason="starting code generation",
            )
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
                self.transition(
                    session,
                    PipelineState.FAILED,
                    attempt_number=attempt_num,
                    reason="coder failed",
                )
                self.emit("system", f"✗ Coder failed: {e}", level="error")
                return session

            script_path = save_attempt_to_disk(self._session_dir, attempt_num, code)
            self.emit("coder", f"Script saved → attempt_{attempt_num}.py", level="info")

            if self.cancel_requested():
                return self.cancel_session(
                    session,
                    attempt_number=attempt_num,
                    reason="cancel requested before execution",
                )

            self.transition(
                session,
                PipelineState.EXECUTING,
                attempt_number=attempt_num,
                reason="running generated code",
            )
            self.emit(
                "qa",
                (
                    f"Executing attempt_{attempt_num}.py "
                    f"(timeout: {os.getenv('SUBPROCESS_TIMEOUT', 30)}s)..."
                ),
            )

            result = run_qa(script_path=script_path, cancel_event=self.cancel_event)

            attempt = AttemptRecord(
                attempt_number=attempt_num,
                code=code,
                script_path=script_path,
                execution_result=result,
            )
            session.attempts.append(attempt)

            if result.status == "cancelled" or self.cancel_requested():
                return self.cancel_session(
                    session,
                    attempt_number=attempt_num,
                    reason="cancel requested during execution",
                )

            if result.status == "pass":
                self.transition(
                    session,
                    PipelineState.SUCCEEDED,
                    attempt_number=attempt_num,
                    reason="attempt passed",
                )
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

            if is_non_retriable_qa_failure(result.stderr):
                self.transition(
                    session,
                    PipelineState.FAILED,
                    attempt_number=attempt_num,
                    reason="non-retriable sandbox infrastructure failure",
                )
                self.emit(
                    "system",
                    (
                        "✗ Sandbox infrastructure failure is non-retriable. "
                        "Circuit breaker stopped the retry loop."
                    ),
                    level="error",
                )
                return session

            if result.stderr:
                repeated_error_count = (
                    repeated_error_count + 1
                    if result.stderr == previous_error
                    else 1
                )
                previous_error = result.stderr
            else:
                repeated_error_count = 0
                previous_error = result.stderr

            if repeated_error_count >= 2:
                self.transition(
                    session,
                    PipelineState.FAILED,
                    attempt_number=attempt_num,
                    reason="identical traceback repeated twice",
                )
                self.emit(
                    "system",
                    (
                        "✗ Identical traceback repeated twice. "
                        "Circuit breaker stopped the retry loop."
                    ),
                    level="error",
                )
                return session

            if attempt_num < self.max_retries:
                self.transition(
                    session,
                    PipelineState.RETRYING,
                    attempt_number=attempt_num,
                    reason="attempt failed and retry budget remains",
                )
                self.emit(
                    "coder",
                    (
                        "Received error context. Fixing for attempt "
                        f"{attempt_num + 1}/{self.max_retries}..."
                    ),
                    level="warning",
                )

        self.transition(
            session,
            PipelineState.FAILED,
            attempt_number=self.max_retries,
            reason="retry budget exhausted",
        )
        self.emit(
            "system",
            (
                f"✗ All {self.max_retries} attempts failed. "
                "Task could not be completed."
            ),
            level="error",
        )
        return session

import os
import queue
import threading
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Literal, Optional

from src.agents.architect import run_architect
from src.agents.coder import run_coder
from src.agents.qa import run_qa
from src.agents.tool_agent import run_tool_agent
from src.config import MAX_RETRIES, WORKSPACE_DIR
from src.memory import FixMemory, format_fixes
from src.models import AgentLogEntry, AgentSession, AttemptRecord, ExecutionResult
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


TERMINAL_STATUSES = {"completed", "failed", "cancelled"}


def is_non_retriable_qa_failure(stderr: str) -> bool:
    return stderr.startswith(NON_RETRIABLE_QA_ERROR_PREFIXES)


def with_tests(code: str, test_code: Optional[str]) -> str:
    return f"{code}\n\n{test_code}\n" if test_code else code


class Orchestrator:
    def __init__(
        self,
        log_queue: queue.Queue,
        max_retries: int = MAX_RETRIES,
        workspace_dir: str = WORKSPACE_DIR,
        cancel_event: Optional[threading.Event] = None,
        *,
        mode: Literal["classic", "tools"] = "classic",
        feedback: bool = True,
        use_memory: bool = True,
    ):
        self.log_queue = log_queue
        self.max_retries = max_retries
        self.workspace_dir = workspace_dir
        self.cancel_event = cancel_event
        self.mode = mode
        # feedback=False retries without the traceback: the benchmark's ablation baseline.
        self.feedback = feedback
        self.memory = (
            FixMemory(Path(workspace_dir) / "memory" / "fixes.jsonl") if use_memory else None
        )
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

    def run(
        self,
        task: str,
        *,
        plan: Optional[str] = None,
        test_code: Optional[str] = None,
    ) -> AgentSession:
        """Run the pipeline. A given plan skips the Architect; test_code is appended
        to every executed script so assertions decide pass/fail."""
        self._state = PipelineState.IDLE
        session = AgentSession(task=task)
        self._session_dir = create_session_dir(session, self.workspace_dir)

        self.transition(session, PipelineState.PLANNING, reason="task received")
        if self.cancel_requested():
            return self.cancel_session(session, reason="cancel requested before planning")
        if plan is None:
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

        if self.mode == "tools":
            return self._run_tool_mode(session, plan, test_code)

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

            coder_error = previous_error if self.feedback else None
            if coder_error and self.memory:
                fixes = self.memory.search(coder_error)
                if fixes:
                    self.emit("coder", f"Memory: {len(fixes)} similar past fix(es) added to prompt")
                    coder_error = f"{coder_error}\n\n{format_fixes(fixes)}"

            try:
                code = run_coder(
                    plan=plan,
                    attempt=attempt_num,
                    error=coder_error,
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

            script_path = save_attempt_to_disk(
                self._session_dir, attempt_num, with_tests(code, test_code)
            )
            self.emit("coder", f"Script saved → attempt_{attempt_num}.py", level="info")

            if self.cancel_requested():
                return self.cancel_session(
                    session,
                    attempt_number=attempt_num,
                    reason="cancel requested before execution",
                )

            result = self._execute(session, attempt_num, code, script_path)

            if result.status == "cancelled" or self.cancel_requested():
                return self.cancel_session(
                    session,
                    attempt_number=attempt_num,
                    reason="cancel requested during execution",
                )

            if result.status == "pass":
                return self._succeed(session, attempt_num, code, result)

            self._report_failure(attempt_num, result)

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

    def _execute(
        self, session: AgentSession, attempt_num: int, code: str, script_path: str
    ) -> ExecutionResult:
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
        session.attempts.append(
            AttemptRecord(
                attempt_number=attempt_num,
                code=code,
                script_path=script_path,
                execution_result=result,
            )
        )
        return result

    def _report_failure(self, attempt_num: int, result: ExecutionResult) -> None:
        self.emit(
            "qa",
            f"✗ Attempt {attempt_num} FAILED (exit {result.exit_code}):\n{result.stderr}",
            level="error",
        )

    def _succeed(
        self, session: AgentSession, attempt_num: int, code: str, result: ExecutionResult
    ) -> AgentSession:
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
            f"✓ Passed on attempt {attempt_num}! (exit 0, {result.execution_time_ms:.0f}ms)",
            level="success",
        )
        self._remember_fix(session)
        return session

    def _remember_fix(self, session: AgentSession) -> None:
        """Store the traceback that preceded a passing attempt, keyed by its embedding."""
        if not self.memory or len(session.attempts) < 2:
            return
        failed = session.attempts[-2].execution_result
        error = failed.stderr if failed else ""
        if error and self.memory.add(
            task=session.task, error=error, fixed_code=session.attempts[-1].code
        ):
            self.emit("system", "Stored traceback-and-fix pair in long-term memory.")

    def _run_tool_mode(
        self, session: AgentSession, plan: str, test_code: Optional[str]
    ) -> AgentSession:
        """The model drives: it calls run_code / read_attempt / search_past_fixes itself.
        Tools still route through transition(), so the state log keeps the classic shape."""
        self.transition(
            session, PipelineState.CODING, attempt_number=1, reason="model is driving tools"
        )
        self.emit("coder", "Tool mode: model chooses when to run, inspect, or search.")

        def run_code(code: str) -> str:
            """Run a complete Python script in the sandbox. Returns PASS or FAIL with exit code, stdout and stderr."""
            attempt_num = session.attempt_count + 1
            if self._state is PipelineState.RETRYING:
                self.transition(
                    session,
                    PipelineState.CODING,
                    attempt_number=attempt_num,
                    reason="model submitted new code",
                )
            script_path = save_attempt_to_disk(
                self._session_dir, attempt_num, with_tests(code, test_code)
            )
            self.emit("coder", f"Script saved → attempt_{attempt_num}.py")
            result = self._execute(session, attempt_num, code, script_path)

            if result.status == "cancelled" or self.cancel_requested():
                self.cancel_session(
                    session, attempt_number=attempt_num, reason="cancel requested during execution"
                )
                return "Cancelled."
            if result.status == "pass":
                self._succeed(session, attempt_num, code, result)
                return f"PASS\nstdout:\n{result.stdout}"

            self._report_failure(attempt_num, result)
            if is_non_retriable_qa_failure(result.stderr):
                self.transition(
                    session,
                    PipelineState.FAILED,
                    attempt_number=attempt_num,
                    reason="non-retriable sandbox infrastructure failure",
                )
            elif attempt_num >= self.max_retries:
                self.transition(
                    session,
                    PipelineState.FAILED,
                    attempt_number=attempt_num,
                    reason="retry budget exhausted",
                )
            else:
                self.transition(
                    session,
                    PipelineState.RETRYING,
                    attempt_number=attempt_num,
                    reason="run_code failed; traceback returned to model",
                )
            return (
                f"FAIL exit_code={result.exit_code}\n"
                f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
            )

        def read_attempt(attempt_number: int) -> str:
            """Return the code and execution result of an earlier attempt, numbered from 1."""
            if not 1 <= attempt_number <= session.attempt_count:
                return f"No attempt {attempt_number}; {session.attempt_count} so far."
            attempt = session.attempts[attempt_number - 1]
            result = attempt.execution_result
            return (
                f"code:\n{attempt.code}\n\nexit_code={result.exit_code}\n"
                f"stderr:\n{result.stderr}"
            )

        def search_past_fixes(error: str) -> str:
            """Find fixes for similar tracebacks from earlier sessions."""
            fixes = self.memory.search(error) if self.memory else []
            self.emit("coder", f"search_past_fixes: {len(fixes)} match(es)")
            return format_fixes(fixes) or "No similar past fixes."

        try:
            run_tool_agent(
                task=session.task,
                plan=plan,
                tools=[run_code, read_attempt, search_past_fixes],
                max_turns=self.max_retries * 3 + 2,
                should_stop=lambda: (
                    session.status in TERMINAL_STATUSES or self.cancel_requested()
                ),
            )
        except Exception as e:
            if session.status not in TERMINAL_STATUSES:
                self.transition(session, PipelineState.FAILED, reason="tool agent failed")
                self.emit("system", f"✗ Tool agent failed: {e}", level="error")
            return session

        if session.status in TERMINAL_STATUSES:
            return session
        if self.cancel_requested():
            return self.cancel_session(session, reason="cancel requested during tool loop")
        self.transition(
            session, PipelineState.FAILED, reason="model stopped without a passing run"
        )
        self.emit("system", "✗ Model stopped calling tools before any run passed.", level="error")
        return session

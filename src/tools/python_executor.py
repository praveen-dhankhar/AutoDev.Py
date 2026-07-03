from __future__ import annotations

import json
import os
import subprocess
import threading
import time
import uuid
from dataclasses import dataclass
from typing import Optional

try:
    from crewai.tools import tool
except ImportError:
    def tool(name: str):
        def decorator(func):
            return func

        return decorator


MAX_OUTPUT_CHARS = 4000
DEFAULT_SANDBOX_IMAGE = "autodev-py-sandbox:latest"
SANDBOX_CONTAINER_PREFIX = "autodev-py-sandbox-"
SANDBOX_WORKDIR = "/workspace"
SANDBOX_TMPFS_SIZE = "16m"
SANDBOX_MEMORY = "128m"
SANDBOX_CPUS = "1"
SANDBOX_PIDS_LIMIT = "64"


@dataclass
class ExecutorInput:
    script_path: str
    timeout_seconds: int = 30
    working_directory: Optional[str] = None
    cancel_event: Optional[threading.Event] = None


@dataclass
class ExecutorOutput:
    status: str
    stdout: str
    stderr: str
    exit_code: int
    execution_time_ms: float


def _truncate(value: Optional[str]) -> str:
    return (value or "")[:MAX_OUTPUT_CHARS]


def _env_flag_enabled(name: str) -> bool:
    return os.getenv(name, "").strip().lower() in {"1", "true", "yes", "on"}


class SandboxedPythonExecutor:
    name: str = "python_executor"
    description: str = (
        "Executes a Python script inside a constrained Docker sandbox. Returns "
        "stdout, stderr, exit_code, execution_time_ms, and execution status."
    )

    def run(self, input: ExecutorInput) -> ExecutorOutput:
        if not os.path.exists(input.script_path):
            return ExecutorOutput(
                status="fail",
                stdout="",
                stderr=f"FileNotFoundError: {input.script_path} does not exist",
                exit_code=1,
                execution_time_ms=0.0,
            )

        with open(input.script_path, "r", encoding="utf-8") as script_file:
            code = script_file.read()

        start = time.monotonic()
        image = os.getenv("SANDBOX_IMAGE", DEFAULT_SANDBOX_IMAGE)
        container_name = f"{SANDBOX_CONTAINER_PREFIX}{uuid.uuid4().hex[:12]}"

        image_error = self._image_unavailable_reason(image)
        if image_error:
            return ExecutorOutput(
                status="fail",
                stdout="",
                stderr=image_error,
                exit_code=127,
                execution_time_ms=round((time.monotonic() - start) * 1000, 2),
            )

        command = self.build_docker_command(image=image, container_name=container_name)

        if self._cancel_requested(input.cancel_event):
            return self._cancelled_output(start)

        try:
            if input.cancel_event is not None:
                return self._run_cancelable(
                    command=command,
                    code=code,
                    timeout_seconds=input.timeout_seconds,
                    container_name=container_name,
                    start=start,
                    cancel_event=input.cancel_event,
                )

            result = subprocess.run(
                command,
                input=code,
                capture_output=True,
                text=True,
                timeout=input.timeout_seconds,
            )
            execution_time_ms = (time.monotonic() - start) * 1000
            status = "pass" if result.returncode == 0 else "fail"
            return ExecutorOutput(
                status=status,
                stdout=_truncate(result.stdout),
                stderr=_truncate(result.stderr),
                exit_code=result.returncode,
                execution_time_ms=round(execution_time_ms, 2),
            )
        except subprocess.TimeoutExpired:
            self._force_remove_container(container_name)
            execution_time_ms = (time.monotonic() - start) * 1000
            return ExecutorOutput(
                status="fail",
                stdout="",
                stderr=f"TimeoutError: Script exceeded {input.timeout_seconds}s limit",
                exit_code=-1,
                execution_time_ms=round(execution_time_ms, 2),
            )
        except FileNotFoundError as exc:
            execution_time_ms = (time.monotonic() - start) * 1000
            return ExecutorOutput(
                status="fail",
                stdout="",
                stderr=f"DockerUnavailable: docker CLI was not found: {exc}",
                exit_code=127,
                execution_time_ms=round(execution_time_ms, 2),
            )
        except OSError as exc:
            execution_time_ms = (time.monotonic() - start) * 1000
            return ExecutorOutput(
                status="fail",
                stdout="",
                stderr=f"DockerUnavailable: could not start sandbox: {exc}",
                exit_code=127,
                execution_time_ms=round(execution_time_ms, 2),
            )

    def _run_cancelable(
        self,
        *,
        command: list[str],
        code: str,
        timeout_seconds: int,
        container_name: str,
        start: float,
        cancel_event: threading.Event,
    ) -> ExecutorOutput:
        process = subprocess.Popen(
            command,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        deadline = time.monotonic() + timeout_seconds
        pending_input: Optional[str] = code

        while True:
            if self._cancel_requested(cancel_event):
                self._force_remove_container(container_name)
                stdout, stderr = self._drain_process(process)
                return ExecutorOutput(
                    status="cancelled",
                    stdout=_truncate(stdout),
                    stderr=_truncate(stderr) or "Cancelled: sandbox execution stopped",
                    exit_code=-2,
                    execution_time_ms=round((time.monotonic() - start) * 1000, 2),
                )

            remaining = deadline - time.monotonic()
            if remaining <= 0:
                self._force_remove_container(container_name)
                self._drain_process(process)
                execution_time_ms = (time.monotonic() - start) * 1000
                return ExecutorOutput(
                    status="fail",
                    stdout="",
                    stderr=f"TimeoutError: Script exceeded {timeout_seconds}s limit",
                    exit_code=-1,
                    execution_time_ms=round(execution_time_ms, 2),
                )

            try:
                stdout, stderr = process.communicate(
                    input=pending_input,
                    timeout=min(0.2, remaining),
                )
                execution_time_ms = (time.monotonic() - start) * 1000
                return ExecutorOutput(
                    status="pass" if process.returncode == 0 else "fail",
                    stdout=_truncate(stdout),
                    stderr=_truncate(stderr),
                    exit_code=process.returncode,
                    execution_time_ms=round(execution_time_ms, 2),
                )
            except subprocess.TimeoutExpired:
                pending_input = None

    def build_docker_command(self, image: str, container_name: str) -> list[str]:
        network_mode = "bridge" if self._local_network_allowed() else "none"
        return [
            "docker",
            "run",
            "--rm",
            "--pull=never",
            "--name",
            container_name,
            "--network",
            network_mode,
            "--cpus",
            SANDBOX_CPUS,
            "--memory",
            SANDBOX_MEMORY,
            "--memory-swap",
            SANDBOX_MEMORY,
            "--pids-limit",
            SANDBOX_PIDS_LIMIT,
            "--read-only",
            "--cap-drop",
            "ALL",
            "--security-opt",
            "no-new-privileges",
            "--user",
            "1000:1000",
            "--workdir",
            SANDBOX_WORKDIR,
            "--tmpfs",
            (
                f"{SANDBOX_WORKDIR}:rw,noexec,nosuid,nodev,"
                f"size={SANDBOX_TMPFS_SIZE},mode=1777"
            ),
            "--tmpfs",
            f"/tmp:rw,noexec,nosuid,nodev,size={SANDBOX_TMPFS_SIZE},mode=1777",
            "-e",
            "PYTHONDONTWRITEBYTECODE=1",
            "-e",
            "PYTHONUNBUFFERED=1",
            "-i",
            image,
            "python",
            "-I",
            "-B",
            "-",
        ]

    def _local_network_allowed(self) -> bool:
        if _env_flag_enabled("CI"):
            return False
        return _env_flag_enabled("SANDBOX_ALLOW_NETWORK")

    def _cancel_requested(self, cancel_event: Optional[threading.Event]) -> bool:
        return cancel_event is not None and cancel_event.is_set()

    def _cancelled_output(self, start: float) -> ExecutorOutput:
        return ExecutorOutput(
            status="cancelled",
            stdout="",
            stderr="Cancelled: sandbox execution was not started",
            exit_code=-2,
            execution_time_ms=round((time.monotonic() - start) * 1000, 2),
        )

    def _image_unavailable_reason(self, image: str) -> Optional[str]:
        try:
            result = subprocess.run(
                ["docker", "image", "inspect", image],
                capture_output=True,
                text=True,
                timeout=10,
            )
        except FileNotFoundError as exc:
            return f"DockerUnavailable: docker CLI was not found: {exc}"
        except subprocess.TimeoutExpired:
            return "DockerUnavailable: timed out while checking the sandbox image"
        except OSError as exc:
            return f"DockerUnavailable: could not inspect sandbox image: {exc}"

        if result.returncode != 0:
            detail = _truncate(result.stderr or result.stdout).strip()
            if "docker daemon" in detail.lower() or "cannot connect" in detail.lower():
                return f"DockerUnavailable: Docker daemon is not available. {detail}"
            return (
                f"SandboxImageUnavailable: Docker image {image!r} is not ready. "
                f"Build it with: docker build -f sandbox.Dockerfile "
                f"-t {image} . {detail}"
            )
        return None

    def _force_remove_container(self, container_name: str) -> None:
        try:
            subprocess.run(
                ["docker", "rm", "-f", container_name],
                capture_output=True,
                text=True,
                timeout=5,
            )
        except (FileNotFoundError, OSError, subprocess.TimeoutExpired):
            return None

    def _drain_process(self, process: subprocess.Popen) -> tuple[str, str]:
        try:
            return process.communicate(timeout=5)
        except subprocess.TimeoutExpired:
            try:
                process.kill()
                return process.communicate(timeout=5)
            except (OSError, subprocess.TimeoutExpired):
                return "", ""


class PythonExecutorTool(SandboxedPythonExecutor):
    """Backward-compatible executor name used by QA and CrewAI tooling."""


@tool("python_executor")
def python_executor_tool(script_path: str) -> str:
    """
    Executes a Python script at the given absolute path.
    Returns a JSON string containing: status, stdout, stderr, exit_code, execution_time_ms.
    Use this to validate that generated code runs correctly.
    """
    executor = PythonExecutorTool()
    result = executor.run(
        ExecutorInput(
            script_path=script_path,
            timeout_seconds=int(os.getenv("SUBPROCESS_TIMEOUT", 30)),
        )
    )
    return json.dumps(
        {
            "status": result.status,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "exit_code": result.exit_code,
            "execution_time_ms": result.execution_time_ms,
        }
    )

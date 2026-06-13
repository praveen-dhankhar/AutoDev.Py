from __future__ import annotations

import json
import os
import subprocess
import time
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


@dataclass
class ExecutorInput:
    script_path: str
    timeout_seconds: int = 30
    working_directory: Optional[str] = None


@dataclass
class ExecutorOutput:
    status: str
    stdout: str
    stderr: str
    exit_code: int
    execution_time_ms: float


class PythonExecutorTool:
    name: str = "python_executor"
    description: str = (
        "Executes a Python script at the given absolute path. Returns stdout, "
        "stderr, exit_code, execution_time_ms, and execution status."
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

        start = time.monotonic()
        clean_env = {
            "PATH": os.environ.get("PATH", ""),
            "HOME": os.environ.get("HOME", ""),
            "PYTHONDONTWRITEBYTECODE": "1",
        }

        try:
            result = subprocess.run(
                ["python3", input.script_path],
                capture_output=True,
                text=True,
                timeout=input.timeout_seconds,
                cwd=input.working_directory,
                env=clean_env,
            )
            execution_time_ms = (time.monotonic() - start) * 1000
            status = "pass" if result.returncode == 0 else "fail"
            return ExecutorOutput(
                status=status,
                stdout=result.stdout[:MAX_OUTPUT_CHARS],
                stderr=result.stderr[:MAX_OUTPUT_CHARS],
                exit_code=result.returncode,
                execution_time_ms=round(execution_time_ms, 2),
            )
        except subprocess.TimeoutExpired:
            execution_time_ms = (time.monotonic() - start) * 1000
            return ExecutorOutput(
                status="fail",
                stdout="",
                stderr=f"TimeoutError: Script exceeded {input.timeout_seconds}s limit",
                exit_code=-1,
                execution_time_ms=round(execution_time_ms, 2),
            )


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

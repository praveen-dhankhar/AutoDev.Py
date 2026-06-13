import os

from src.models import ExecutionResult
from src.tools.python_executor import ExecutorInput, PythonExecutorTool


def run_qa(script_path: str) -> ExecutionResult:
    executor = PythonExecutorTool()
    output = executor.run(
        ExecutorInput(
            script_path=script_path,
            timeout_seconds=int(os.getenv("SUBPROCESS_TIMEOUT", 30)),
        )
    )
    return ExecutionResult(
        status=output.status,
        stdout=output.stdout,
        stderr=output.stderr,
        exit_code=output.exit_code,
        execution_time_ms=output.execution_time_ms,
        script_path=script_path,
    )

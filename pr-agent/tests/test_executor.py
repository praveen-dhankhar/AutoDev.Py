import os
import sys
import tempfile
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.tools.python_executor import ExecutorInput, PythonExecutorTool


def write_temp_script(code: str) -> str:
    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
        f.write(code)
        return f.name


def test_executor_passes_script():
    script_path = write_temp_script('print("hello world")')
    try:
        result = PythonExecutorTool().run(ExecutorInput(script_path=script_path))
        assert result.status == "pass"
        assert "hello world" in result.stdout
        assert result.exit_code == 0
    finally:
        os.unlink(script_path)


def test_executor_fails_script():
    script_path = write_temp_script("x = undefined_variable")
    try:
        result = PythonExecutorTool().run(ExecutorInput(script_path=script_path))
        assert result.status == "fail"
        assert "NameError" in result.stderr
    finally:
        os.unlink(script_path)


def test_executor_times_out_script():
    script_path = write_temp_script("import time; time.sleep(999)")
    try:
        result = PythonExecutorTool().run(
            ExecutorInput(script_path=script_path, timeout_seconds=2)
        )
        assert result.status == "fail"
        assert "TimeoutError" in result.stderr
    finally:
        os.unlink(script_path)

import os
import subprocess
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.tools.python_executor import (
    ExecutorInput,
    PythonExecutorTool,
    SANDBOX_CONTAINER_PREFIX,
    SandboxedPythonExecutor,
)


def write_temp_script(code: str) -> str:
    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
        f.write(code)
        return f.name


def completed_process(returncode: int = 0, stdout: str = "", stderr: str = ""):
    return subprocess.CompletedProcess(
        args=["docker"],
        returncode=returncode,
        stdout=stdout,
        stderr=stderr,
    )


def test_executor_passes_script():
    script_path = write_temp_script('print("hello world")')
    try:
        with patch("src.tools.python_executor.subprocess.run") as run_mock:
            run_mock.side_effect = [
                completed_process(),
                completed_process(stdout="hello world\n"),
            ]

            result = PythonExecutorTool().run(ExecutorInput(script_path=script_path))

        assert result.status == "pass"
        assert "hello world" in result.stdout
        assert result.exit_code == 0

        docker_run_call = run_mock.call_args_list[1]
        assert docker_run_call.kwargs["input"] == 'print("hello world")'
        assert docker_run_call.kwargs["timeout"] == 30
    finally:
        os.unlink(script_path)


def test_executor_fails_script():
    script_path = write_temp_script("x = undefined_variable")
    try:
        with patch("src.tools.python_executor.subprocess.run") as run_mock:
            run_mock.side_effect = [
                completed_process(),
                completed_process(returncode=1, stderr="NameError: undefined_variable"),
            ]

            result = PythonExecutorTool().run(ExecutorInput(script_path=script_path))

        assert result.status == "fail"
        assert "NameError" in result.stderr
    finally:
        os.unlink(script_path)


def test_executor_times_out_script():
    script_path = write_temp_script("import time; time.sleep(999)")
    try:
        with patch("src.tools.python_executor.subprocess.run") as run_mock:
            run_mock.side_effect = [
                completed_process(),
                subprocess.TimeoutExpired(cmd=["docker", "run"], timeout=2),
                completed_process(),
            ]

            result = PythonExecutorTool().run(
                ExecutorInput(script_path=script_path, timeout_seconds=2)
            )

        assert result.status == "fail"
        assert "TimeoutError" in result.stderr
        cleanup_call = run_mock.call_args_list[2]
        assert cleanup_call.args[0][:3] == ["docker", "rm", "-f"]
        assert cleanup_call.args[0][3].startswith(SANDBOX_CONTAINER_PREFIX)
    finally:
        os.unlink(script_path)


def test_executor_fails_closed_when_docker_daemon_is_unavailable():
    script_path = write_temp_script('print("should not run")')
    try:
        with patch("src.tools.python_executor.subprocess.run") as run_mock:
            run_mock.return_value = completed_process(
                returncode=1,
                stderr="Cannot connect to the Docker daemon",
            )

            result = PythonExecutorTool().run(ExecutorInput(script_path=script_path))

        assert result.status == "fail"
        assert result.exit_code == 127
        assert "DockerUnavailable" in result.stderr
        assert run_mock.call_count == 1
    finally:
        os.unlink(script_path)


def test_executor_fails_closed_when_sandbox_image_is_missing():
    script_path = write_temp_script('print("should not run")')
    try:
        with patch("src.tools.python_executor.subprocess.run") as run_mock:
            run_mock.return_value = completed_process(
                returncode=1,
                stderr="No such image: autodev-py-sandbox:latest",
            )

            result = PythonExecutorTool().run(ExecutorInput(script_path=script_path))

        assert result.status == "fail"
        assert result.exit_code == 127
        assert "SandboxImageUnavailable" in result.stderr
        assert run_mock.call_count == 1
    finally:
        os.unlink(script_path)


def test_sandbox_command_enforces_default_restrictions(monkeypatch):
    monkeypatch.delenv("SANDBOX_ALLOW_NETWORK", raising=False)
    monkeypatch.delenv("CI", raising=False)

    command = SandboxedPythonExecutor().build_docker_command(
        image="autodev-py-sandbox:test",
        container_name="autodev-py-sandbox-test",
    )

    assert "--network" in command
    assert command[command.index("--network") + 1] == "none"
    assert "--read-only" in command
    assert command[command.index("--cap-drop") + 1] == "ALL"
    assert command[command.index("--security-opt") + 1] == "no-new-privileges"
    assert command[command.index("--memory") + 1] == "128m"
    assert command[command.index("--memory-swap") + 1] == "128m"
    assert command[command.index("--pids-limit") + 1] == "64"
    assert command[command.index("--user") + 1] == "1000:1000"
    assert command[command.index("--workdir") + 1] == "/workspace"
    assert "-v" not in command
    assert "--volume" not in command
    assert "--mount" not in command


def test_ci_forces_network_none_even_when_local_network_is_enabled(monkeypatch):
    monkeypatch.setenv("SANDBOX_ALLOW_NETWORK", "1")
    monkeypatch.setenv("CI", "true")

    command = SandboxedPythonExecutor().build_docker_command(
        image="autodev-py-sandbox:test",
        container_name="autodev-py-sandbox-test",
    )

    assert command[command.index("--network") + 1] == "none"


def test_local_network_can_be_opted_in(monkeypatch):
    monkeypatch.setenv("SANDBOX_ALLOW_NETWORK", "1")
    monkeypatch.delenv("CI", raising=False)

    command = SandboxedPythonExecutor().build_docker_command(
        image="autodev-py-sandbox:test",
        container_name="autodev-py-sandbox-test",
    )

    assert command[command.index("--network") + 1] == "bridge"

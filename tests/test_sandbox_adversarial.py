import os
import subprocess
import sys
from pathlib import Path

import pytest


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.tools.python_executor import (  # noqa: E402
    DEFAULT_SANDBOX_IMAGE,
    ExecutorInput,
    PythonExecutorTool,
    SANDBOX_CONTAINER_PREFIX,
)


def sandbox_required() -> bool:
    return os.getenv("SANDBOX_REQUIRED") == "1" or os.getenv("CI") == "true"


def docker_command(args: list[str], timeout: int = 10) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["docker", *args],
        capture_output=True,
        text=True,
        timeout=timeout,
    )


def sandbox_image() -> str:
    return os.getenv("SANDBOX_IMAGE", DEFAULT_SANDBOX_IMAGE)


def require_docker_sandbox() -> str:
    try:
        info = docker_command(["info"], timeout=10)
    except (FileNotFoundError, OSError, subprocess.TimeoutExpired) as exc:
        if sandbox_required():
            pytest.fail(f"Docker is required for sandbox tests: {exc}")
        pytest.skip(f"Docker is not available locally: {exc}")

    if info.returncode != 0:
        if sandbox_required():
            pytest.fail(f"Docker is required for sandbox tests: {info.stderr}")
        pytest.skip(f"Docker daemon is not available locally: {info.stderr}")

    image = sandbox_image()
    inspect = docker_command(["image", "inspect", image], timeout=10)
    if inspect.returncode != 0:
        if sandbox_required():
            pytest.fail(f"Sandbox image {image!r} is required: {inspect.stderr}")
        pytest.skip(f"Sandbox image {image!r} is not built locally")

    return image


def sandbox_container_ids() -> list[str]:
    result = docker_command(
        [
            "ps",
            "-aq",
            "--filter",
            f"name={SANDBOX_CONTAINER_PREFIX}",
            "--format",
            "{{.ID}}",
        ],
        timeout=10,
    )
    if result.returncode != 0:
        return []
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def remove_sandbox_containers() -> None:
    ids = sandbox_container_ids()
    if ids:
        docker_command(["rm", "-f", *ids], timeout=10)


@pytest.fixture(scope="module")
def docker_sandbox_image():
    return require_docker_sandbox()


@pytest.fixture(autouse=True)
def assert_no_sandbox_container_leaks(docker_sandbox_image):
    remove_sandbox_containers()
    yield
    remaining = sandbox_container_ids()
    try:
        assert remaining == []
    finally:
        if remaining:
            remove_sandbox_containers()


def host_marker_probe(marker: Path) -> str:
    marker_literal = str(marker)
    return f"""
import os

_host_marker = {marker_literal!r}
try:
    os.makedirs(os.path.dirname(_host_marker), exist_ok=True)
    with open(_host_marker, "w", encoding="utf-8") as marker_file:
        marker_file.write("escaped")
    print("HOST_MARKER_WRITE_ATTEMPTED", flush=True)
except Exception as exc:
    print("HOST_MARKER_BLOCKED", type(exc).__name__, flush=True)
"""


def run_payload(tmp_path: Path, payload: str, host_marker: Path, timeout: int = 4):
    script_path = tmp_path / "payload.py"
    script_path.write_text(host_marker_probe(host_marker) + "\n" + payload)

    result = PythonExecutorTool().run(
        ExecutorInput(script_path=str(script_path), timeout_seconds=timeout)
    )

    assert not host_marker.exists()
    return result


def output_text(result) -> str:
    return f"{result.stdout}\n{result.stderr}"


def assert_safely_contained(result, host_marker: Path, success_marker: str) -> None:
    combined = output_text(result)
    assert not host_marker.exists()
    assert success_marker not in combined
    assert result.status == "fail" or "BLOCKED" in combined


@pytest.mark.docker
def test_outbound_network_call_is_blocked(tmp_path, monkeypatch, docker_sandbox_image):
    monkeypatch.setenv("SANDBOX_IMAGE", docker_sandbox_image)
    monkeypatch.setenv("SANDBOX_ALLOW_NETWORK", "0")
    host_marker = Path.cwd() / ".sandbox-network-escape"
    host_marker.unlink(missing_ok=True)

    result = run_payload(
        tmp_path,
        """
import urllib.request

try:
    urllib.request.urlopen("http://example.com", timeout=2)
    print("NETWORK_SUCCEEDED", flush=True)
except Exception as exc:
    print("NETWORK_BLOCKED", type(exc).__name__, flush=True)
""",
        host_marker,
        timeout=5,
    )

    assert_safely_contained(result, host_marker, "NETWORK_SUCCEEDED")
    host_marker.unlink(missing_ok=True)


@pytest.mark.docker
def test_process_storm_is_capped_by_pid_limit(tmp_path, monkeypatch, docker_sandbox_image):
    monkeypatch.setenv("SANDBOX_IMAGE", docker_sandbox_image)
    host_marker = Path.cwd() / ".sandbox-fork-escape"
    host_marker.unlink(missing_ok=True)

    result = run_payload(
        tmp_path,
        """
import os
import sys
import time

children = []
try:
    for _ in range(512):
        pid = os.fork()
        if pid == 0:
            time.sleep(30)
            sys.exit(0)
        children.append(pid)
    print("FORK_SUCCEEDED", len(children), flush=True)
except OSError as exc:
    print("FORK_BLOCKED", len(children), type(exc).__name__, flush=True)
""",
        host_marker,
        timeout=6,
    )

    assert_safely_contained(result, host_marker, "FORK_SUCCEEDED")
    host_marker.unlink(missing_ok=True)


@pytest.mark.docker
def test_disk_fill_is_capped_by_tmpfs_limit(tmp_path, monkeypatch, docker_sandbox_image):
    monkeypatch.setenv("SANDBOX_IMAGE", docker_sandbox_image)
    host_marker = Path.cwd() / ".sandbox-disk-escape"
    host_marker.unlink(missing_ok=True)

    result = run_payload(
        tmp_path,
        """
try:
    with open("/workspace/fill.bin", "wb") as output:
        for _ in range(64):
            output.write(b"x" * 1024 * 1024)
            output.flush()
    print("DISK_FILL_SUCCEEDED", flush=True)
except OSError as exc:
    print("DISK_BLOCKED", getattr(exc, "errno", "unknown"), flush=True)
""",
        host_marker,
        timeout=5,
    )

    assert_safely_contained(result, host_marker, "DISK_FILL_SUCCEEDED")
    host_marker.unlink(missing_ok=True)


@pytest.mark.docker
def test_infinite_loop_is_killed_by_timeout(tmp_path, monkeypatch, docker_sandbox_image):
    monkeypatch.setenv("SANDBOX_IMAGE", docker_sandbox_image)
    host_marker = Path.cwd() / ".sandbox-loop-escape"
    host_marker.unlink(missing_ok=True)

    result = run_payload(
        tmp_path,
        """
while True:
    pass
""",
        host_marker,
        timeout=2,
    )

    assert result.status == "fail"
    assert result.exit_code == -1
    assert "TimeoutError" in result.stderr
    assert not host_marker.exists()
    host_marker.unlink(missing_ok=True)


@pytest.mark.docker
def test_passwd_read_is_container_scoped(tmp_path, monkeypatch, docker_sandbox_image):
    monkeypatch.setenv("SANDBOX_IMAGE", docker_sandbox_image)
    host_marker = Path.cwd() / ".sandbox-passwd-escape"
    host_marker.unlink(missing_ok=True)

    result = run_payload(
        tmp_path,
        """
with open("/etc/passwd", "r", encoding="utf-8") as passwd_file:
    print(passwd_file.read(), flush=True)
""",
        host_marker,
        timeout=4,
    )

    combined = output_text(result)
    assert result.status == "pass"
    assert "sandbox:" in combined
    assert "praveendhankhar" not in combined
    assert "/Users/" not in combined
    assert "/home/runner/work/" not in combined
    assert not host_marker.exists()
    host_marker.unlink(missing_ok=True)


@pytest.mark.docker
def test_memory_exhaustion_is_capped(tmp_path, monkeypatch, docker_sandbox_image):
    monkeypatch.setenv("SANDBOX_IMAGE", docker_sandbox_image)
    host_marker = Path.cwd() / ".sandbox-memory-escape"
    host_marker.unlink(missing_ok=True)

    result = run_payload(
        tmp_path,
        """
chunks = []
try:
    while True:
        chunks.append(bytearray(8 * 1024 * 1024))
        if len(chunks) > 64:
            print("MEMORY_SUCCEEDED", flush=True)
            break
except MemoryError:
    print("MEMORY_BLOCKED", flush=True)
""",
        host_marker,
        timeout=6,
    )

    assert_safely_contained(result, host_marker, "MEMORY_SUCCEEDED")
    host_marker.unlink(missing_ok=True)

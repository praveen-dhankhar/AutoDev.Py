import sys
import urllib.error
from pathlib import Path
from unittest.mock import patch


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.health import check_ollama_health  # noqa: E402


class FakeResponse:
    def __init__(self, status: int):
        self.status = status

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False


def test_check_ollama_health_reports_online():
    with patch("src.health.urllib.request.urlopen", return_value=FakeResponse(200)) as urlopen:
        result = check_ollama_health("http://localhost:11434")

    assert result.healthy is True
    assert "reachable" in result.message
    assert urlopen.call_args.args[0] == "http://localhost:11434/api/tags"


def test_check_ollama_health_reports_unavailable():
    with patch(
        "src.health.urllib.request.urlopen",
        side_effect=urllib.error.URLError("connection refused"),
    ):
        result = check_ollama_health("http://localhost:11434")

    assert result.healthy is False
    assert "connection refused" in result.message

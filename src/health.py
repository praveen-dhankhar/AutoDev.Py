from __future__ import annotations

import urllib.error
import urllib.request
from dataclasses import dataclass

from src.config import OLLAMA_BASE_URL


@dataclass(frozen=True)
class HealthStatus:
    healthy: bool
    message: str


def check_ollama_health(
    base_url: str = OLLAMA_BASE_URL,
    timeout_seconds: float = 1.5,
) -> HealthStatus:
    url = f"{base_url.rstrip('/')}/api/tags"
    try:
        with urllib.request.urlopen(url, timeout=timeout_seconds) as response:
            status = getattr(response, "status", 200)
            if 200 <= status < 400:
                return HealthStatus(True, f"Ollama reachable at {base_url}")
            return HealthStatus(False, f"Ollama returned HTTP {status}")
    except urllib.error.URLError as exc:
        return HealthStatus(False, f"Ollama unavailable: {exc.reason}")
    except TimeoutError:
        return HealthStatus(False, "Ollama health check timed out")
    except OSError as exc:
        return HealthStatus(False, f"Ollama unavailable: {exc}")

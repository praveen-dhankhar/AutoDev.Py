"""Long-term memory: traceback-and-fix pairs retrieved by embedding similarity."""

from __future__ import annotations

import json
import math
import urllib.request
from pathlib import Path
from typing import Callable

from src.config import EMBED_MODEL, OLLAMA_BASE_URL

MIN_SCORE = 0.6
EMBED_CHARS = 2000  # tracebacks end with the useful part, so embed the tail


def ollama_embed(text: str) -> list[float]:
    request = urllib.request.Request(
        f"{OLLAMA_BASE_URL.rstrip('/')}/api/embed",
        data=json.dumps({"model": EMBED_MODEL, "input": text}).encode(),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.load(response)["embeddings"][0]


def _cosine(a: list[float], b: list[float]) -> float:
    if len(a) != len(b):  # stored with a different EMBED_MODEL
        return 0.0
    norm = math.sqrt(sum(x * x for x in a)) * math.sqrt(sum(y * y for y in b))
    return sum(x * y for x, y in zip(a, b, strict=True)) / norm if norm else 0.0


class FixMemory:
    """JSONL store of {task, error, fixed_code, embedding} records.

    Embedding failures (Ollama down, model not pulled) degrade to "no memory"
    instead of failing the run.
    """

    # NOTE: linear scan over a JSONL file; move to sqlite-vec/chromadb past ~10k fixes.

    def __init__(self, path: str | Path, embed: Callable[[str], list[float]] = ollama_embed):
        self.path = Path(path)
        self.embed = embed

    def add(self, *, task: str, error: str, fixed_code: str) -> bool:
        try:
            vector = self.embed(error[-EMBED_CHARS:])
        except Exception:
            return False
        record = {"task": task, "error": error, "fixed_code": fixed_code, "embedding": vector}
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record) + "\n")
        return True

    def search(self, error: str, k: int = 2, min_score: float = MIN_SCORE) -> list[dict]:
        if not self.path.exists():
            return []
        try:
            query = self.embed(error[-EMBED_CHARS:])
        except Exception:
            return []

        scored = []
        for line in self.path.read_text(encoding="utf-8").splitlines():
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue
            score = _cosine(query, record.pop("embedding", []))
            if score >= min_score:
                scored.append({**record, "score": round(score, 3)})
        return sorted(scored, key=lambda r: r["score"], reverse=True)[:k]


def format_fixes(fixes: list[dict]) -> str:
    if not fixes:
        return ""
    parts = ["Similar errors were fixed in earlier sessions. Use them as hints, not as answers:"]
    for i, fix in enumerate(fixes, 1):
        parts.append(
            f"--- Past fix {i} (similarity {fix['score']}) ---\n"
            f"Error:\n{fix['error'][-800:]}\n"
            f"Fixed code:\n{fix['fixed_code'][:1500]}"
        )
    return "\n\n".join(parts)

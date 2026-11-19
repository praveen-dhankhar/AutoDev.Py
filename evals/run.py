"""Benchmark the self-correction loop on MBPP-style tasks.

    python -m evals.run --limit 20
    python -m evals.run --conditions feedback,no-feedback,memory --mode tools

Conditions:
  feedback     retries see the previous traceback (normal behaviour)
  no-feedback  retries regenerate from the task alone (ablation baseline)
  memory       feedback plus long-term fix memory, starting from an empty store

The task prompt doubles as the plan, so the Architect is skipped and the
numbers isolate the Coder -> sandbox -> retry loop. Compare models by
re-running with a different OLLAMA_MODEL or LLM_MODEL.
"""

from __future__ import annotations

import argparse
import json
import queue
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

from evals.tasks import TASKS
from src.agents.qa import run_qa
from src.config import LLM_MODEL, MAX_RETRIES, OLLAMA_BASE_URL, OLLAMA_MODEL
from src.health import check_ollama_health
from src.orchestrator import Orchestrator

RESULTS_DIR = Path(__file__).with_name("results")
CONDITIONS = {
    "feedback": {"feedback": True, "use_memory": False},
    "no-feedback": {"feedback": False, "use_memory": False},
    "memory": {"feedback": True, "use_memory": True},
}


def task_prompt(task: dict) -> str:
    return f"{task['prompt']}\nYour code should pass these tests:\n" + "\n".join(task["tests"])


def run_task(task: dict, *, workspace_dir: str, max_retries: int, mode: str, **condition) -> dict:
    prompt = task_prompt(task)
    start = time.monotonic()
    session = Orchestrator(
        log_queue=queue.Queue(),
        max_retries=max_retries,
        workspace_dir=workspace_dir,
        mode=mode,
        **condition,
    ).run(prompt, plan=prompt, test_code="\n".join(task["tests"]))
    return {
        "id": task["id"],
        "passed": session.final_code is not None,
        "attempts": session.attempt_count,
        "status": session.status,
        "seconds": round(time.monotonic() - start, 1),
    }


def summarize(results: list[dict]) -> dict:
    n = len(results) or 1
    return {
        "tasks": len(results),
        "first_try_pass_rate": round(
            sum(r["passed"] and r["attempts"] == 1 for r in results) / n, 3
        ),
        "final_pass_rate": round(sum(r["passed"] for r in results) / n, 3),
        "avg_retries": round(sum(max(r["attempts"] - 1, 0) for r in results) / n, 2),
    }


def format_table(report: dict) -> str:
    lines = [
        "| Condition | Tasks | First-try pass | Pass after retries | Avg retries |",
        "|---|---:|---:|---:|---:|",
    ]
    for name, data in report["conditions"].items():
        s = data["summary"]
        lines.append(
            f"| {name} | {s['tasks']} | {s['first_try_pass_rate']:.1%} | "
            f"{s['final_pass_rate']:.1%} | {s['avg_retries']} |"
        )
    if "feedback_lift" in report:
        lines.append(f"\nTraceback feedback lift: {report['feedback_lift']:+.1%}")
    return "\n".join(lines)


def preflight() -> str | None:
    if not LLM_MODEL:
        health = check_ollama_health(OLLAMA_BASE_URL)
        if not health.healthy:
            return health.message
    with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False) as f:
        f.write("print('ok')\n")
    result = run_qa(f.name)
    Path(f.name).unlink()
    return None if result.status == "pass" else f"Sandbox check failed: {result.stderr}"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m evals.run", description=__doc__.split("\n")[0])
    parser.add_argument("--limit", type=int, help="Run only the first N tasks.")
    parser.add_argument("--conditions", default="feedback,no-feedback")
    parser.add_argument("--mode", choices=["classic", "tools"], default="classic")
    parser.add_argument("--max-retries", type=int, default=MAX_RETRIES)
    parser.add_argument("--out", type=Path, help="Results JSON path.")
    args = parser.parse_args(argv)

    conditions = args.conditions.split(",")
    unknown = set(conditions) - CONDITIONS.keys()
    if unknown:
        parser.error(f"unknown conditions: {', '.join(sorted(unknown))}")
    problem = preflight()
    if problem:
        print(problem)
        return 2

    tasks = TASKS[: args.limit]
    report = {
        "model": LLM_MODEL or f"ollama/{OLLAMA_MODEL}",
        "mode": args.mode,
        "max_retries": args.max_retries,
        "started_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "conditions": {},
    }
    with tempfile.TemporaryDirectory() as tmp:
        for name in conditions:
            results = []
            for i, task in enumerate(tasks, 1):
                result = run_task(
                    task,
                    workspace_dir=f"{tmp}/{name}",
                    max_retries=args.max_retries,
                    mode=args.mode,
                    **CONDITIONS[name],
                )
                results.append(result)
                verdict = "PASS" if result["passed"] else "FAIL"
                print(f"[{name}] {i}/{len(tasks)} {task['id']}: {verdict} "
                      f"({result['attempts']} attempts)", flush=True)
            report["conditions"][name] = {"summary": summarize(results), "results": results}

    summaries = {name: data["summary"] for name, data in report["conditions"].items()}
    if {"feedback", "no-feedback"} <= summaries.keys():
        report["feedback_lift"] = round(
            summaries["feedback"]["final_pass_rate"] - summaries["no-feedback"]["final_pass_rate"], 3
        )

    out = args.out or RESULTS_DIR / f"eval_{datetime.now():%Y%m%d-%H%M%S}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(format_table(report))
    print(f"Results: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

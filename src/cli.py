from __future__ import annotations

import argparse
import queue
import subprocess
import sys
from pathlib import Path
from typing import Sequence

from src import __version__
from src.config import MAX_RETRIES, OLLAMA_BASE_URL, WORKSPACE_DIR
from src.health import check_ollama_health
from src.orchestrator import Orchestrator


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="pr-agent",
        description="Run AutoDev.py from the command line.",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    run_parser = subparsers.add_parser(
        "run",
        help="Run the agent pipeline for a task.",
    )
    run_parser.add_argument("task", help="Natural language task for the agent.")
    run_parser.add_argument(
        "--workspace-dir",
        default=WORKSPACE_DIR,
        help=f"Directory for run artifacts. Defaults to {WORKSPACE_DIR!r}.",
    )
    run_parser.add_argument(
        "--max-retries",
        type=int,
        default=MAX_RETRIES,
        help=f"Maximum correction attempts. Defaults to {MAX_RETRIES}.",
    )
    run_parser.add_argument(
        "--quiet",
        action="store_true",
        help="Suppress log output and print only the final summary.",
    )
    run_parser.add_argument(
        "--skip-health-check",
        action="store_true",
        help="Skip the Ollama preflight check.",
    )
    run_parser.set_defaults(func=run_command)

    ui_parser = subparsers.add_parser(
        "ui",
        help="Launch the Streamlit dashboard.",
    )
    ui_parser.add_argument(
        "--server-address",
        default="localhost",
        help="Streamlit server address.",
    )
    ui_parser.add_argument(
        "--server-port",
        type=int,
        default=8501,
        help="Streamlit server port.",
    )
    ui_parser.set_defaults(func=ui_command)

    return parser


def run_command(args: argparse.Namespace) -> int:
    if not args.skip_health_check:
        health = check_ollama_health(OLLAMA_BASE_URL)
        if not health.healthy:
            print(health.message, file=sys.stderr)
            return 2

    log_queue: queue.Queue = queue.Queue()
    orchestrator = Orchestrator(
        log_queue=log_queue,
        max_retries=args.max_retries,
        workspace_dir=args.workspace_dir,
    )
    session = orchestrator.run(args.task)

    if not args.quiet:
        while not log_queue.empty():
            entry = log_queue.get()
            print(f"[{entry.level}] {entry.agent}: {entry.message}")

    session_dir = Path(args.workspace_dir) / "sessions" / session.session_id
    print(f"Session: {session.session_id}")
    print(f"Status: {session.status}")
    print(f"Artifacts: {session_dir}")

    if session.final_code:
        print(f"Final script: {session_dir / 'final.py'}")
        return 0

    return 1


def ui_command(args: argparse.Namespace) -> int:
    command = [
        sys.executable,
        "-m",
        "streamlit",
        "run",
        "app.py",
        "--server.address",
        args.server_address,
        "--server.port",
        str(args.server_port),
    ]
    return subprocess.call(command)


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())

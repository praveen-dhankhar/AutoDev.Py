from __future__ import annotations

import argparse
import queue
import subprocess
import sys
from pathlib import Path
from typing import Sequence

from src import __version__
from src.config import LLM_MODEL, MAX_RETRIES, OLLAMA_BASE_URL, OLLAMA_MODEL, WORKSPACE_DIR
from src.health import check_ollama_health, model_supports_tools
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
    run_parser.add_argument(
        "--tools",
        action="store_true",
        help="Let the model call run_code/read_attempt/search_past_fixes itself.",
    )
    run_parser.set_defaults(func=run_command)

    serve_parser = subparsers.add_parser(
        "serve",
        help="Start the FastAPI job server.",
    )
    serve_parser.add_argument("--host", default="127.0.0.1", help="Bind address.")
    serve_parser.add_argument("--port", type=int, default=8000, help="Bind port.")
    serve_parser.set_defaults(func=serve_command)

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
    if args.tools and LLM_MODEL:
        print("Tool mode uses Ollama tool calling; unset LLM_MODEL.", file=sys.stderr)
        return 2

    if not args.skip_health_check and not LLM_MODEL:
        health = check_ollama_health(OLLAMA_BASE_URL)
        if not health.healthy:
            print(health.message, file=sys.stderr)
            return 2
        if args.tools and not model_supports_tools(OLLAMA_MODEL, OLLAMA_BASE_URL):
            print(
                f"Ollama model {OLLAMA_MODEL!r} does not report tool-calling support.",
                file=sys.stderr,
            )
            return 2

    log_queue: queue.Queue = queue.Queue()
    orchestrator = Orchestrator(
        log_queue=log_queue,
        max_retries=args.max_retries,
        workspace_dir=args.workspace_dir,
        mode="tools" if args.tools else "classic",
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


def serve_command(args: argparse.Namespace) -> int:
    import uvicorn

    uvicorn.run("src.api:app", host=args.host, port=args.port)
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())

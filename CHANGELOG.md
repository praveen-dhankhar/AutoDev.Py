# Changelog

## Unreleased

- Reworked README for reviewer-first portfolio presentation.
- Added architecture diagrams and an explicit security section for the Docker sandbox.
- Added a compact self-correction demo recording asset.
- Rewrote `PR-Agent-Docs.md` to match the current v0.1.0 implementation.

## v0.1.0 - 2026-07-03

- Added Python package metadata and the `pr-agent` console entry point.
- Added `pr-agent run "task"` for CLI execution and `pr-agent ui` for the Streamlit dashboard.
- Added Docker image builds for the app and sandbox runtime.
- Added CI gates for Ruff, unit tests, package build, Docker builds, sandbox adversarial tests, and nightly live Ollama smoke testing.
- Added Ollama health checks in the UI and CLI before live agent execution.
- Added UI cancellation with a `CANCELLED` state and sandbox cleanup on stopped runs.
- Added workspace session reload so prior runs reappear when the dashboard starts.
- Hardened the orchestrator state machine with transition logging, retry exhaustion tests, and repeated-traceback circuit breaking.
- Hardened Python execution behind a Docker sandbox with adversarial verification.

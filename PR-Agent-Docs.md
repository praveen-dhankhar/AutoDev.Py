# PR-Agent: Automated Software Engineer
## Complete Technical Documentation Suite

> **Version:** 1.0.0 | **Author:** Praveen | **Date:** June 2026  
> **Classification:** Portfolio / Open Source  
> **Stack:** Python · CrewAI · Ollama · Open-Source LLM · Streamlit · Subprocess

---

# Table of Contents

1. [Product Requirements Document (PRD)](#1-product-requirements-document)
2. [App Flow](#2-app-flow)
3. [UI/UX Brief](#3-uiux-brief)
4. [Backend Schema](#4-backend-schema)
5. [Technical Requirements Document (TRD)](#5-technical-requirements-document)
6. [Implementation Workflow](#6-implementation-workflow)

---

---

# 1. Product Requirements Document

## 1.1 Overview

**PR-Agent** is a multi-agent AI system that automates Python software development. Given a natural language feature request, it orchestrates three specialized LLM agents — an Architect, a Coder, and a QA Engineer — to plan, write, execute, and self-correct code until it passes, with zero human intervention in the loop.

This is a "Mini-Devin" proof of concept. It closes the feedback loop that tools like GitHub Copilot leave open: the developer seeing output, manually running it, reading errors, and prompting again.

## 1.2 Problem Statement

| Current Reality | What PR-Agent Does |
|---|---|
| Developer prompts LLM → gets code → manually runs it → sees error → prompts again | Agent writes code → agent runs it → agent reads the error → agent fixes it |
| Static, single-shot code generation | Dynamic, stateful agentic pipeline |
| No awareness of runtime failure | Self-correcting loop with bounded retry logic |
| Developer is the execution feedback channel | Subprocess tool is the execution feedback channel |

## 1.3 Goals

**Primary Goal (Career):** Demonstrate production-level understanding of Agentic AI workflows to FAANG and top-tier product company interviewers.

**Secondary Goal (Technical):** Build a reusable, extensible agent pipeline that can be adapted beyond code generation (e.g., data pipelines, test generation, documentation).

## 1.4 Target Users

| Persona | Description | Use Case |
|---|---|---|
| **Developer (Self)** | Portfolio owner, primary user | Automate repetitive Python scripting tasks |
| **Technical Recruiter** | Reviews GitHub & watches Loom demo | Evaluate depth of AI/agent systems knowledge |
| **Hiring Manager / Interviewer** | Dives into architecture and codebase | Assess state management, tool use, guardrails |

## 1.5 Core Feature Requirements

### F1 — Natural Language Task Input
- User enters a plain English task description (e.g., *"Write a script that fetches the top 10 HackerNews stories and saves them to a CSV"*)
- Input field supports multi-line
- Pre-loaded example prompts to reduce friction during demos

### F2 — Three-Agent Pipeline
- **Architect Agent:** Receives raw task. Outputs a structured, numbered implementation plan. Does not write code.
- **Coder Agent:** Receives implementation plan (and error context if retrying). Outputs a complete, runnable Python script.
- **QA Agent:** Receives the script path. Executes it via `PythonExecutorTool`. Emits structured execution result (pass/fail + stdout/stderr).

### F3 — Sandboxed Code Execution
- Generated scripts are executed via Python `subprocess` with a hard timeout
- Execution is isolated from the host environment
- Returns structured output: `{ status, stdout, stderr, exit_code, execution_time_ms }`

### F4 — Self-Correction Loop
- If QA fails, the exact error traceback is passed back to the Coder Agent
- Maximum 3 correction attempts (configurable)
- Loop terminates on first successful execution
- On exhausting retries, system enters `FAILED` terminal state and surfaces all attempts to user

### F5 — Real-Time Agent Log Streaming
- Every agent thought, action, and output streams into the UI in real time
- Log entries are color-coded by agent identity
- Users can watch the agents "think" — this is the most impressive demo element

### F6 — Code Viewer with Syntax Highlighting
- Final (or latest) generated code is displayed with Python syntax highlighting
- Previous attempt diffs are accessible

### F7 — Download Generated Script
- One-click download of the final passing Python script as a `.py` file

### F8 — Session History (In-Memory)
- Within the session, past runs are accessible from a sidebar
- Each run stores: task, plan, attempts, final code, status

## 1.6 Non-Functional Requirements

| Requirement | Target |
|---|---|
| End-to-end latency (simple task) | < 90 seconds |
| End-to-end latency (complex task) | < 180 seconds |
| Self-correction success rate | ≥ 70% of single-error failures |
| Max LLM API cost per run | $0 with local Ollama (hardware cost only) |
| Subprocess execution timeout | 30 seconds hard limit |
| Per-agent LLM call timeout | 60 seconds |
| Max retry attempts | 3 (via `MAX_RETRIES` env var) |
| Streaming log delay | < 2 seconds from LLM token to UI |

## 1.7 Out of Scope (v1.0)

- Multi-language code generation (only Python)
- GitHub PR creation and branch management
- Cloud/remote deployment of the generated code
- User authentication or multi-user support
- Persistent database (sessions live in memory + local filesystem)
- True Docker-based sandboxing (subprocess is sufficient for demo)
- Support for tasks requiring external API keys in the generated code

## 1.8 Success Metrics

| Metric | How to Measure |
|---|---|
| Self-correction demo works | Agent catches an error and fixes it end-to-end in the Loom video |
| Real-time streaming visible | Agent log updates during execution, not after |
| Clean GitHub repo | README with architecture diagram, setup instructions, demo GIF |
| Portfolio signal | Project results in at least one interview callback that cites it |

---

---

# 2. App Flow

## 2.1 High-Level System Flow

```
┌─────────────────────────────────────────────────────────────────────┐
│                         USER INTERFACE                               │
│                    (Streamlit Dashboard)                             │
└─────────────────────┬───────────────────────────────────────────────┘
                       │  task: str
                       ▼
┌─────────────────────────────────────────────────────────────────────┐
│                        ORCHESTRATOR                                  │
│                    orchestrator.py                                   │
│  Manages state machine, agent sequencing, retry logic               │
└─────┬────────────────────┬──────────────────────┬────────────────────┘
       │                    │                       │
       ▼                    ▼                       ▼
┌──────────────┐   ┌──────────────────┐   ┌────────────────────────┐
│  ARCHITECT   │   │     CODER        │   │      QA AGENT          │
│    AGENT     │──►│     AGENT        │──►│                        │
│              │   │                  │   │  ┌──────────────────┐  │
│  Takes task  │   │  Takes plan      │   │  │ PythonExecutor   │  │
│  Outputs     │   │  + error context │   │  │     Tool         │  │
│  impl. plan  │   │  Outputs .py     │   │  │ subprocess.run() │  │
└──────────────┘   └──────────────────┘   │  └──────────────────┘  │
                            ▲              │          │               │
                            │              │    pass / fail          │
                            │    error     └──────────┬──────────────┘
                            └─────────────────────────┘
                              (max 3 iterations)
```

## 2.2 State Machine

The orchestrator manages a strict state machine. No state can be skipped.

```
                    ┌─────────────┐
                    │    IDLE     │◄────────────────────────────┐
                    └──────┬──────┘                              │
                           │ user submits task                   │
                           ▼                                     │
                    ┌─────────────┐                              │
                    │  PLANNING   │  Architect Agent running     │
                    └──────┬──────┘                              │
                           │ plan emitted                        │
                           ▼                                     │
                    ┌─────────────┐                              │
                    │   CODING    │  Coder Agent running         │
                    └──────┬──────┘                              │
                           │ code emitted                        │
                           ▼                                     │
                    ┌─────────────┐                              │
                    │  EXECUTING  │  QA Agent + subprocess       │
                    └──────┬──────┘                              │
                     ┌─────┴──────┐                              │
                     │            │                              │
              pass ◄─┘            └─► fail                      │
                │                        │                       │
                ▼                        ▼                       │
         ┌───────────┐           ┌──────────────┐               │
         │ COMPLETED │           │  CORRECTING  │ attempt < 3   │
         └─────┬─────┘           └──────┬───────┘               │
               │                        │ retry → CODING        │
               │                        │                        │
               │                 attempt == 3                    │
               │                        │                        │
               │                 ┌──────▼───────┐               │
               │                 │    FAILED    │               │
               │                 └──────────────┘               │
               │                                                 │
               └──────────────── new task ───────────────────────┘
```

**States:**

| State | Description | Next States |
|---|---|---|
| `IDLE` | Awaiting user input | `PLANNING` |
| `PLANNING` | Architect Agent is generating the plan | `CODING` |
| `CODING` | Coder Agent is writing/fixing code | `EXECUTING` |
| `EXECUTING` | QA Agent is running the script | `COMPLETED`, `CORRECTING`, `FAILED` |
| `CORRECTING` | Error sent back to Coder (attempt < max) | `CODING` |
| `COMPLETED` | Code passed execution | `IDLE` (new task) |
| `FAILED` | Max retries exhausted | `IDLE` (new task) |

## 2.3 Agent Communication Protocol

Each agent communicates via a structured `AgentContext` object passed through the orchestrator. Agents do not directly reference each other.

```
STEP 1: Orchestrator → Architect
  Input:  { task: "Write a script that..." }
  Output: { plan: "1. Import requests...\n2. Fetch endpoint...\n..." }

STEP 2: Orchestrator → Coder (first attempt)
  Input:  { plan: "...", attempt: 1, previous_error: None }
  Output: { code: "import requests\n...", script_path: "/workspace/sessions/abc123/attempt_1.py" }

STEP 3: Orchestrator → QA
  Input:  { script_path: "/workspace/sessions/abc123/attempt_1.py" }
  Output: { status: "fail", stdout: "", stderr: "NameError: name 'x' is not defined", exit_code: 1 }

STEP 4: Orchestrator → Coder (retry)
  Input:  { plan: "...", attempt: 2, previous_error: "NameError: name 'x' is not defined\nTraceback..." }
  Output: { code: "import requests\nx = 5\n...", script_path: "/workspace/sessions/abc123/attempt_2.py" }

STEP 5: Orchestrator → QA
  Input:  { script_path: "/workspace/sessions/abc123/attempt_2.py" }
  Output: { status: "pass", stdout: "Data saved to output.csv", stderr: "", exit_code: 0 }
```

## 2.4 Self-Correction Loop Logic

```python
# Pseudocode — orchestrator.py

MAX_RETRIES = int(os.getenv("MAX_RETRIES", 3))

plan = architect_agent.run(task=user_task)
emit_log("architect", f"Plan ready:\n{plan}")

previous_error = None
for attempt in range(1, MAX_RETRIES + 1):
    emit_log("coder", f"Writing code (attempt {attempt}/{MAX_RETRIES})...")
    code, script_path = coder_agent.run(plan=plan, attempt=attempt, error=previous_error)
    save_to_filesystem(session_id, attempt, code)

    emit_log("qa", f"Executing attempt_{attempt}.py...")
    result = qa_agent.run(script_path=script_path)

    if result.status == "pass":
        emit_log("system", f"✓ Code passed on attempt {attempt}.")
        return CompletedSession(code=code, result=result)

    emit_log("qa", f"✗ Attempt {attempt} failed:\n{result.stderr}")
    previous_error = result.stderr

emit_log("system", f"✗ All {MAX_RETRIES} attempts exhausted. Task failed.")
return FailedSession(attempts=all_attempts)
```

## 2.5 Log Stream Flow

The UI subscribes to a log queue that the orchestrator writes to. This decouples agent execution from UI rendering.

```
Orchestrator.emit_log(agent, message)
    └──► LogQueue.put({ agent, message, timestamp })
              └──► Streamlit st.empty() polling loop
                        └──► Renders colored chat bubble in AgentLog component
```

---

---

# 3. UI/UX Brief

## 3.1 Design Philosophy

The UI should feel like watching a **live terminal with a co-pilot**. The primary experience is the agent activity log streaming in real time. Everything else is secondary. Recruiters watching a 2-minute demo should feel the system is alive and intelligent — not a static code block that appeared after 30 seconds of a spinner.

**Core Principles:**
- **Transparency over Magic:** Show every agent decision, not just the final output
- **Streaming First:** No content appears in a single dump; everything flows in
- **Minimal Chrome:** The log and the code are the product; no distracting UI noise
- **Demo-Optimized:** Layout is designed for screen recording at 1280×720

## 3.2 Page Layout

```
┌─────────────────────────────────────────────────────────────────────────┐
│  PR-Agent ⚙️          [Status Badge: ● Idle]          [Session: #3]     │
├────────────────────┬────────────────────────────────────────────────────┤
│                    │                                                      │
│   LEFT PANEL       │              MAIN PANEL                             │
│   (28%)            │              (72%)                                  │
│                    │  ┌─────────────────────────────────────────────┐   │
│  ┌──────────────┐  │  │  AGENT ACTIVITY LOG                         │   │
│  │  TASK INPUT  │  │  │  ─────────────────────────────────────────  │   │
│  │  ──────────  │  │  │  🔵 [Architect] Analyzing task...          │   │
│  │  [ Textarea ]│  │  │  🔵 [Architect] Plan ready (4 steps)       │   │
│  │              │  │  │  🟢 [Coder] Writing attempt 1/3...         │   │
│  │  [Examples ▾]│  │  │  🟢 [Coder] Script saved.                  │   │
│  │              │  │  │  🟠 [QA] Executing attempt_1.py...         │   │
│  │  [▶ Run]     │  │  │  🔴 [QA] FAILED: NameError on line 14     │   │
│  └──────────────┘  │  │  🟢 [Coder] Fixing (attempt 2/3)...       │   │
│                    │  │  🟠 [QA] Executing attempt_2.py...         │   │
│  ┌──────────────┐  │  │  🟢 [QA] PASSED ✓ (exit code 0)           │   │
│  │  SESSION     │  │  └─────────────────────────────────────────────┘   │
│  │  HISTORY     │  │                                                      │
│  │  ──────────  │  │  ┌─────────────────────────────────────────────┐   │
│  │  ● Run #3 ✓  │  │  │  GENERATED CODE               [⬇ Download] │   │
│  │  ○ Run #2 ✗  │  │  │  ─────────────────────────────────────────  │   │
│  │  ○ Run #1 ✓  │  │  │  import requests                            │   │
│  └──────────────┘  │  │  import csv                                  │   │
│                    │  │                                               │   │
│  ┌──────────────┐  │  │  def fetch_hn_stories(n=10):                │   │
│  │  CONFIG      │  │  │      ...                                     │   │
│  │  ──────────  │  │  │                                               │   │
│  │  Model: mini │  │  │  [Attempt 1 ✗] [Attempt 2 ✓]               │   │
│  │  Retries: 3  │  │  └─────────────────────────────────────────────┘   │
│  └──────────────┘  │                                                      │
│                    │  ┌─────────────────────────────────────────────┐   │
│                    │  │  EXECUTION OUTPUT                            │   │
│                    │  │  stdout: Data saved to hn_stories.csv (10   │   │
│                    │  │  rows)                                       │   │
│                    │  └─────────────────────────────────────────────┘   │
└────────────────────┴────────────────────────────────────────────────────┘
```

## 3.3 Component Specifications

### Component 1: Task Input Panel

```
┌─────────────────────────────────┐
│  What should I build?           │
│  ┌─────────────────────────┐    │
│  │                         │    │
│  │  [Multi-line textarea]  │    │
│  │  ~4 rows, resizable     │    │
│  │                         │    │
│  └─────────────────────────┘    │
│  Examples: [HN Scraper] [Sort]  │
│                                 │
│  [ ▶ Run Agent Pipeline ]       │
│  (disabled while running)       │
└─────────────────────────────────┘
```

- Disabled during active run (`st.text_area(disabled=st.session_state.running)`)
- Example prompt chips pre-fill the textarea on click
- Run button toggles to `● Running...` with spinner during execution

### Component 2: Agent Activity Log

```
┌─────────────────────────────────────────────────────────┐
│  🔵 Architect  2s ago                                    │
│  Breaking down task into 4 implementation steps...      │
│                                                          │
│  🟢 Coder  5s ago                                        │
│  Attempt 1/3: Writing initial Python script...          │
│                                                          │
│  🟠 QA Engineer  12s ago                                 │
│  Executing attempt_1.py (timeout: 30s)...               │
│                                                          │
│  🔴 QA Engineer  13s ago                                 │
│  FAILED — NameError: name 'soup' is not defined         │
│  Line 18, in fetch_stories                              │
│                                                          │
│  🟢 Coder  15s ago                                       │
│  Received error context. Fixing (attempt 2/3)...        │
└─────────────────────────────────────────────────────────┘
```

**Color-Coding:**

| Agent | Color | Streamlit Avatar |
|---|---|---|
| Architect | `#3B82F6` Blue | `🔵` |
| Coder | `#22C55E` Green | `🟢` |
| QA Engineer | `#F97316` Orange | `🟠` |
| System | `#6B7280` Gray | `⚙️` |
| Error | `#EF4444` Red | `🔴` |

- Implemented with `st.chat_message()` — each agent gets a distinct `name` and avatar
- Log autoscrolls to bottom on new entries
- Timestamps displayed as relative ("3s ago")

### Component 3: Status Badge

Displayed in the header. Updates on every state transition.

| State | Badge | Color |
|---|---|---|
| IDLE | `● Idle` | Gray |
| PLANNING | `◌ Planning...` | Blue |
| CODING | `◌ Coding...` | Green |
| EXECUTING | `◌ Executing...` | Orange |
| CORRECTING | `◌ Fixing (2/3)...` | Yellow |
| COMPLETED | `✓ Completed` | Green |
| FAILED | `✗ Failed` | Red |

### Component 4: Code Viewer

- Uses `st.code(language="python")` with the latest attempt's code
- Tab switcher for multiple attempts: `[Attempt 1 ✗]  [Attempt 2 ✓]`
- Failed attempt tabs are styled with a red border
- Passing attempt tabs are styled with a green border
- Download button triggers `st.download_button()` with the final code

### Component 5: Execution Output Panel

```
┌─────────────────────────────────────────────────────┐
│  EXECUTION OUTPUT                                    │
│  ─────────────────────────────────────────────────  │
│  exit code: 0  |  time: 2.3s  |  status: ● PASS    │
│                                                      │
│  STDOUT                                              │
│  ┌──────────────────────────────────────────────┐   │
│  │ Fetching HackerNews stories...               │   │
│  │ Saved 10 stories to hn_stories.csv           │   │
│  └──────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────┘
```

## 3.4 UX Flow for Demo (Optimized for Loom Recording)

```
1. Open browser at localhost:8501
2. Type task into input (or click example chip)  [5 seconds]
3. Click "Run Agent Pipeline"
4. Watch Architect log entry appear               [streaming, ~5s]
5. Watch Coder log entry appear                   [streaming, ~10s]
6. Watch QA "Executing..." appear                 [streaming, ~15s]
7. Watch QA "FAILED — NameError..." appear        [~16s]
8. Watch Coder "Fixing (attempt 2/3)..." appear   [streaming, ~20s]
9. Watch QA "PASSED ✓" appear                     [~30s]
10. Code viewer populates with highlighted code   [~30s]
11. Click Download button                          [demo complete]
```

## 3.5 Responsive Behavior

- `st.columns([1, 2.5])` for left/main panel split
- On narrow screens: panels stack vertically
- Log panel has `height=400` with overflow scroll
- Code viewer has `height=300` with overflow scroll

---

---

# 4. Backend Schema

> PR-Agent is a local single-user application. There is no persistent database. State is managed in Streamlit's `session_state` (in-memory) and the local filesystem (for files).

## 4.1 Core Data Models

```python
# models.py

from dataclasses import dataclass, field
from typing import Literal, List, Optional
from datetime import datetime
import uuid


ExecutionStatus = Literal["pass", "fail"]
SessionStatus = Literal["idle", "planning", "coding", "executing", "correcting", "completed", "failed"]
AgentName = Literal["architect", "coder", "qa", "system"]
LogLevel = Literal["info", "warning", "error", "success"]


@dataclass
class ExecutionResult:
    """Returned by PythonExecutorTool after running a script."""
    status: ExecutionStatus
    stdout: str
    stderr: str
    exit_code: int
    execution_time_ms: float
    script_path: str


@dataclass
class AttemptRecord:
    """One code generation + execution cycle."""
    attempt_number: int          # 1-indexed
    code: str                    # Raw Python source code
    script_path: str             # Absolute path on disk
    execution_result: Optional[ExecutionResult] = None
    timestamp: datetime = field(default_factory=datetime.utcnow)

    @property
    def passed(self) -> bool:
        return self.execution_result is not None and self.execution_result.status == "pass"


@dataclass
class AgentLogEntry:
    """A single streaming log event emitted by an agent or the system."""
    agent: AgentName
    message: str
    level: LogLevel = "info"
    timestamp: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> dict:
        return {
            "agent": self.agent,
            "message": self.message,
            "level": self.level,
            "timestamp": self.timestamp.isoformat()
        }


@dataclass
class AgentSession:
    """
    The complete state of a single pipeline run.
    One AgentSession is created per user task submission.
    """
    session_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    task: str = ""
    status: SessionStatus = "idle"
    implementation_plan: Optional[str] = None
    attempts: List[AttemptRecord] = field(default_factory=list)
    logs: List[AgentLogEntry] = field(default_factory=list)
    final_code: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None

    @property
    def attempt_count(self) -> int:
        return len(self.attempts)

    @property
    def latest_attempt(self) -> Optional[AttemptRecord]:
        return self.attempts[-1] if self.attempts else None

    @property
    def passing_attempt(self) -> Optional[AttemptRecord]:
        return next((a for a in reversed(self.attempts) if a.passed), None)
```

## 4.2 Agent Configuration Schema

```python
# config.py

from dataclasses import dataclass
from typing import List, Optional


@dataclass
class AgentConfig:
    name: str
    role: str
    goal: str
    backstory: str
    llm_model: str
    temperature: float
    max_tokens: int
    tools: List[str] = field(default_factory=list)


ARCHITECT_CONFIG = AgentConfig(
    name="Architect",
    role="Senior Software Architect",
    goal=(
        "Analyze the user's task and produce a clear, numbered, step-by-step "
        "implementation plan. Focus on logic and structure. Do not write code."
    ),
    backstory=(
        "You are a senior engineer who has designed hundreds of Python systems. "
        "You are methodical, precise, and always break problems into manageable steps."
    ),
    llm_model=os.getenv("OLLAMA_MODEL", "qwen2.5-coder:7b"),
    temperature=0.3,
    max_tokens=800,
)

CODER_CONFIG = AgentConfig(
    name="Coder",
    role="Expert Python Developer",
    goal=(
        "Write clean, complete, runnable Python code from the given implementation plan. "
        "If an error context is provided, fix only what is broken. "
        "Return ONLY the Python script, no markdown fences, no explanation."
    ),
    backstory=(
        "You are a meticulous Python engineer. You write production-quality code that "
        "handles edge cases and follows PEP 8. When given an error, you trace it precisely "
        "and fix only the affected section."
    ),
    llm_model=os.getenv("OLLAMA_MODEL", "qwen2.5-coder:7b"),
    temperature=0.15,
    max_tokens=2000,
)

QA_CONFIG = AgentConfig(
    name="QA Engineer",
    role="Quality Assurance Engineer",
    goal=(
        "Execute the provided Python script using the python_executor tool. "
        "Report the exact stdout, stderr, and exit code. "
        "Do not interpret — return raw output."
    ),
    backstory=(
        "You are a QA engineer who validates code correctness through execution. "
        "You are rigorous and report failures with full traceback context."
    ),
    llm_model=os.getenv("OLLAMA_MODEL", "qwen2.5-coder:7b"),
    temperature=0.0,
    max_tokens=500,
    tools=["python_executor"],
)
```

## 4.3 Tool Schema

```python
# tools/python_executor.py

from dataclasses import dataclass
from typing import Optional
import subprocess
import time
import os


@dataclass
class ExecutorInput:
    script_path: str
    timeout_seconds: int = 30
    working_directory: Optional[str] = None


@dataclass
class ExecutorOutput:
    status: str          # "pass" | "fail"
    stdout: str
    stderr: str
    exit_code: int
    execution_time_ms: float


class PythonExecutorTool:
    """
    Custom CrewAI tool that executes a Python script via subprocess.
    The tool is given to the QA Agent exclusively.
    """
    name: str = "python_executor"
    description: str = (
        "Executes a Python script at the given path. "
        "Returns stdout, stderr, exit_code, and execution status. "
        "Use this to validate that generated code runs correctly."
    )

    def run(self, input: ExecutorInput) -> ExecutorOutput:
        if not os.path.exists(input.script_path):
            return ExecutorOutput(
                status="fail",
                stdout="",
                stderr=f"FileNotFoundError: {input.script_path} does not exist",
                exit_code=1,
                execution_time_ms=0.0
            )

        start = time.monotonic()
        try:
            result = subprocess.run(
                ["python3", input.script_path],
                capture_output=True,
                text=True,
                timeout=input.timeout_seconds,
                cwd=input.working_directory or os.path.dirname(input.script_path),
                env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"}
            )
            elapsed = (time.monotonic() - start) * 1000
            status = "pass" if result.returncode == 0 else "fail"
            return ExecutorOutput(
                status=status,
                stdout=result.stdout[:4000],    # Truncate to avoid context overflow
                stderr=result.stderr[:4000],
                exit_code=result.returncode,
                execution_time_ms=round(elapsed, 2)
            )
        except subprocess.TimeoutExpired:
            elapsed = (time.monotonic() - start) * 1000
            return ExecutorOutput(
                status="fail",
                stdout="",
                stderr=f"TimeoutError: Script exceeded {input.timeout_seconds}s limit",
                exit_code=-1,
                execution_time_ms=round(elapsed, 2)
            )
```

## 4.4 Streamlit Session State Schema

```python
# The st.session_state keys used across the app

{
    "running": bool,                      # True while pipeline is active
    "current_session": AgentSession,      # The active pipeline run
    "session_history": List[AgentSession],# Past completed runs
    "log_queue": queue.Queue,             # Thread-safe log event queue
    "config": {
        "model": str,                     # "qwen2.5-coder:7b" | "llama3.1:8b"
        "max_retries": int,               # 1-5
        "timeout_seconds": int,           # 10-120
    }
}
```

## 4.5 Filesystem Layout

```
pr-agent/
│
├── workspace/                          # Auto-created at runtime
│   └── sessions/
│       └── {session_id}/               # e.g., "a3f1b2c4/"
│           ├── task.txt                # User's raw task input
│           ├── plan.md                 # Architect's implementation plan
│           ├── attempt_1.py            # First code generation
│           ├── attempt_2.py            # Second attempt (if error on 1)
│           ├── attempt_3.py            # Third attempt (if error on 2)
│           ├── final.py               # Symlink or copy of last passing attempt
│           └── execution_log.jsonl    # Newline-delimited JSON log entries
│
├── src/
│   ├── agents/
│   │   ├── architect.py
│   │   ├── coder.py
│   │   └── qa.py
│   ├── tools/
│   │   └── python_executor.py
│   ├── models.py
│   ├── config.py
│   ├── orchestrator.py
│   └── utils.py
│
├── app.py                              # Streamlit entrypoint
├── .env                                # OLLAMA_MODEL, MAX_RETRIES, etc.
├── requirements.txt
└── README.md
```

## 4.6 Environment Variables

```bash
# .env

OLLAMA_MODEL=qwen2.5-coder:7b  # Local Ollama model to use
OLLAMA_BASE_URL=http://localhost:11434
MAX_RETRIES=3                  # Default: 3. Range: 1-5
SUBPROCESS_TIMEOUT=30          # Default: 30s per execution
AGENT_CALL_TIMEOUT=60          # Default: 60s per LLM call
WORKSPACE_DIR=./workspace      # Where session files are saved
LOG_LEVEL=INFO                 # DEBUG | INFO | WARNING
```

---

---

# 5. Technical Requirements Document

## 5.1 System Architecture

**Pattern:** Multi-Agent Pipeline with Conditional Retry Loop

**Deployment Model:** Local machine, single-user, no auth

**Architecture Style:** Sequential agent pipeline with tool-augmented execution and feedback routing

```
┌──────────────────────────────────────────────────────────────┐
│                    APPLICATION LAYERS                         │
│                                                              │
│  ┌─────────────────────────────────────────────────────┐    │
│  │               UI LAYER (Streamlit)                   │    │
│  │   app.py  ·  Session state  ·  Log rendering         │    │
│  └───────────────────────┬─────────────────────────────┘    │
│                           │                                  │
│  ┌───────────────────────▼─────────────────────────────┐    │
│  │            ORCHESTRATION LAYER                       │    │
│  │   orchestrator.py  ·  State machine  ·  Retry loop  │    │
│  └───────┬───────────────┬──────────────────┬──────────┘    │
│           │               │                  │               │
│  ┌────────▼───┐  ┌────────▼───┐  ┌──────────▼────────┐     │
│  │  ARCHITECT │  │   CODER    │  │    QA AGENT        │     │
│  │   AGENT    │  │   AGENT    │  │                    │     │
│  └────────┬───┘  └────────┬───┘  └────────┬──────────┘     │
│           │               │               │                  │
│  ┌────────▼───────────────▼───────────────▼──────────┐      │
│  │               LLM PROVIDER LAYER                   │      │
│  │         Local Ollama model (qwen2.5-coder:7b)      │      │
│  └────────────────────────────────────────────────────┘      │
│                                                              │
│  ┌─────────────────────────────────────────────────────┐    │
│  │               TOOL LAYER                             │    │
│  │         PythonExecutorTool · subprocess.run()        │    │
│  └─────────────────────────────────────────────────────┘    │
│                                                              │
│  ┌─────────────────────────────────────────────────────┐    │
│  │           FILESYSTEM LAYER                           │    │
│  │    /workspace/sessions/{id}/*.py  ·  *.jsonl         │    │
│  └─────────────────────────────────────────────────────┘    │
└──────────────────────────────────────────────────────────────┘
```

## 5.2 Technology Stack

| Layer | Technology | Version | Rationale |
|---|---|---|---|
| Agent Framework | **CrewAI** | ≥0.80.0 | Built-in sequential process, explicit role/goal/backstory model, fast to prototype |
| LLM Provider | **Ollama** | qwen2.5-coder:7b | Free local open-source code model; no API key required |
| Frontend | **Streamlit** | ≥1.36.0 | Zero boilerplate UI; `st.chat_message` + `st.status` native streaming |
| Env Management | **python-dotenv** | ≥1.0.0 | Standard config from `.env` |
| Execution Tool | **subprocess** (stdlib) | Python 3.11+ | No extra dependencies; `capture_output=True` for clean I/O capture |
| State Management | **st.session_state** | Streamlit native | Persistent across reruns; sufficient for single-user |
| Logging | **logging** + `jsonl` | stdlib | Structured logs, easily parsed for post-run analysis |

## 5.3 Agent Framework Decision: CrewAI vs LangGraph

| Criterion | CrewAI | LangGraph |
|---|---|---|
| Learning curve | Low — 2 hours to first working agent | Medium — requires understanding DAG concepts |
| Control over flow | Medium — opinionated sequential process | High — explicit graph nodes and edges |
| Custom tool integration | Simple `@tool` decorator | Standard LangChain tool pattern |
| Streaming support | Via callbacks | Native with `astream_events` |
| Best for this project | **Yes — v1 in 7 days** | Yes — better for v2 refactor |

**Decision:** CrewAI for v1. Refactor to LangGraph for v2 if adding parallel agents or complex branching.

## 5.4 Local LLM Integration

```python
# Per-agent LLM call breakdown (worst-case single run, 3 attempts)

ARCHITECT:
  - Input:  ~500 tokens (system prompt + user task)
  - Output: ~600 tokens (implementation plan)
  - Total:  ~1,100 tokens × 1 call = 1,100 tokens

CODER:
  - Input:  ~700 tokens (system prompt + plan + error context)
  - Output: ~1,500 tokens (Python code)
  - Total:  ~2,200 tokens × 3 calls = 6,600 tokens

QA:
  - Input:  ~300 tokens (system prompt + script path)
  - Output: ~200 tokens (execution result interpretation)
  - Total:  ~500 tokens × 3 calls = 1,500 tokens

TOTAL WORST CASE: ~9,200 tokens, served locally through Ollama with no API usage cost.
```

**Local Availability & Retry:**
```python
# Exponential backoff on temporary Ollama/server errors
RETRY_DELAYS = [1, 2, 4]   # seconds (3 retries max)
MAX_LLM_RETRIES = 3
```

## 5.5 Security Requirements

| Risk | Mitigation |
|---|---|
| Generated code calls `os.system()` or `shutil.rmtree("/")` | Coder Agent system prompt includes guardrail: "Never use os.system(), shutil.rmtree(), or sys.exit()" |
| Generated code runs indefinitely | `subprocess.run(timeout=30)` — hard kill after 30 seconds |
| Generated code reads `.env` or API keys | Subprocess runs with restricted environment: `env={"PATH": ..., "HOME": ...}` — no host secrets in subprocess env |
| Generated code makes unexpected network calls | Out of scope for v1; v2 consideration: network namespace isolation |
| Prompt injection via task input | Input is user-controlled on localhost; not a concern for single-user local app |
| Arbitrary file writes | Generated scripts save to `/workspace/sessions/{id}/` only; Coder Agent instructed not to write outside this directory |

## 5.6 Error Handling Matrix

| Error | Where Caught | Behavior |
|---|---|---|
| LLM API timeout (>60s) | `orchestrator.py` | Set status=FAILED, surface error to UI |
| LLM API 429 Rate Limit | `agents/*.py` retry wrapper | Exponential backoff, max 3 retries |
| LLM returns non-code (markdown fence, explanation) | `coder.py` post-processor | Strip markdown fences, extract code block |
| Subprocess timeout (>30s) | `python_executor.py` | Return `TimeoutError` in stderr, status=fail |
| Script file not saved before execution | `orchestrator.py` | Raise `FileNotFoundError`, set status=FAILED |
| Max retries exhausted | `orchestrator.py` | Set status=FAILED, preserve all attempts in session |
| Streamlit thread error | `app.py` try/catch | Reset `running=False`, show error in UI |

## 5.7 Threading Model

Streamlit reruns the entire script on every interaction. The pipeline must run in a background thread to avoid blocking UI updates.

```python
# app.py — threading pattern

import threading
import queue

def run_pipeline(task: str, log_queue: queue.Queue):
    """Runs in a background thread. Writes logs to queue."""
    orchestrator = Orchestrator(log_queue=log_queue)
    session = orchestrator.run(task=task)
    st.session_state.current_session = session
    st.session_state.running = False

if st.button("Run Agent Pipeline") and not st.session_state.running:
    st.session_state.running = True
    st.session_state.log_queue = queue.Queue()
    thread = threading.Thread(
        target=run_pipeline,
        args=(user_task, st.session_state.log_queue),
        daemon=True
    )
    thread.start()
```

## 5.8 Performance Budget

| Operation | Target | Hard Limit |
|---|---|---|
| Architect agent call | < 10s | 60s |
| Coder agent call (per attempt) | < 20s | 60s |
| Script execution | < 10s | 30s |
| Total pipeline (1 attempt, pass) | < 45s | 120s |
| Total pipeline (3 attempts) | < 120s | 180s |
| UI log update latency | < 2s | 5s |

## 5.9 Dependencies

```txt
# requirements.txt

crewai>=0.80.0
langchain-ollama>=0.2.0
streamlit>=1.36.0
python-dotenv>=1.0.0
pygments>=2.18.0
```

## 5.10 Interview Talking Points (Technical Depth Signals)

When discussing this project in FAANG interviews, emphasize:

**On State Management:**
> "I designed a strict state machine with 7 states and explicit transition rules. No agent can proceed without the orchestrator validating the prior state. This prevents partial pipeline execution and makes the system debuggable."

**On Tool Use:**
> "The QA Agent doesn't just call the LLM — it has a custom tool that executes real code in a subprocess. This is the difference between an agent that thinks about code and one that actually runs it. I designed the tool schema as a typed interface with explicit input/output contracts."

**On Guardrails:**
> "I built three layers of protection: a hard subprocess timeout, a maximum retry cap of 3 to bound API cost and prevent infinite loops, and a per-agent LLM call timeout. The system fails gracefully and preserves all intermediate state for debugging."

**On Observability:**
> "Every agent I/O is logged to a `jsonl` file with timestamps. The UI subscribes to a thread-safe queue, so logs stream in real time without blocking execution. You can reconstruct the exact sequence of decisions from the logs alone."

---

---

# 6. Implementation Workflow

## 6.1 Repository Structure (Set Up on Day 0)

```
pr-agent/
├── src/
│   ├── agents/
│   │   ├── __init__.py
│   │   ├── architect.py
│   │   ├── coder.py
│   │   └── qa.py
│   ├── tools/
│   │   ├── __init__.py
│   │   └── python_executor.py
│   ├── models.py
│   ├── config.py
│   ├── orchestrator.py
│   └── utils.py
├── app.py
├── tests/
│   ├── test_executor.py
│   ├── test_orchestrator.py
│   └── test_agents.py
├── workspace/                  # gitignored, auto-created
├── .env.example
├── .gitignore
├── requirements.txt
└── README.md
```

## 6.2 Day-by-Day Plan

---

### Day 0 · Setup & Proof of Concept (2–3 hours)

**Objective:** Working Python environment. One LLM call confirmed.

**Tasks:**
```bash
# 1. Create virtual environment
python3 -m venv venv && source venv/bin/activate

# 2. Install dependencies
pip install crewai langchain-ollama streamlit python-dotenv

# 3. Pull local open-source model and create .env
ollama pull qwen2.5-coder:7b
cp .env.example .env

# 4. Verify local LLM connectivity
python3 -c "
from langchain_ollama import ChatOllama
llm = ChatOllama(model='qwen2.5-coder:7b', base_url='http://localhost:11434')
print(llm.invoke('Say hello in 5 words').content)
"
```

**Milestone:** `"Hello! How can I help you?"` prints to terminal.

---

### Day 1 · Core Data Models & Config (3–4 hours)

**Objective:** All data structures defined. No agent logic yet.

**Files to create:**
- `src/models.py` — `AgentSession`, `AttemptRecord`, `ExecutionResult`, `AgentLogEntry`
- `src/config.py` — `ARCHITECT_CONFIG`, `CODER_CONFIG`, `QA_CONFIG`
- `.env.example` — template with all required env vars

**Validation test:**
```python
# Quick sanity check
from src.models import AgentSession, AttemptRecord
session = AgentSession(task="test")
assert session.session_id is not None
assert session.attempt_count == 0
print("Models OK")
```

**Milestone:** All models instantiate without errors.

---

### Day 2 · Build the Architect & Coder Agents (4–5 hours)

**Objective:** Two agents callable with typed inputs/outputs.

**Files to create:**
- `src/agents/architect.py`
- `src/agents/coder.py`

```python
# src/agents/architect.py
from crewai import Agent, Task, Crew
from src.llm import build_llm
from src.config import ARCHITECT_CONFIG

def run_architect(task: str) -> str:
    """Returns implementation plan as a string."""
    llm = build_llm(ARCHITECT_CONFIG)
    agent = Agent(
        role=ARCHITECT_CONFIG.role,
        goal=ARCHITECT_CONFIG.goal,
        backstory=ARCHITECT_CONFIG.backstory,
        llm=llm,
        verbose=True
    )
    task_obj = Task(
        description=f"Analyze and plan the implementation for: {task}",
        expected_output="A numbered, step-by-step implementation plan. No code.",
        agent=agent
    )
    crew = Crew(agents=[agent], tasks=[task_obj])
    result = crew.kickoff()
    return str(result)
```

**Testing:**
```python
# tests/test_agents.py
from src.agents.architect import run_architect

plan = run_architect("Write a script to fetch BTC price and print it")
assert len(plan) > 100
assert "1." in plan   # Should have numbered steps
print("Architect: PASS")
```

**Milestone:** Architect returns a plan with ≥ 3 numbered steps. Coder returns valid Python code (visually inspect).

---

### Day 3 · Build the Execution Tool & QA Agent (4–5 hours)

**Objective:** PythonExecutorTool works. QA Agent uses it correctly.

**Files to create:**
- `src/tools/python_executor.py`
- `src/agents/qa.py`

**Testing the tool directly first:**
```python
# tests/test_executor.py
from src.tools.python_executor import PythonExecutorTool, ExecutorInput

tool = PythonExecutorTool()

# Test 1: Passing script
import tempfile, os
with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
    f.write('print("hello world")')
    path = f.name

result = tool.run(ExecutorInput(script_path=path))
assert result.status == "pass"
assert "hello world" in result.stdout
assert result.exit_code == 0
print("Test 1 PASS")

# Test 2: Failing script
with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
    f.write('x = undefined_variable')
    path = f.name

result = tool.run(ExecutorInput(script_path=path))
assert result.status == "fail"
assert "NameError" in result.stderr
print("Test 2 PASS")

# Test 3: Timeout
with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
    f.write('import time; time.sleep(999)')
    path = f.name

result = tool.run(ExecutorInput(script_path=path, timeout_seconds=2))
assert result.status == "fail"
assert "TimeoutError" in result.stderr
print("Test 3 PASS")
```

**Milestone:** All 3 tool tests pass. QA Agent returns structured execution result.

---

### Day 4 · Build the Orchestrator & Self-Correction Loop (5–6 hours)

**Objective:** Full pipeline end-to-end. Self-correction works.

**File to create:** `src/orchestrator.py`

```python
# src/orchestrator.py (core structure)

class Orchestrator:
    def __init__(self, log_queue: queue.Queue, max_retries: int = 3):
        self.log_queue = log_queue
        self.max_retries = max_retries

    def emit(self, agent: str, message: str, level: str = "info"):
        entry = AgentLogEntry(agent=agent, message=message, level=level)
        self.log_queue.put(entry)

    def run(self, task: str) -> AgentSession:
        session = AgentSession(task=task)
        session.status = "planning"
        self._save_session_dir(session)

        # Step 1: Architect
        self.emit("architect", "Analyzing task and creating implementation plan...")
        plan = run_architect(task)
        session.implementation_plan = plan
        session.status = "coding"
        self.emit("architect", f"Plan ready:\n{plan}", level="success")

        # Step 2: Coder + QA loop
        previous_error = None
        for attempt_num in range(1, self.max_retries + 1):
            self.emit("coder", f"Writing code (attempt {attempt_num}/{self.max_retries})...")
            session.status = "coding"
            code = run_coder(plan=plan, attempt=attempt_num, error=previous_error)
            script_path = self._save_attempt(session, attempt_num, code)

            self.emit("qa", f"Executing attempt_{attempt_num}.py (timeout: 30s)...")
            session.status = "executing"
            result = run_qa(script_path=script_path)

            attempt = AttemptRecord(
                attempt_number=attempt_num,
                code=code,
                script_path=script_path,
                execution_result=result
            )
            session.attempts.append(attempt)

            if result.status == "pass":
                session.status = "completed"
                session.final_code = code
                session.completed_at = datetime.utcnow()
                self.emit("system", f"✓ Passed on attempt {attempt_num}!", level="success")
                return session

            self.emit("qa", f"✗ Attempt {attempt_num} failed:\n{result.stderr}", level="error")
            previous_error = result.stderr
            if attempt_num < self.max_retries:
                session.status = "correcting"
                self.emit("coder", f"Received error. Fixing for attempt {attempt_num + 1}...")

        session.status = "failed"
        self.emit("system", f"✗ All {self.max_retries} attempts failed.", level="error")
        return session
```

**Milestone:** Running `python3 -c "from src.orchestrator import Orchestrator; ..."` with a simple task (e.g., "print the fibonacci sequence up to 10") should complete end-to-end, potentially with at least one self-correction if you intentionally introduce a complexity.

---

### Day 5 · Build the Streamlit UI (4–5 hours)

**Objective:** Full UI with streaming logs, code viewer, and download.

**File to create:** `app.py`

**Key Streamlit patterns to implement:**

```python
# app.py — key patterns

# 1. Real-time log streaming
log_placeholder = st.empty()
with log_placeholder.container():
    while st.session_state.running or not log_queue.empty():
        try:
            entry = log_queue.get_nowait()
            with st.chat_message(name=entry.agent, avatar=AGENT_AVATARS[entry.agent]):
                st.markdown(entry.message)
        except queue.Empty:
            time.sleep(0.1)
        st.experimental_rerun()   # Or use st.rerun() in newer Streamlit

# 2. Code viewer with attempt tabs
if session.attempts:
    tabs = st.tabs([f"Attempt {a.attempt_number} {'✓' if a.passed else '✗'}" 
                    for a in session.attempts])
    for tab, attempt in zip(tabs, session.attempts):
        with tab:
            st.code(attempt.code, language="python")

# 3. Download button
if session.final_code:
    st.download_button(
        label="⬇ Download final.py",
        data=session.final_code,
        file_name="final.py",
        mime="text/x-python"
    )
```

**Milestone:** Run `streamlit run app.py`. Full UI visible at `localhost:8501`. Submit a task and watch logs stream in real time.

---

### Day 6 · Testing, Edge Cases & Hardening (3–4 hours)

**Objective:** Robust pipeline. Documented failure examples for README.

**Test Matrix:**

| Task | Expected Behavior |
|---|---|
| "Print hello world" | Pass on attempt 1 |
| "Sort a list of 5 numbers" | Pass on attempt 1 |
| "Fetch BTC price from CoinGecko API" | May fail on attempt 1 (missing import), self-correct |
| "Use a variable before defining it" | QA catches NameError, Coder fixes it |
| "Write an infinite loop" | Subprocess timeout fires after 30s, status=FAILED |
| "Parse a JSON string that has a typo" | JSONDecodeError caught, Coder fixes |
| "Write a 200-line complex script" | Tests patience + max retry behavior |

**Document at least one self-correction example:**
```
BEFORE (attempt 1):
  response = requests.get(url)
  data = json.loads(response)     # ← Bug: response is not a string
  
ERROR:
  TypeError: the JSON object must be str, bytes or bytearray, not Response

AFTER (attempt 2):
  response = requests.get(url)
  data = response.json()          # ← Fixed: using .json() method
```

This before/after example goes directly into the README.

**Hardening checklist:**
- [ ] `MAX_RETRIES` is read from env, not hardcoded
- [ ] All timeouts are configurable
- [ ] Log file written to `/workspace/sessions/{id}/execution_log.jsonl`
- [ ] Run button disabled while pipeline is active
- [ ] Session history displays past runs in sidebar
- [ ] UI shows FAILED state gracefully (does not crash)

---

### Day 7 · Polish, README & Loom Demo (4–5 hours)

**Objective:** GitHub-ready. Recruiter-ready. Demo recorded.

#### README.md Must-Haves

```markdown
# PR-Agent 🤖 — Automated Software Engineer

> A multi-agent AI system that writes, runs, and self-corrects Python code.

## Architecture

[ASCII or image architecture diagram — show 3 agents + tool + loop]

## Demo

[Embed Loom link here]
[Embed a GIF of the self-correction loop in action]

## Tech Stack
- CrewAI · Ollama · Qwen2.5-Coder · Streamlit · Python subprocess

## Quick Start
git clone ...
pip install -r requirements.txt
ollama pull qwen2.5-coder:7b
cp .env.example .env
streamlit run app.py

## Self-Correction Example
[Paste your Day 6 before/after example here]

## What I Learned
[3-4 bullet points on state management, tool use, guardrails, observability]
```

#### Loom Demo Script (2 minutes)

```
0:00–0:15  |  "Hi, I'm Praveen. This is PR-Agent — a system where 
             |   three AI agents collaborate to write and fix Python code."
             
0:15–0:30  |  [Type task: "Fetch top 5 HackerNews stories and save to CSV"]
             |  Click Run.
             
0:30–1:10  |  [Watch log stream in real time]
             |  Narrate: "The Architect is planning. Now the Coder is writing."
             |  "Here you can see the QA agent catching a NameError..."
             |  "And now the Coder is fixing it on attempt 2..."
             |  "Passed! The agent self-corrected without any human input."
             
1:10–1:40  |  [Switch to Code Viewer]
             |  "Here's the final generated code. I can click Attempt 1 to 
             |   see the broken version and compare with the fixed Attempt 2."
             
1:40–2:00  |  "This demonstrates tool use, state management across LLM calls,
             |   and guardrails to prevent infinite loops. Thanks for watching."
```

## 6.3 Git Commit Strategy

```bash
# Suggested commit history (one per day)

Day 0:  "init: project structure, venv, LLM connectivity verified"
Day 1:  "feat: core data models — AgentSession, AttemptRecord, ExecutionResult"
Day 2:  "feat: architect and coder agents with typed I/O"
Day 3:  "feat: PythonExecutorTool with pass/fail/timeout handling"
Day 4:  "feat: orchestrator with self-correction loop (max 3 retries)"
Day 5:  "feat: streamlit UI with real-time log streaming and code viewer"
Day 6:  "fix: edge case handling, hardening, execution log persistence"
Day 7:  "docs: README, architecture diagram, demo GIF, Loom link"
```

## 6.4 v2 Roadmap (Post-Hiring Enhancements)

| Feature | Complexity | Value |
|---|---|---|
| Migrate orchestrator to LangGraph | Medium | Tighter control, better streaming |
| Docker sandbox for code execution | Medium | Real security isolation |
| GitHub PR creation via PyGitHub | Medium | "Actually creates a PR" demo |
| Support multiple languages (JS, Go) | High | Broadens use case |
| Parallel agents (Architect + Coder simultaneously) | High | Performance demo |
| Vector memory across sessions | High | Agent remembers past mistakes |

---

*Document last updated: June 2026*  
*Total estimated implementation time: 35–42 hours over 7 days*

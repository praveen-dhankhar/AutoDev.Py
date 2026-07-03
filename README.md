# PR-Agent ⚙️ — Automated Software Engineer

> A multi-agent AI system that writes, runs, and self-corrects Python code autonomously.

## Architecture

```
User
  |
  v
Streamlit Dashboard
  |
  v
Orchestrator
  |
  +--> Architect Agent
  |      |
  |      v
  |   Numbered implementation plan
  |
  +--> Coder Agent
  |      |
  |      v
  |   Complete Python script
  |
  +--> QA Agent
         |
         v
   PythonExecutorTool
         |
         v
   SandboxedPythonExecutor
         |
         v
   docker run autodev-py-sandbox
         |
         +--> pass --> COMPLETED --> final.py available for download
         |
         +--> fail --> traceback sent back to Coder Agent
                       |
                       v
                  RETRYING until success, retry budget is exhausted,
                  or a circuit breaker stops repeated failures
```

PR-Agent uses a strict, explicit state machine rather than an open-ended autonomous agent. The pipeline moves through `PLANNING -> CODING -> EXECUTING -> RETRYING -> SUCCEEDED/FAILED`, and each transition is written to `execution_log.jsonl` with a timestamp and reason. If execution fails, the exact traceback becomes the next Coder prompt; if the same traceback appears twice in a row, a circuit breaker stops the loop instead of burning the remaining retry budget.

## Tech Stack

- CrewAI · Ollama · Qwen2.5-Coder · Streamlit · Docker sandbox

## Quick Start

```bash
git clone https://github.com/praveen-dhankhar/AutoDev.Py.git
cd AutoDev.Py
python3.11 -m venv .venv
source .venv/bin/activate
pip install -e .
docker build -f sandbox.Dockerfile -t autodev-py-sandbox:latest .
docker build -t autodev-py-app:latest .
ollama pull qwen2.5-coder:7b
cp .env.example .env
pr-agent ui
```

The app opens at [http://localhost:8501](http://localhost:8501). Docker must be running so generated scripts execute inside the sandbox, and Ollama must be running locally at `http://localhost:11434`.

To run the pipeline from a shell instead of the dashboard:

```bash
pr-agent run "Write a Python script that prints the Fibonacci sequence up to 10"
```

`pr-agent run` performs an Ollama health check before starting the agent loop and exits early if the local model server is unavailable.

## Self-Correction Example

BEFORE (attempt 1 — broken):

```python
response = requests.get(url)
data = json.loads(response)     # Bug: response is not a string
```

ERROR:

```text
TypeError: the JSON object must be str, bytes or bytearray, not Response
```

AFTER (attempt 2 — fixed by Coder Agent):

```python
response = requests.get(url)
data = response.json()          # Fixed: using .json() method
```

## Environment Variables

| Variable             | Default         | Description                   |
|----------------------|-----------------|-------------------------------|
| OLLAMA_MODEL         | qwen2.5-coder:7b | Local Ollama model to use     |
| OLLAMA_BASE_URL      | http://localhost:11434 | Ollama server URL      |
| MAX_RETRIES          | 3               | Max self-correction attempts  |
| SUBPROCESS_TIMEOUT   | 30              | Script execution timeout (s)  |
| AGENT_CALL_TIMEOUT   | 60              | Local LLM call timeout (s)    |
| WORKSPACE_DIR        | ./workspace     | Where session files are saved |
| SANDBOX_IMAGE        | autodev-py-sandbox:latest | Docker image used to run generated code |
| SANDBOX_ALLOW_NETWORK | 0              | Allow sandbox network locally only; CI always disables it |

## Development

```bash
python3.11 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
ruff check .
pytest
```

To verify live local LLM connectivity after creating `.env` and pulling the model:

```bash
python3 -c "
from dotenv import load_dotenv; load_dotenv()
import os
from langchain_ollama import ChatOllama
llm = ChatOllama(
    model=os.getenv('OLLAMA_MODEL', 'qwen2.5-coder:7b'),
    base_url=os.getenv('OLLAMA_BASE_URL', 'http://localhost:11434'),
)
print(llm.invoke('Say hello in 5 words').content)
"
```

## Runtime Files

Each run writes local artifacts under `workspace/sessions/{session_id}/`:

- `task.txt` contains the user request
- `plan.md` contains the Architect plan
- `attempt_1.py`, `attempt_2.py`, and later attempts contain generated code
- `final.py` is written only after a successful execution
- `execution_log.jsonl` records timestamped agent and system messages

The dashboard reloads past sessions from `workspace/sessions/` on startup. The `workspace/` directory is intentionally ignored by Git because it contains generated run output.

## What I Learned

- Strict state machines make multi-step agent pipelines debuggable and predictable
- Tool use (subprocess execution) is what separates an agent that thinks from one that acts
- Thread-safe queues decouple agent execution from UI rendering, enabling true streaming
- Bounded retry loops with explicit max caps prevent infinite LLM feedback cycles

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
   subprocess.run(["python3", script_path])
         |
         +--> pass --> COMPLETED --> final.py available for download
         |
         +--> fail --> traceback sent back to Coder Agent
                       |
                       v
                  retry until MAX_RETRIES is exhausted
```

PR-Agent uses a strict orchestration loop rather than an open-ended autonomous agent. The Architect creates a plan, the Coder writes a runnable script, and the QA layer executes the generated file in a subprocess. If execution fails, the exact traceback becomes the next Coder prompt, giving the system a bounded self-correction loop.

## Tech Stack

- CrewAI · Ollama · Qwen2.5-Coder · Streamlit · Python subprocess

## Quick Start

```bash
git clone <your-repo-url>
cd pr-agent
/usr/local/bin/python3.11 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
ollama pull qwen2.5-coder:7b
cp .env.example .env
streamlit run app.py
```

The app opens at [http://localhost:8501](http://localhost:8501). Ollama must be running locally at `http://localhost:11434`.

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

## Development

```bash
/usr/local/bin/python3.11 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
pip install pytest
pytest tests/test_executor.py tests/test_orchestrator.py -v
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

The `workspace/` directory is intentionally ignored by Git because it contains generated run output.

## What I Learned

- Strict state machines make multi-step agent pipelines debuggable and predictable
- Tool use (subprocess execution) is what separates an agent that thinks from one that acts
- Thread-safe queues decouple agent execution from UI rendering, enabling true streaming
- Bounded retry loops with explicit max caps prevent infinite LLM feedback cycles

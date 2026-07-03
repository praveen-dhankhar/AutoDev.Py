# AutoDev.Py

AutoDev.Py is a Python project centered on `pr-agent`, a local multi-agent coding assistant. The app uses Streamlit for the UI, CrewAI for the agent loop, Ollama for local LLM execution, and a subprocess-based QA step to run generated Python scripts.

## Repository Layout

```text
.
|-- PR-Agent-Docs.md        # Detailed project write-up
|-- pr-agent/
|   |-- app.py              # Streamlit application
|   |-- requirements.txt    # Runtime dependencies
|   |-- src/                # Agent, orchestration, model, and tool code
|   `-- tests/              # Unit tests
|-- requirements-dev.txt    # Local/CI test dependencies
`-- pytest.ini              # Root pytest configuration
```

## Quick Start

```bash
git clone https://github.com/praveen-dhankhar/AutoDev.Py.git
cd AutoDev.Py/pr-agent

python3.11 -m venv .venv
source .venv/bin/activate

pip install -r requirements.txt
ollama pull qwen2.5-coder:7b
cp .env.example .env

streamlit run app.py
```

The app opens at <http://localhost:8501>. Ollama must be running locally at `http://localhost:11434`.

## Running Tests

From the repository root:

```bash
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
pytest
```

The default unit tests do not require Ollama or the runtime agent dependencies. Live local LLM tests are opt-in:

```bash
cd pr-agent
OLLAMA_LIVE_TESTS=1 pytest tests/test_agents.py
```

## Runtime Output

Generated scripts, plans, and logs are written under `pr-agent/workspace/` during app runs. That directory is ignored by Git because it contains local run artifacts.

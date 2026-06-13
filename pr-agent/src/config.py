import os
from dataclasses import dataclass, field
from typing import List

try:
    from dotenv import load_dotenv
except ImportError:
    def load_dotenv() -> None:
        return None


load_dotenv()

MAX_RETRIES = int(os.getenv("MAX_RETRIES", 3))
SUBPROCESS_TIMEOUT = int(os.getenv("SUBPROCESS_TIMEOUT", 30))
AGENT_CALL_TIMEOUT = int(os.getenv("AGENT_CALL_TIMEOUT", 60))
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5-coder:7b")
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
WORKSPACE_DIR = os.getenv("WORKSPACE_DIR", "./workspace")


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
        "A senior engineer who has designed hundreds of Python systems. "
        "Methodical, precise, always breaks problems into manageable steps."
    ),
    llm_model=OLLAMA_MODEL,
    temperature=0.3,
    max_tokens=800,
)

CODER_CONFIG = AgentConfig(
    name="Coder",
    role="Expert Python Developer",
    goal=(
        "Write clean, complete, runnable Python code from the given implementation plan. "
        "If an error context is provided, fix only what is broken. "
        "Return ONLY the Python script. No markdown fences. No explanation."
    ),
    backstory=(
        "A meticulous Python engineer who writes production-quality, PEP 8 code. "
        "When given an error, traces it precisely and fixes only the affected section."
    ),
    llm_model=OLLAMA_MODEL,
    temperature=0.15,
    max_tokens=2000,
)

QA_CONFIG = AgentConfig(
    name="QA Engineer",
    role="Quality Assurance Engineer",
    goal=(
        "Execute the provided Python script using the python_executor tool. "
        "Report the exact stdout, stderr, and exit code. Do not interpret — return raw output."
    ),
    backstory=(
        "A QA engineer who validates code correctness through execution. "
        "Rigorous, reports failures with full traceback context."
    ),
    llm_model=OLLAMA_MODEL,
    temperature=0.0,
    max_tokens=500,
    tools=["python_executor"],
)

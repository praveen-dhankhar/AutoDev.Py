from src.config import AGENT_CALL_TIMEOUT, OLLAMA_BASE_URL, AgentConfig


def build_llm(config: AgentConfig):
    try:
        from crewai import LLM
    except ImportError as exc:
        raise RuntimeError(
            "crewai is required for local open-source LLMs. "
            "Install dependencies with: pip install -r requirements.txt"
        ) from exc

    return LLM(
        model=f"ollama/{config.llm_model}",
        temperature=config.temperature,
        max_tokens=config.max_tokens,
        base_url=OLLAMA_BASE_URL,
        timeout=AGENT_CALL_TIMEOUT,
    )

from src.config import AGENT_CALL_TIMEOUT, LLM_MODEL, OLLAMA_BASE_URL, AgentConfig


def build_llm(config: AgentConfig):
    try:
        from crewai import LLM
    except ImportError as exc:
        raise RuntimeError(
            "crewai is required for local open-source LLMs. "
            "Install dependencies with: pip install -r requirements.txt"
        ) from exc

    if LLM_MODEL:
        # Hosted provider; credentials come from OPENAI_API_KEY / GEMINI_API_KEY.
        return LLM(
            model=LLM_MODEL,
            temperature=config.temperature,
            max_tokens=config.max_tokens,
            timeout=AGENT_CALL_TIMEOUT,
        )

    return LLM(
        model=f"ollama/{config.llm_model}",
        temperature=config.temperature,
        max_tokens=config.max_tokens,
        base_url=OLLAMA_BASE_URL,
        timeout=AGENT_CALL_TIMEOUT,
    )

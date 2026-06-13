from src.config import AGENT_CALL_TIMEOUT, OLLAMA_BASE_URL, AgentConfig


def build_llm(config: AgentConfig):
    try:
        from langchain_ollama import ChatOllama
    except ImportError as exc:
        raise RuntimeError(
            "langchain-ollama is required for local open-source LLMs. "
            "Install dependencies with: pip install -r requirements.txt"
        ) from exc

    return ChatOllama(
        model=config.llm_model,
        temperature=config.temperature,
        num_predict=config.max_tokens,
        base_url=OLLAMA_BASE_URL,
        client_kwargs={"timeout": AGENT_CALL_TIMEOUT},
    )

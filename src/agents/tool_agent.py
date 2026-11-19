"""Tool-calling agent: the model decides when to run, inspect, or search."""

from __future__ import annotations

from typing import Callable

from src.config import AGENT_CALL_TIMEOUT, CODER_CONFIG, OLLAMA_BASE_URL

SYSTEM_PROMPT = """You are an expert Python developer working with tools.
1. Write a complete Python script for the task and call run_code with it.
2. If run_code fails, study the traceback. You may call search_past_fixes with the
   error, or read_attempt to compare with earlier code. Then call run_code again
   with the full corrected script, never a diff.
3. Stop once run_code reports PASS."""


def _chat_model():
    from langchain_ollama import ChatOllama

    return ChatOllama(
        model=CODER_CONFIG.llm_model,
        base_url=OLLAMA_BASE_URL,
        temperature=CODER_CONFIG.temperature,
        num_predict=CODER_CONFIG.max_tokens,
        client_kwargs={"timeout": AGENT_CALL_TIMEOUT},
    )


def run_tool_agent(
    *,
    task: str,
    plan: str,
    tools: list[Callable],
    max_turns: int,
    should_stop: Callable[[], bool],
    llm=None,
) -> None:
    """Loop model turns until it stops calling tools, should_stop() is true, or turns run out."""
    from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage
    from langchain_core.tools import tool as as_tool

    by_name = {fn.__name__: as_tool(fn) for fn in tools}
    model = (llm or _chat_model()).bind_tools(list(by_name.values()))
    messages = [SystemMessage(SYSTEM_PROMPT), HumanMessage(f"Task:\n{task}\n\nPlan:\n{plan}")]

    for _ in range(max_turns):
        reply = model.invoke(messages)
        messages.append(reply)
        if not reply.tool_calls:
            return
        for call in reply.tool_calls:
            tool = by_name.get(call["name"])
            try:
                output = tool.invoke(call["args"]) if tool else f"Unknown tool: {call['name']}"
            except Exception as exc:  # bad arguments go back to the model as text
                output = f"Tool error: {exc}"
            messages.append(ToolMessage(content=str(output), tool_call_id=call["id"]))
            if should_stop():
                return

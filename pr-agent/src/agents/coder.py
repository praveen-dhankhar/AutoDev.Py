import re
from typing import Optional

from src.config import CODER_CONFIG
from src.llm import build_llm


def run_coder(plan: str, attempt: int, error: Optional[str] = None) -> str:
    try:
        from crewai import Agent, Crew, Task

        llm = build_llm(CODER_CONFIG)
        agent = Agent(
            role=CODER_CONFIG.role,
            goal=CODER_CONFIG.goal,
            backstory=CODER_CONFIG.backstory,
            llm=llm,
            verbose=False,
        )

        if error:
            description = f"""
Implementation plan:
{plan}

Attempt number: {attempt}

The previous attempt failed with this error:
{error}

Fix the code. Address the exact error. Return ONLY the corrected Python script with no markdown fences and no explanations.
"""
        else:
            description = f"""
Implementation plan:
{plan}

Write a complete, runnable Python script that implements this plan.
Return ONLY the Python script. No markdown fences. No explanations. No preamble.
"""

        task_obj = Task(
            description=description.strip(),
            expected_output=(
                "A complete, runnable Python script only, with no markdown fences, "
                "no explanation, and no preamble."
            ),
            agent=agent,
        )
        result = Crew(agents=[agent], tasks=[task_obj], verbose=False).kickoff()
        code = str(result)
        return re.sub(r"^```(?:python)?\n?", "", code.strip()).rstrip("```").strip()
    except Exception as e:
        raise RuntimeError(f"Coder agent failed: {e}") from e

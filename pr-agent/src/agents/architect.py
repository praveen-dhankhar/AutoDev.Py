from src.config import ARCHITECT_CONFIG
from src.llm import build_llm


def run_architect(task: str, log_callback=None) -> str:
    try:
        from crewai import Agent, Crew, Task

        llm = build_llm(ARCHITECT_CONFIG)
        agent = Agent(
            role=ARCHITECT_CONFIG.role,
            goal=ARCHITECT_CONFIG.goal,
            backstory=ARCHITECT_CONFIG.backstory,
            llm=llm,
            verbose=False,
        )
        task_obj = Task(
            description=f"Analyze and plan the implementation for this task:\n\n{task}",
            expected_output=(
                "A clear, numbered, step-by-step implementation plan. "
                "Do not write any code."
            ),
            agent=agent,
        )
        result = Crew(agents=[agent], tasks=[task_obj], verbose=False).kickoff()
        return str(result)
    except Exception as e:
        raise RuntimeError(f"Architect agent failed: {e}") from e

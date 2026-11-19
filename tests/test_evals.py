from evals.run import format_table, summarize, task_prompt
from evals.tasks import TASKS


def test_benchmark_has_50_unique_tasks():
    ids = [task["id"] for task in TASKS]
    assert len(ids) >= 50
    assert len(set(ids)) == len(ids)


def test_every_reference_solution_passes_its_assertions():
    for task in TASKS:
        namespace: dict = {}
        exec(task["solution"] + "\n" + "\n".join(task["tests"]), namespace)  # noqa: S102


def test_prompt_shows_tests_to_the_agent():
    task = TASKS[0]
    assert all(test in task_prompt(task) for test in task["tests"])


def test_summarize_and_lift_table():
    results = [
        {"passed": True, "attempts": 1},
        {"passed": True, "attempts": 3},
        {"passed": False, "attempts": 3},
        {"passed": False, "attempts": 1},
    ]
    assert summarize(results) == {
        "tasks": 4,
        "first_try_pass_rate": 0.25,
        "final_pass_rate": 0.5,
        "avg_retries": 1.0,
    }
    table = format_table(
        {"conditions": {"feedback": {"summary": summarize(results)}}, "feedback_lift": 0.25}
    )
    assert "| feedback | 4 | 25.0% | 50.0% | 1.0 |" in table
    assert "+25.0%" in table

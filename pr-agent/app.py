import queue
import threading
import time

import streamlit as st
from dotenv import load_dotenv

from src.models import AgentLogEntry
from src.models import AgentSession
from src.orchestrator import Orchestrator
from src.config import OLLAMA_MODEL


load_dotenv()

st.set_page_config(
    page_title="PR-Agent",
    page_icon="⚙️",
    layout="wide",
    initial_sidebar_state="expanded",
)

defaults = {
    "running": False,
    "current_session": None,
    "session_history": [],
    "log_queue": queue.Queue(),
    "result_queue": queue.Queue(),
    "config": {"model": OLLAMA_MODEL, "max_retries": 3, "timeout": 30},
    "all_log_entries": [],
    "task_input": "",
}
for k, v in defaults.items():
    if k not in st.session_state:
        st.session_state[k] = v

st.markdown(
    """
<style>
.status-badge { font-size: 0.85rem; padding: 2px 10px; border-radius: 12px; font-weight: 600; }
.status-idle      { background: #374151; color: #9CA3AF; }
.status-planning  { background: #1E3A5F; color: #60A5FA; }
.status-coding    { background: #14532D; color: #4ADE80; }
.status-executing { background: #431407; color: #FB923C; }
.status-correcting{ background: #451A03; color: #FCD34D; }
.status-completed { background: #14532D; color: #4ADE80; }
.status-failed    { background: #450A0A; color: #F87171; }
.stdout-block { border: 1px solid #14532D; border-radius: 8px; padding: 12px; background: #052E16; }
.stderr-block { border: 1px solid #7F1D1D; border-radius: 8px; padding: 12px; background: #450A0A; }
</style>
""",
    unsafe_allow_html=True,
)


def run_pipeline_thread(
    task: str,
    log_q: queue.Queue,
    result_q: queue.Queue,
    max_retries: int,
) -> None:
    try:
        orch = Orchestrator(log_queue=log_q, max_retries=max_retries)
        session = orch.run(task=task)
        result_q.put(session)
    except Exception as e:
        failed_session = AgentSession(task=task, status="failed")
        entry = AgentLogEntry(
            agent="system",
            message=f"Unexpected pipeline failure: {e}",
            level="error",
        )
        failed_session.logs.append(entry)
        log_q.put(entry)
        result_q.put(failed_session)


while not st.session_state.result_queue.empty():
    try:
        completed_session = st.session_state.result_queue.get_nowait()
        st.session_state.current_session = completed_session
        st.session_state.session_history.append(completed_session)
        st.session_state.running = False
    except queue.Empty:
        break

col_title, col_status, col_session = st.columns([3, 2, 1])
with col_title:
    st.title("PR-Agent ⚙️")
with col_status:
    status = (
        st.session_state.current_session.status
        if st.session_state.current_session
        else "idle"
    )
    if st.session_state.running and st.session_state.all_log_entries:
        last_agent = st.session_state.all_log_entries[-1].agent
        if last_agent == "architect":
            status = "planning"
        elif last_agent == "coder":
            status = "coding"
        elif last_agent == "qa":
            status = "executing"
    st.markdown(
        f'<span class="status-badge status-{status}">● {status.upper()}</span>',
        unsafe_allow_html=True,
    )
with col_session:
    session_count = len(st.session_state.session_history)
    st.caption(f"Session #{session_count + 1}")
st.divider()

left_col, main_col = st.columns([1, 2.5])

examples = [
    "Fetch the top 10 HackerNews stories and save them to a CSV file",
    "Sort a list of 10 random integers and print the result",
    "Check if a number is prime and print whether it is prime or not",
]

with left_col:
    st.subheader("What should I build?")
    user_task = st.text_area(
        "Task",
        key="task_input",
        height=140,
        disabled=st.session_state.running,
        label_visibility="collapsed",
        placeholder="Describe a Python script for the agents to build...",
    )

    st.caption("Examples")
    for idx, example in enumerate(examples):
        if st.button(
            example,
            key=f"example_{idx}",
            disabled=st.session_state.running,
            use_container_width=True,
        ):
            st.session_state.task_input = example
            st.rerun()

    run_disabled = st.session_state.running or not user_task.strip()
    run_label = "● Running..." if st.session_state.running else "▶ Run Agent Pipeline"
    if st.button(run_label, disabled=run_disabled, use_container_width=True):
        st.session_state.running = True
        st.session_state.log_queue = queue.Queue()
        st.session_state.result_queue = queue.Queue()
        st.session_state.all_log_entries = []
        st.session_state.current_session = None
        thread = threading.Thread(
            target=run_pipeline_thread,
            args=(
                user_task.strip(),
                st.session_state.log_queue,
                st.session_state.result_queue,
                st.session_state.config["max_retries"],
            ),
            daemon=True,
        )
        thread.start()
        st.rerun()

    with st.expander("Config", expanded=False):
        st.session_state.config["max_retries"] = st.select_slider(
            "Max retries",
            options=[1, 2, 3, 4, 5],
            value=st.session_state.config["max_retries"],
            disabled=st.session_state.running,
        )
        st.caption(f"Model: {st.session_state.config['model']} via Ollama")

    st.subheader("Session History")
    if st.session_state.session_history:
        for session in reversed(st.session_state.session_history):
            marker = "●" if session.status == "completed" else "○"
            result = "✓" if session.status == "completed" else "✗"
            excerpt = session.task[:52] + ("..." if len(session.task) > 52 else "")
            st.caption(f"{marker} {session.session_id} {result} — {excerpt}")
    else:
        st.caption("No sessions yet.")

with main_col:
    st.header("📡 Agent Activity Log")

    if st.session_state.running:
        while not st.session_state.log_queue.empty():
            try:
                entry = st.session_state.log_queue.get_nowait()
                st.session_state.all_log_entries.append(entry)
            except queue.Empty:
                break

    AGENT_DISPLAY = {
        "architect": ("🔵", "Architect"),
        "coder": ("🟢", "Coder"),
        "qa": ("🟠", "QA Engineer"),
        "system": ("⚙️", "System"),
    }

    with st.container(height=420):
        if not st.session_state.all_log_entries:
            st.caption("Agent logs will appear here when a run starts.")
        for entry in st.session_state.all_log_entries:
            avatar, display_name = AGENT_DISPLAY.get(entry.agent, ("⚙️", "System"))
            if entry.level == "error":
                avatar, display_name = "🔴", "QA Engineer"
            with st.chat_message(display_name, avatar=avatar):
                st.markdown(entry.message)

    session = st.session_state.current_session
    if session and session.attempts:
        st.header("💻 Generated Code")
        attempts = session.attempts
        if len(attempts) > 1:
            tabs = st.tabs(
                [
                    f"Attempt {attempt.attempt_number} {'✓' if attempt.passed else '✗'}"
                    for attempt in attempts
                ]
            )
            for tab, attempt in zip(tabs, attempts):
                with tab:
                    st.code(attempt.code, language="python")
        else:
            st.code(attempts[0].code, language="python")

        if session.status == "completed" and session.final_code:
            st.download_button(
                label="⬇ Download final.py",
                data=session.final_code,
                file_name="final.py",
                mime="text/x-python",
            )

        latest_attempt = session.latest_attempt
        if latest_attempt and latest_attempt.execution_result:
            result = latest_attempt.execution_result
            st.header("Execution Output")
            metric_status, metric_exit, metric_time = st.columns(3)
            metric_status.metric("Status", result.status.upper())
            metric_exit.metric("Exit Code", result.exit_code)
            metric_time.metric("Time", f"{result.execution_time_ms:.0f} ms")

            st.subheader("STDOUT")
            st.markdown('<div class="stdout-block">', unsafe_allow_html=True)
            st.code(result.stdout or "(no stdout)", language="text")
            st.markdown("</div>", unsafe_allow_html=True)

            if result.stderr:
                st.subheader("STDERR")
                st.markdown('<div class="stderr-block">', unsafe_allow_html=True)
                st.code(result.stderr, language="text")
                st.markdown("</div>", unsafe_allow_html=True)

if st.session_state.running:
    while not st.session_state.log_queue.empty():
        try:
            entry = st.session_state.log_queue.get_nowait()
            st.session_state.all_log_entries.append(entry)
        except queue.Empty:
            break
    time.sleep(0.3)
    st.rerun()

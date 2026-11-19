"""HTTP API: submit agent jobs, poll them, and stream state changes over SSE.

Run with `pr-agent serve`. Jobs live in memory and are lost on restart.
"""

from __future__ import annotations

import asyncio
import json
import os
import secrets
import threading
import uuid
from dataclasses import dataclass, field
from typing import Literal, Optional

from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from src.config import MAX_RETRIES, WORKSPACE_DIR
from src.models import AgentSession
from src.orchestrator import Orchestrator
from src.session_store import STATE_TO_STATUS

API_TOKEN = os.getenv("API_TOKEN", "")
MAX_CONCURRENT_JOBS = int(os.getenv("MAX_CONCURRENT_JOBS", 2))
SSE_POLL_SECONDS = 0.25


class EventLog(list):
    """A list the Orchestrator can use as its log queue (it only calls put)."""

    put = list.append


@dataclass
class Job:
    id: str
    task: str
    events: EventLog = field(default_factory=EventLog)
    cancel_event: threading.Event = field(default_factory=threading.Event)
    session: Optional[AgentSession] = None
    error: Optional[str] = None
    finished: bool = False

    @property
    def status(self) -> str:
        if self.session:
            return self.session.status
        if self.error:
            return "failed"
        for entry in reversed(self.events):
            if entry.event_type == "state_transition":
                return STATE_TO_STATUS.get(entry.to_state, "running")
        return "queued"

    def summary(self) -> dict:
        session = self.session
        return {
            "job_id": self.id,
            "task": self.task,
            "status": self.status,
            "session_id": session.session_id if session else None,
            "attempts": session.attempt_count if session else None,
            "final_code": session.final_code if session else None,
            "error": self.error,
        }


class JobRequest(BaseModel):
    task: str = Field(min_length=1, max_length=4000)
    max_retries: int = Field(default=MAX_RETRIES, ge=1, le=10)
    mode: Literal["classic", "tools"] = "classic"


def require_token(authorization: str = Header(default="")) -> None:
    if API_TOKEN and not secrets.compare_digest(authorization, f"Bearer {API_TOKEN}"):
        raise HTTPException(status_code=401, detail="Invalid or missing bearer token")


app = FastAPI(title="AutoDev.py", dependencies=[Depends(require_token)])
# NOTE: in-memory job table that never prunes; move to a DB when jobs must survive restarts.
jobs: dict[str, Job] = {}
_jobs_lock = threading.Lock()


def _run_job(job: Job, request: JobRequest) -> None:
    try:
        job.session = Orchestrator(
            log_queue=job.events,
            max_retries=request.max_retries,
            workspace_dir=WORKSPACE_DIR,
            cancel_event=job.cancel_event,
            mode=request.mode,
        ).run(job.task)
    except Exception as exc:
        job.error = str(exc)
    finally:
        job.finished = True


def _get_job(job_id: str) -> Job:
    job = jobs.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@app.post("/jobs", status_code=202)
def create_job(request: JobRequest) -> dict:
    with _jobs_lock:
        if sum(not job.finished for job in jobs.values()) >= MAX_CONCURRENT_JOBS:
            raise HTTPException(status_code=429, detail="Too many running jobs")
        job = Job(id=uuid.uuid4().hex[:12], task=request.task)
        jobs[job.id] = job
    threading.Thread(target=_run_job, args=(job, request), daemon=True).start()
    return {"job_id": job.id, "status": job.status}


@app.get("/jobs/{job_id}")
def get_job(job_id: str) -> dict:
    return _get_job(job_id).summary()


@app.post("/jobs/{job_id}/cancel", status_code=202)
def cancel_job(job_id: str) -> dict:
    job = _get_job(job_id)
    job.cancel_event.set()
    return {"job_id": job.id, "status": job.status}


@app.get("/jobs/{job_id}/events")
async def stream_events(job_id: str) -> StreamingResponse:
    """SSE stream: replays every event so far, then follows until the job ends."""
    job = _get_job(job_id)

    async def events():
        sent = 0
        while True:
            while sent < len(job.events):
                entry = job.events[sent]
                kind = "state" if entry.event_type == "state_transition" else "log"
                yield f"event: {kind}\ndata: {json.dumps(entry.to_dict())}\n\n"
                sent += 1
            if job.finished and sent >= len(job.events):
                yield f"event: end\ndata: {json.dumps(job.summary())}\n\n"
                return
            # NOTE: polls the event list; switch to per-client asyncio queues if latency matters.
            await asyncio.sleep(SSE_POLL_SECONDS)

    return StreamingResponse(
        events(), media_type="text/event-stream", headers={"Cache-Control": "no-cache"}
    )

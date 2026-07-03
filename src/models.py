from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Literal, Optional


ExecutionStatus = Literal["pass", "fail"]
SessionStatus = Literal[
    "idle",
    "planning",
    "coding",
    "executing",
    "correcting",
    "completed",
    "failed",
]
AgentName = Literal["architect", "coder", "qa", "system"]
LogLevel = Literal["info", "warning", "error", "success"]


@dataclass
class ExecutionResult:
    status: ExecutionStatus
    stdout: str
    stderr: str
    exit_code: int
    execution_time_ms: float
    script_path: str


@dataclass
class AttemptRecord:
    attempt_number: int
    code: str
    script_path: str
    execution_result: Optional[ExecutionResult] = None
    timestamp: datetime = field(default_factory=datetime.utcnow)

    @property
    def passed(self) -> bool:
        return (
            self.execution_result is not None
            and self.execution_result.status == "pass"
        )


@dataclass
class AgentLogEntry:
    agent: AgentName
    message: str
    level: LogLevel = "info"
    timestamp: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> dict:
        return {
            "agent": self.agent,
            "message": self.message,
            "level": self.level,
            "timestamp": self.timestamp.isoformat(),
        }


@dataclass
class AgentSession:
    session_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    task: str = ""
    status: SessionStatus = "idle"
    implementation_plan: Optional[str] = None
    attempts: List[AttemptRecord] = field(default_factory=list)
    logs: List[AgentLogEntry] = field(default_factory=list)
    final_code: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None

    @property
    def attempt_count(self) -> int:
        return len(self.attempts)

    @property
    def latest_attempt(self) -> Optional[AttemptRecord]:
        return self.attempts[-1] if self.attempts else None

    @property
    def passing_attempt(self) -> Optional[AttemptRecord]:
        return next((attempt for attempt in reversed(self.attempts) if attempt.passed), None)

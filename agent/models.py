"""
Pydantic models used across the agent system.
"""
from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------

class TaskStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    WAITING_APPROVAL = "waiting_approval"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ActionType(str, Enum):
    BROWSER_NAVIGATE = "browser_navigate"
    BROWSER_CLICK = "browser_click"
    BROWSER_TYPE = "browser_type"
    BROWSER_EXTRACT = "browser_extract"
    BROWSER_SCREENSHOT = "browser_screenshot"
    FILE_READ = "file_read"
    FILE_WRITE = "file_write"
    API_CALL = "api_call"
    MOCK_APP_READ = "mock_app_read"
    MOCK_APP_WRITE = "mock_app_write"
    MEMORY_STORE = "memory_store"
    MEMORY_RECALL = "memory_recall"
    VERIFY = "verify"
    ASK_USER = "ask_user"
    FINISH = "finish"


class StepStatus(str, Enum):
    PENDING = "pending"
    SUCCESS = "success"
    FAILED = "failed"
    RETRIED = "retried"
    SKIPPED = "skipped"


# ---------------------------------------------------------------------------
# Core domain models
# ---------------------------------------------------------------------------

class TaskRequest(BaseModel):
    """Incoming task from the user."""
    task: str = Field(..., description="Natural language description of the task")
    context: Optional[dict[str, Any]] = Field(default=None, description="Optional extra context")
    max_iterations: Optional[int] = Field(default=None)


class StepRecord(BaseModel):
    """A single action step taken by the agent."""
    step_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    action_type: ActionType
    description: str
    input_data: dict[str, Any] = Field(default_factory=dict)
    output_data: dict[str, Any] = Field(default_factory=dict)
    status: StepStatus = StepStatus.PENDING
    error: Optional[str] = None
    retry_count: int = 0
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    duration_ms: Optional[float] = None


class TaskRecord(BaseModel):
    """Full record of a task execution."""
    task_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    task: str
    status: TaskStatus = TaskStatus.PENDING
    steps: list[StepRecord] = Field(default_factory=list)
    memory: dict[str, Any] = Field(default_factory=dict)
    result: Optional[str] = None
    error: Optional[str] = None
    verification_passed: Optional[bool] = None
    verification_notes: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None


class ApprovalRequest(BaseModel):
    """Sent to the user when the agent needs approval before proceeding."""
    task_id: str
    step_id: str
    action_type: ActionType
    description: str
    details: dict[str, Any] = Field(default_factory=dict)
    options: list[str] = Field(default=["approve", "reject", "modify"])


class ApprovalResponse(BaseModel):
    """User's response to an approval request."""
    task_id: str
    step_id: str
    decision: str  # "approve" | "reject" | "modify"
    modification: Optional[str] = None


class AgentState(BaseModel):
    """Live state object passed through the LangGraph execution graph."""
    task_id: str
    task: str
    context: dict[str, Any] = Field(default_factory=dict)
    steps: list[StepRecord] = Field(default_factory=list)
    memory: dict[str, Any] = Field(default_factory=dict)
    iteration: int = 0
    max_iterations: int = 15
    status: TaskStatus = TaskStatus.RUNNING
    pending_approval: Optional[ApprovalRequest] = None
    approval_response: Optional[ApprovalResponse] = None
    result: Optional[str] = None
    error: Optional[str] = None
    verification_passed: Optional[bool] = None
    verification_notes: Optional[str] = None
    scratchpad: list[str] = Field(default_factory=list)  # agent's working notes


class ToolResult(BaseModel):
    """Standardised result returned by every tool."""
    success: bool
    output: Any = None
    error: Optional[str] = None
    metadata: dict[str, Any] = Field(default_factory=dict)

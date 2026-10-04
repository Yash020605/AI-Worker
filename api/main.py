"""
Main API Server — FastAPI on port 8000.

Endpoints:
  POST /tasks              — submit a new task
  GET  /tasks              — list all tasks
  GET  /tasks/{id}         — get task details + steps
  POST /tasks/{id}/approve — respond to an approval request
  GET  /tasks/{id}/stream  — SSE stream of live task updates
  GET  /health             — health check
"""
from __future__ import annotations

import asyncio
import json
import uuid
from datetime import datetime
from typing import Any, Optional

from fastapi import BackgroundTasks, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from agent.config import config
from agent.executor import run_task
from agent.logger import logger
from agent.models import (
    AgentState,
    ApprovalResponse,
    TaskRecord,
    TaskRequest,
    TaskStatus,
)

app = FastAPI(
    title="Autonomous AI Worker API",
    version="1.0.0",
    description="API for submitting tasks to the autonomous AI worker agent",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# In-memory task store (keyed by task_id)
# ---------------------------------------------------------------------------

_task_store: dict[str, AgentState] = {}
_task_events: dict[str, list[str]] = {}  # task_id → list of SSE event strings


def emit_event(task_id: str, event_type: str, data: dict) -> None:
    """Append an SSE event to the task's event queue."""
    if task_id not in _task_events:
        _task_events[task_id] = []
    payload = json.dumps({"type": event_type, "data": data, "ts": datetime.utcnow().isoformat()})
    _task_events[task_id].append(f"data: {payload}\n\n")


# ---------------------------------------------------------------------------
# Background task runner
# ---------------------------------------------------------------------------

async def _run_and_store(task_id: str, task: str, context: dict, max_iterations: Optional[int]) -> None:
    emit_event(task_id, "started", {"task_id": task_id, "task": task})
    try:
        state = await run_task(task, context=context, max_iterations=max_iterations)
        _task_store[task_id] = state
        emit_event(task_id, "completed", {
            "task_id": task_id,
            "status": state.status,
            "result": state.result,
            "verification_passed": state.verification_passed,
            "steps_count": len(state.steps),
        })
    except Exception as e:
        logger.error(f"[API] Task {task_id} failed: {e}")
        emit_event(task_id, "error", {"task_id": task_id, "error": str(e)})


# ---------------------------------------------------------------------------
# Request/Response models
# ---------------------------------------------------------------------------

class TaskSubmitResponse(BaseModel):
    task_id: str
    status: str
    message: str


class TaskSummary(BaseModel):
    task_id: str
    task: str
    status: str
    steps_count: int
    result: Optional[str]
    verification_passed: Optional[bool]
    created_at: Optional[str]


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.post("/tasks", response_model=TaskSubmitResponse, status_code=202)
async def submit_task(request: TaskRequest, background_tasks: BackgroundTasks):
    """Submit a natural language task to the agent."""
    task_id = str(uuid.uuid4())
    logger.info(f"[API] New task id={task_id!r} task={request.task[:60]!r}")

    background_tasks.add_task(
        _run_and_store,
        task_id,
        request.task,
        request.context or {},
        request.max_iterations,
    )

    return TaskSubmitResponse(
        task_id=task_id,
        status="accepted",
        message="Task accepted and running in background. Poll /tasks/{task_id} for status.",
    )


@app.get("/tasks")
async def list_tasks():
    """List all submitted tasks with summary."""
    summaries = []
    for task_id, state in _task_store.items():
        summaries.append({
            "task_id": state.task_id,
            "task": state.task[:100],
            "status": state.status,
            "steps_count": len(state.steps),
            "result": state.result,
            "verification_passed": state.verification_passed,
        })
    return {"tasks": summaries, "total": len(summaries)}


@app.get("/tasks/{task_id}")
async def get_task(task_id: str):
    """Get full details of a specific task."""
    if task_id not in _task_store:
        # Task may still be running
        if task_id in _task_events:
            return {"task_id": task_id, "status": "running", "message": "Task is still running"}
        raise HTTPException(status_code=404, detail=f"Task {task_id} not found")

    state = _task_store[task_id]
    return {
        "task_id": state.task_id,
        "task": state.task,
        "status": state.status,
        "result": state.result,
        "error": state.error,
        "verification_passed": state.verification_passed,
        "verification_notes": state.verification_notes,
        "iteration": state.iteration,
        "steps": [s.model_dump() for s in state.steps],
        "memory": state.memory,
        "scratchpad": state.scratchpad,
    }


@app.post("/tasks/{task_id}/approve")
async def respond_to_approval(task_id: str, response: ApprovalResponse):
    """Submit a human approval/rejection for a pending action."""
    if task_id not in _task_store:
        raise HTTPException(status_code=404, detail="Task not found")

    state = _task_store[task_id]
    if state.status != TaskStatus.WAITING_APPROVAL:
        raise HTTPException(status_code=400, detail="Task is not waiting for approval")

    state.approval_response = response
    state.status = TaskStatus.RUNNING
    emit_event(task_id, "approval_received", {"decision": response.decision})

    return {"message": "Approval response recorded", "decision": response.decision}


@app.get("/tasks/{task_id}/stream")
async def stream_task(task_id: str):
    """Server-Sent Events stream for live task updates."""
    async def event_generator():
        seen = 0
        while True:
            events = _task_events.get(task_id, [])
            for event in events[seen:]:
                yield event
                seen += 1

            # Check if task is done
            state = _task_store.get(task_id)
            if state and state.status in (TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED):
                yield "data: {\"type\": \"done\"}\n\n"
                break

            await asyncio.sleep(0.5)

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@app.get("/health")
async def health():
    return {
        "status": "ok",
        "service": "ai_worker_api",
        "tasks_in_store": len(_task_store),
        "model": config.LLM_MODEL,
    }


@app.get("/", response_class=HTMLResponse)
async def root():
    return HTMLResponse(content="""
<!DOCTYPE html>
<html>
<head><title>AI Worker API</title>
<style>body{font-family:system-ui;background:#0f172a;color:#e2e8f0;padding:40px;max-width:800px;margin:0 auto}
h1{color:#38bdf8}a{color:#7dd3fc}code{background:#1e293b;padding:2px 6px;border-radius:3px;font-size:0.9em}
.endpoint{background:#1e293b;border-radius:8px;padding:16px;margin:12px 0}
.method{font-weight:700;margin-right:8px}.get{color:#4ade80}.post{color:#f59e0b}
</style></head>
<body>
<h1>🤖 Autonomous AI Worker</h1>
<p>API is running. Use the endpoints below to submit and monitor tasks.</p>
<br>
<div class="endpoint"><span class="method post">POST</span><code>/tasks</code> — Submit a task<br>
<small>Body: <code>{"task": "Find the latest invoice from Acme Supplies and enter it into the system"}</code></small></div>
<div class="endpoint"><span class="method get">GET</span><code>/tasks</code> — List all tasks</div>
<div class="endpoint"><span class="method get">GET</span><code>/tasks/{id}</code> — Get task details</div>
<div class="endpoint"><span class="method get">GET</span><code>/tasks/{id}/stream</code> — Live SSE stream</div>
<div class="endpoint"><span class="method post">POST</span><code>/tasks/{id}/approve</code> — Human approval</div>
<br>
<p>📖 <a href="/docs">Interactive API Docs (Swagger UI)</a></p>
<p>🏢 <a href="http://localhost:8001">Mock Company App (port 8001)</a></p>
<p>🖥️ <a href="http://localhost:3000">Frontend UI (port 3000)</a></p>
</body>
</html>
""")

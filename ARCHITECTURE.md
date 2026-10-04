# Architecture Deep-Dive

## 1. System Overview

The Autonomous AI Worker is composed of four independent layers that communicate through well-defined interfaces:

```
┌───────────────────────────────────────────────────────────────────────┐
│  PRESENTATION LAYER                                                   │
│  frontend/index.html  ·  cli.py  ·  Swagger UI (/docs)               │
└────────────────────────────┬──────────────────────────────────────────┘
                             │ HTTP REST + SSE
┌────────────────────────────▼──────────────────────────────────────────┐
│  API LAYER  (api/main.py · port 8000)                                 │
│  FastAPI · Background tasks · SSE event bus · Approval handler        │
└────────────────────────────┬──────────────────────────────────────────┘
                             │ asyncio
┌────────────────────────────▼──────────────────────────────────────────┐
│  AGENT CORE  (agent/)                                                 │
│                                                                       │
│  executor.py  ──  LangGraph State Machine                             │
│  ┌──────────────────────────────────────────────────────────────┐    │
│  │  plan_node → execute_node → reflect_node → verify_node       │    │
│  │                ↕ ToolDispatcher                               │    │
│  │   browser │ file │ api │ mock_app │ memory                   │    │
│  └──────────────────────────────────────────────────────────────┘    │
│                                                                       │
│  memory.py    ──  ShortTermMemory + ConversationWindow                │
│  prompts.py   ──  System / Reflection / Verification prompts          │
│  llm.py       ──  LLM factory (OpenAI / Anthropic)                   │
│  models.py    ──  Pydantic data contracts                             │
└────────────────────────────┬──────────────────────────────────────────┘
                             │ HTTP (localhost)
┌────────────────────────────▼──────────────────────────────────────────┐
│  DATA LAYER  (mock_app/app.py · port 8001)                            │
│  In-memory store · REST API · Browser UI                              │
│  Invoices · Vendors · Payments · Tasks                                │
└───────────────────────────────────────────────────────────────────────┘
```

---

## 2. Agent Core — LangGraph State Machine

### State Object

Every node receives and returns an `AgentState` object:

```python
class AgentState(BaseModel):
    task_id: str
    task: str                       # original natural language task
    context: dict                   # extra context + inter-node signals
    steps: list[StepRecord]         # history of all actions taken
    memory: dict                    # snapshot of short-term memory
    iteration: int                  # current loop count
    max_iterations: int             # hard limit
    status: TaskStatus              # RUNNING / COMPLETED / FAILED / WAITING_APPROVAL
    pending_approval: ApprovalRequest | None
    result: str | None              # final answer
    verification_passed: bool | None
    scratchpad: list[str]           # agent's reasoning notes
```

### Node: PLAN

- Receives the raw task and builds the LLM context
- Provides the full tool catalogue to the LLM
- LLM outputs the first action as structured JSON
- Stored in `state.context["_next_action"]`

### Node: EXECUTE

- Reads `_next_action` from context
- Checks if the action requires human approval
- If yes: sets `status = WAITING_APPROVAL`, stores `ApprovalRequest`
- If no: routes to `ToolDispatcher.dispatch(action, params)`
- Records a `StepRecord` with timing, output, and error
- Stores result in `context["_last_result"]`

### Node: REFLECT

- Provides LLM with: all steps taken, memory facts, last result
- LLM reasons about progress and chooses the next action
- If task is done, outputs `{"action": "finish", "params": {"result": "..."}}`
- Otherwise outputs the next tool call

### Node: VERIFY

- Runs only when `status == COMPLETED`
- LLM evaluates: did the actions actually achieve the goal?
- Returns PASS or FAIL
- FAIL downgrades status back to FAILED

### Routing Logic

```
plan → execute
execute → verify      (if status == COMPLETED)
execute → reflect     (if still running)
execute → approval    (if waiting for human)
execute → END         (if failed)
reflect → execute     (if more work to do)
reflect → END         (if done or max iter)
verify → END
```

---

## 3. Tool Dispatcher

Central router that translates string action names to tool method calls:

```python
await dispatcher.dispatch("mock_list_invoices", {"company": "Acme"})
# → MockAppTool.list_invoices(company="Acme")
# → ApiTool.get("http://localhost:8001/api/invoices?company=Acme")
# → ToolResult(success=True, output={...})
```

All tools return `ToolResult(success, output, error, metadata)`.  
The dispatcher never throws — failures are captured in the result.

---

## 4. Memory System

Two layers:

**ShortTermMemory** (within a task):
- Key-value store for facts discovered during execution
- Example: `{"invoice_id": "inv001", "amount": 148500, "due_date": "2024-12-15"}`
- Serialised into every LLM prompt as "Known facts"

**ConversationWindow**:
- Sliding window of last N messages
- Prevents context overflow for long tasks
- Default window size: 10 messages

---

## 5. Human Approval System

Certain actions are gated behind human approval:

| Category | Actions |
|----------|---------|
| `payment` | `mock_record_payment` |
| `delete` | `file_delete`, `mock_delete` |
| `send_email` | Any email tool |
| `external_post` | Configurable |

When triggered:
1. Agent sets `status = WAITING_APPROVAL`
2. `ApprovalRequest` is stored in state
3. API server exposes this via `GET /tasks/{id}`
4. Frontend shows approve/reject buttons
5. User calls `POST /tasks/{id}/approve`
6. Agent receives decision and continues or aborts

---

## 6. Error Handling & Retry Strategy

**Tool level**: All tool methods catch exceptions and return `ToolResult(success=False, error=...)`. The agent never crashes from a tool error.

**HTTP level**: `ApiTool` uses tenacity to retry on `TimeoutException` and `ConnectError` with exponential backoff (1s → 2s → 4s, max 3 attempts).

**Agent level**: When a step fails, the LLM's REFLECT node sees the failure and reasons about alternatives:
- Try a different selector if browser click failed
- Try a different endpoint if API call failed
- Ask the user if the data is ambiguous

**Iteration limit**: Hard cap at `AGENT_MAX_ITERATIONS` (default 15) prevents infinite loops.

---

## 7. Prompt Design

Three prompt templates:

**SYSTEM_PROMPT**: Persistent context in every LLM call. Describes the agent's role, available tools, rules, and expected output format.

**REFLECTION_PROMPT**: Used in the REFLECT node. Provides full task history and asks: is this done? What's next? Is anything broken?

**VERIFICATION_PROMPT**: Used in the VERIFY node. Asks the LLM to judge whether the outcome actually matches the goal, with specific evidence criteria.

---

## 8. API Design

The API server runs tasks as background asyncio tasks, allowing immediate `202 Accepted` responses. Clients poll or stream for updates.

```
POST /tasks → 202 Accepted {task_id}
    ↓
Background: run_task(task) → AgentState
    ↓
GET /tasks/{id} → full state (poll)
GET /tasks/{id}/stream → SSE events (push)
```

This decoupled design means:
- The HTTP request doesn't block waiting for the LLM
- Multiple tasks can run concurrently
- The frontend stays responsive regardless of task duration

---

## 9. Security Considerations

| Risk | Mitigation |
|------|-----------|
| Path traversal | FileTool sandboxes all paths to `workspace_files/` |
| Destructive actions | Payment/delete require human approval |
| Prompt injection | System prompt clearly defines agent role and rules |
| Secrets in files | .env excluded from git; .env.example uses placeholder values |
| External data | Tool results treated as untrusted input to LLM context |

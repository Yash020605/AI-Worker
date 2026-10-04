# 🤖 Autonomous AI Worker

> A prototype of an AI worker that takes natural language tasks and autonomously completes them using a computer — browsing, reading files, calling APIs, and interacting with a simulated internal company application.

---

## 📋 Table of Contents

- [Overview](#overview)
- [Architecture](#architecture)
- [Features](#features)
- [Project Structure](#project-structure)
- [Setup & Installation](#setup--installation)
- [Running the System](#running-the-system)
- [Usage Examples](#usage-examples)
- [API Reference](#api-reference)
- [Design Decisions](#design-decisions)
- [Known Limitations](#known-limitations)
- [What I'd Build Next](#what-id-build-next)
- [Assumptions](#assumptions)
- [Tech Stack](#tech-stack)

---

## Overview

This system allows a user to describe a task in plain English and have an AI agent autonomously complete it by:

1. **Understanding** the goal (not just following steps)
2. **Planning** a sequence of actions
3. **Executing** actions using real tools (browser, files, APIs, internal app)
4. **Remembering** facts discovered during execution
5. **Recovering** from failures with retries and alternative strategies
6. **Verifying** the outcome was actually achieved
7. **Asking** for human approval on risky or ambiguous actions
8. **Reporting** a concise summary with evidence

### Example Task

```
"Find the latest invoice from Acme Supplies Ltd, extract the amount and due date,
enter it into the internal system, and tell me when it's done."
```

The agent will:
- Query the mock company app for Acme invoices
- Extract invoice number, amount, due date
- Store those facts in memory
- Update the internal system record
- Verify the update succeeded
- Return a summary with all values found

---

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    User / Frontend                       │
│              (index.html / CLI / API call)               │
└──────────────────────┬──────────────────────────────────┘
                       │ POST /tasks
                       ▼
┌─────────────────────────────────────────────────────────┐
│              FastAPI Agent API  (port 8000)              │
│   /tasks  /tasks/{id}  /tasks/{id}/approve  /stream     │
└──────────────────────┬──────────────────────────────────┘
                       │ asyncio background task
                       ▼
┌─────────────────────────────────────────────────────────┐
│                  LangGraph Agent Loop                    │
│                                                         │
│  ┌────────┐   ┌─────────┐   ┌──────────┐   ┌────────┐  │
│  │  PLAN  │──▶│ EXECUTE │──▶│ REFLECT  │──▶│ VERIFY │  │
│  └────────┘   └─────────┘   └──────────┘   └────────┘  │
│                    │              ▲                      │
│                    └──────────────┘  (loop until done)  │
│                                                         │
│  ┌──────────────────────────────────────────────────┐   │
│  │                 Tool Dispatcher                  │   │
│  │  Browser │ File │ API │ MockApp │ Memory         │   │
│  └──────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────┘
                       │ HTTP
                       ▼
┌─────────────────────────────────────────────────────────┐
│         Mock Company App  (port 8001)                   │
│   /api/invoices  /api/vendors  /api/payments  /api/tasks│
│            + HTML browser interface                     │
└─────────────────────────────────────────────────────────┘
```

### Agent Loop (LangGraph State Machine)

| Node | Role |
|------|------|
| **PLAN** | LLM receives the task, available tools, and context. Outputs the first action as JSON. |
| **EXECUTE** | Tool Dispatcher routes the action to the appropriate tool. Records a `StepRecord`. Checks if human approval is needed. |
| **REFLECT** | LLM reviews all steps taken, memory facts, and last result. Decides the next action. Loops back to EXECUTE. |
| **VERIFY** | After completion, LLM checks whether the task goal was actually achieved. Returns PASS/FAIL. |
| **APPROVAL_WAIT** | Pauses execution for human approval (payment, delete, external POST). |

---

## Features

| Feature | Implementation |
|---------|---------------|
| Natural language task understanding | GPT-4o / Claude 3.5 via LangChain |
| Agentic planning & re-planning | LangGraph ReAct-style loop |
| Browser automation | Playwright (navigate, click, type, extract, screenshot) |
| File operations | Read/write TXT, JSON, CSV with path sandboxing |
| HTTP API calls | HTTPX with retry + exponential backoff (tenacity) |
| Internal company app | FastAPI mock app with invoices, vendors, payments, tasks |
| Short-term memory | In-process key-value store per task run |
| Failure detection & retry | Tool-level error handling + LLM-guided alternative strategies |
| Verification | LLM judges whether outcome matches goal |
| Human approval | Pauses for approval on payment/delete/external POST |
| SSE live updates | Server-Sent Events stream per task |
| Web frontend | Single-file HTML/CSS/JS UI |
| CLI | Typer + Rich CLI with step-by-step output |
| Logging | Loguru (console + rotating file) |

---

## Project Structure

```
AI-Worker/
├── agent/                      # Core agent package
│   ├── config.py               # Env-based config
│   ├── executor.py             # LangGraph loop (main agent brain)
│   ├── llm.py                  # LLM factory (OpenAI / Anthropic)
│   ├── logger.py               # Loguru setup
│   ├── memory.py               # Short-term + conversation memory
│   ├── models.py               # Pydantic data models
│   ├── prompts.py              # System/reflection/verification prompts
│   └── tools/
│       ├── browser.py          # Playwright browser tool
│       ├── file_tool.py        # File read/write tool
│       ├── api_tool.py         # HTTP client tool
│       ├── mock_app_tool.py    # Internal company app tool
│       └── memory_tool.py      # Memory tool wrapper
│
├── api/
│   └── main.py                 # FastAPI server (port 8000)
│
├── mock_app/
│   └── app.py                  # Simulated company app (port 8001)
│
├── frontend/
│   └── index.html              # Single-page web UI
│
├── tests/
│   ├── test_tools.py           # Unit tests for tools
│   ├── test_mock_app.py        # Integration tests for mock app
│   └── test_executor.py        # Agent executor tests
│
├── cli.py                      # CLI entry point
├── run_api.py                  # API server runner
├── run_mock_app.py             # Mock app runner
├── requirements.txt            # Python dependencies
├── .env.example                # Environment variable template
└── README.md                   # This file
```

---

## Setup & Installation

### Prerequisites

- Python 3.11+
- An OpenAI API key (or Anthropic)

### 1. Clone the Repository

```bash
git clone https://github.com/Yash020605/AI-Worker.git
cd AI-Worker
```

### 2. Create a Virtual Environment

```bash
python -m venv venv

# Windows
venv\Scripts\activate

# macOS/Linux
source venv/bin/activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Install Playwright Browsers

```bash
playwright install chromium
```

### 5. Configure Environment

```bash
cp .env.example .env
```

Open `.env` and set your API key:

```env
OPENAI_API_KEY=sk-your-key-here
LLM_MODEL=gpt-4o
```

---

## Running the System

You need **two terminal windows** (or use the combined CLI command):

### Terminal 1 — Mock Company App

```bash
python run_mock_app.py
```

Starts the simulated internal company system at `http://localhost:8001`  
Browse to `http://localhost:8001` to see the invoice/vendor/task dashboard.

### Terminal 2 — AI Worker API

```bash
python run_api.py
```

Starts the agent API at `http://localhost:8000`  
Browse to `http://localhost:8000/docs` for interactive Swagger UI.

### Frontend UI

Open `frontend/index.html` directly in your browser.  
(No build step needed — it's a single HTML file.)

### Combined (CLI)

```bash
python cli.py serve
```

Starts both servers in one command.

---

## Usage Examples

### Via Frontend

1. Open `frontend/index.html` in Chrome/Firefox
2. Click an example task or type your own
3. Click **Run Task →**
4. Watch live steps, memory, and result populate

### Via CLI

```bash
# Basic task
python cli.py run "Find the latest invoice from Acme Supplies Ltd"

# With verbose scratchpad
python cli.py run "List all unpaid invoices and summarise" --verbose

# Quick demo
python cli.py demo

# Limit iterations
python cli.py run "Find TechVision invoice" --max-iter 8
```

### Via REST API

```bash
# Submit task
curl -X POST http://localhost:8000/tasks \
  -H "Content-Type: application/json" \
  -d '{"task": "Find the latest invoice from Acme Supplies Ltd and tell me the amount and due date"}'

# Response: {"task_id": "abc-123", "status": "accepted", ...}

# Poll for result
curl http://localhost:8000/tasks/abc-123

# Live SSE stream
curl http://localhost:8000/tasks/abc-123/stream
```

### Approve a Pending Action

```bash
curl -X POST http://localhost:8000/tasks/{task_id}/approve \
  -H "Content-Type: application/json" \
  -d '{"task_id": "abc-123", "step_id": "step-xyz", "decision": "approve"}'
```

---

## API Reference

### POST `/tasks`

Submit a task to the agent.

**Request body:**
```json
{
  "task": "Find the latest invoice from Acme Supplies Ltd",
  "context": {},
  "max_iterations": 15
}
```

**Response:**
```json
{
  "task_id": "uuid",
  "status": "accepted",
  "message": "Task accepted and running in background."
}
```

### GET `/tasks/{task_id}`

Get full task details including all steps, memory, and result.

### POST `/tasks/{task_id}/approve`

Submit human approval/rejection for a pending action.

```json
{
  "task_id": "uuid",
  "step_id": "uuid",
  "decision": "approve"  // or "reject"
}
```

### GET `/tasks/{task_id}/stream`

Server-Sent Events stream for live updates.

### GET `/health`

Health check.

---

## Design Decisions

### Why LangGraph Instead of Pure ReAct?

LangGraph gives explicit control over the state machine — each node (PLAN, EXECUTE, REFLECT, VERIFY) is a distinct function with clear inputs and outputs. This makes debugging much easier than a black-box chain. When the agent gets stuck or takes a wrong turn, you can see exactly which node failed and why.

### Why a Separate Mock App?

The mock app simulates a realistic internal company system. This means the agent can use its HTTP tool against a real server (not mocked), making the browser and API interactions genuine. It also means the demo works without any external services or credentials.

### Why Pydantic Models for Everything?

Every data structure (task request, step record, agent state, tool result) is a Pydantic model. This gives free validation, serialisation, and IDE support throughout the codebase. It also makes the API contracts explicit.

### Why SSE Instead of WebSockets?

SSE is simpler, works over plain HTTP, and is sufficient for one-way updates (server → client). WebSockets would add complexity for no benefit in this use case.

### Why Short-Term Memory as Key-Value?

The agent needs to remember specific facts (invoice amount, due date, IDs) and reference them later in the same task. A simple key-value store is sufficient for this and is easy to inspect. For long-running tasks or cross-session memory, a vector store would be appropriate.

### Tool Safety Design

- File tool sandboxes all paths to `workspace_files/` — path traversal is blocked
- Payment/delete actions require explicit human approval
- All tools return standardised `ToolResult` objects — the agent never crashes from a tool error, it adapts

---

## Known Limitations

1. **No persistent state** — all task data lives in memory and is lost on server restart. A database (PostgreSQL/SQLite) would fix this.

2. **Single-user** — no authentication, sessions, or multi-tenancy. Fine for a prototype; needs auth middleware for production.

3. **Browser automation is fragile** — CSS selectors break when websites update. A more robust approach would use semantic accessibility selectors or vision-based clicking.

4. **No streaming LLM responses** — the agent waits for full LLM responses. Streaming tokens to the frontend would improve perceived responsiveness.

5. **Memory is not semantic** — facts are stored as exact key-value pairs. A vector store would allow fuzzy recall ("find anything about the Acme invoice amount").

6. **Single agent, no sub-agents** — complex multi-step tasks would benefit from spawning specialised sub-agents (one for browsing, one for data extraction, etc.).

7. **No rate limiting** — multiple simultaneous task submissions could overwhelm the LLM API quota.

8. **Verification is LLM-based** — the agent judges its own work. A separate evaluator LLM or deterministic checks would be more reliable.

---

## What I'd Build Next

1. **Persistent storage** — SQLite/PostgreSQL for task history, audit logs, and memory persistence across sessions.

2. **Computer use / vision** — Integrate Claude Computer Use or GPT-4V to handle arbitrary screens without fragile CSS selectors.

3. **Sub-agent spawning** — Break complex tasks into parallel sub-agents (researcher, executor, verifier) coordinated by a supervisor.

4. **Streaming UI** — Stream LLM tokens to the frontend so users can watch the agent think in real time.

5. **Semantic memory** — Replace key-value memory with a vector store (ChromaDB/Pinecone) for fuzzy recall and cross-task knowledge.

6. **Task scheduling** — Cron-style recurring tasks ("every Monday, check for new overdue invoices").

7. **Richer evaluation framework** — Automated test suite that runs specific tasks and scores them on correctness, efficiency, and reliability.

8. **Auth + multi-tenancy** — JWT authentication, per-user task isolation, audit trails.

9. **Tool marketplace** — Plugin system so new tools (Slack, email, CRM) can be added without modifying the core agent.

10. **Observability** — OpenTelemetry tracing, Prometheus metrics, Grafana dashboard for monitoring agent performance in production.

---

## Assumptions

- The system runs in a trusted local environment (no authentication in the prototype)
- The mock company app represents a realistic subset of an internal ERP/accounting system
- The agent uses GPT-4o by default; any function-calling-capable model works
- "Latest invoice" means most recently created by `created_at` timestamp
- Human approval is simulated via API call (in production, this would be a Slack message, email, or UI prompt)
- All monetary values are in INR unless specified otherwise in the data
- Playwright runs in headless mode by default; set `BROWSER_HEADLESS=false` in `.env` to watch the browser

---

## Tech Stack

| Component | Technology |
|-----------|-----------|
| Agent reasoning | LangGraph + LangChain |
| LLM | OpenAI GPT-4o (or Claude 3.5 Sonnet) |
| API server | FastAPI + Uvicorn |
| Browser automation | Playwright (Chromium) |
| HTTP client | HTTPX + Tenacity |
| Data validation | Pydantic v2 |
| Logging | Loguru |
| CLI | Typer + Rich |
| Frontend | Vanilla HTML/CSS/JS (no build step) |
| Tests | Pytest + pytest-asyncio |

---

## License

MIT — built for the AI Engineering Internship technical assessment.

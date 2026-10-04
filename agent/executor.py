"""
Core agent execution loop using LangGraph.

Architecture:
  ┌─────────┐    ┌──────────┐    ┌─────────────┐    ┌──────────────┐
  │  START  │───▶│  PLAN    │───▶│  EXECUTE    │───▶│   REFLECT    │
  └─────────┘    └──────────┘    └─────────────┘    └──────┬───────┘
                                                            │
                      ┌─────────────────────────────────────┘
                      │
              ┌───────▼────────┐    ┌──────────────┐    ┌──────────┐
              │  APPROVAL_CHECK│───▶│  VERIFY      │───▶│   END    │
              └────────────────┘    └──────────────┘    └──────────┘

Each node receives the AgentState, mutates it, and returns the updated state.
Conditional edges decide which node comes next.
"""
from __future__ import annotations

import asyncio
import json
import time
import uuid
from datetime import datetime
from typing import Any, Literal

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langgraph.graph import END, StateGraph

from agent.config import config
from agent.llm import get_llm
from agent.logger import logger
from agent.memory import TaskMemory
from agent.models import (
    ActionType,
    AgentState,
    ApprovalRequest,
    StepRecord,
    StepStatus,
    TaskStatus,
    ToolResult,
)
from agent.prompts import (
    REFLECTION_PROMPT,
    SYSTEM_PROMPT,
    VERIFICATION_PROMPT,
)
from agent.tools import ApiTool, BrowserTool, FileTool, MemoryTool, MockAppTool


# ---------------------------------------------------------------------------
# Tool dispatcher
# ---------------------------------------------------------------------------

class ToolDispatcher:
    """Owns all tool instances for a single task run."""

    def __init__(self, task_memory: TaskMemory) -> None:
        self.browser = BrowserTool()
        self.file = FileTool()
        self.api = ApiTool()
        self.mock_app = MockAppTool()
        self.memory = MemoryTool(task_memory)
        self._browser_started = False

    async def dispatch(self, action: str, params: dict[str, Any]) -> ToolResult:
        """Route action string to the right tool method."""
        action = action.lower().strip()
        logger.info(f"[Dispatcher] {action} params={list(params.keys())}")

        # ── Browser ──────────────────────────────────────────────────────
        if action == "browser_navigate":
            return await self.browser.navigate(params["url"])
        elif action == "browser_click":
            return await self.browser.click(params["selector"])
        elif action == "browser_type":
            return await self.browser.type_text(params["selector"], params["text"])
        elif action == "browser_extract":
            return await self.browser.extract_text(params.get("selector", "body"))
        elif action == "browser_extract_table":
            return await self.browser.extract_table(params.get("selector", "table"))
        elif action == "browser_screenshot":
            path = params.get("path", f"screenshots/{uuid.uuid4().hex[:8]}.png")
            return await self.browser.screenshot(path)
        elif action == "browser_get_page":
            return await self.browser.get_page_text()
        elif action == "browser_fill_form":
            return await self.browser.fill_form(params["fields"])

        # ── File ─────────────────────────────────────────────────────────
        elif action == "file_read":
            return self.file.read(params["filename"])
        elif action == "file_write":
            return self.file.write(params["filename"], params["content"])
        elif action == "file_list":
            return self.file.list_files()

        # ── API ──────────────────────────────────────────────────────────
        elif action == "api_get":
            return await self.api.get(params["url"], params=params.get("params"))
        elif action == "api_post":
            return await self.api.post(params["url"], payload=params.get("payload"))
        elif action == "api_put":
            return await self.api.put(params["url"], payload=params.get("payload"))

        # ── Mock App ─────────────────────────────────────────────────────
        elif action == "mock_list_invoices":
            return await self.mock_app.list_invoices(params.get("company"))
        elif action == "mock_get_invoice":
            return await self.mock_app.get_invoice(params["invoice_id"])
        elif action == "mock_create_invoice":
            return await self.mock_app.create_invoice(params["data"])
        elif action == "mock_update_invoice":
            return await self.mock_app.update_invoice(params["invoice_id"], params["data"])
        elif action == "mock_list_vendors":
            return await self.mock_app.list_vendors()
        elif action == "mock_record_payment":
            return await self.mock_app.record_payment(params["data"])
        elif action == "mock_list_payments":
            return await self.mock_app.list_payments()
        elif action == "mock_create_task":
            return await self.mock_app.create_task(params["data"])
        elif action == "mock_list_tasks":
            return await self.mock_app.list_tasks()
        elif action == "mock_read":
            return await self.mock_app.read(params["resource"], params.get("id"))
        elif action == "mock_write":
            return await self.mock_app.write(params["resource"], params["data"], params.get("id"))

        # ── Memory ───────────────────────────────────────────────────────
        elif action == "memory_store":
            return self.memory.store(params["key"], params["value"])
        elif action == "memory_recall":
            return self.memory.recall(params["key"])
        elif action == "memory_recall_all":
            return self.memory.recall_all()

        else:
            return ToolResult(success=False, error=f"Unknown action: {action!r}")

    async def cleanup(self) -> None:
        await self.browser.stop()


# ---------------------------------------------------------------------------
# LLM action parser
# ---------------------------------------------------------------------------

def parse_llm_action(text: str) -> dict[str, Any]:
    """
    Parse the LLM's chosen action from its response text.
    Expected format (JSON block):
        ```json
        {
          "action": "mock_list_invoices",
          "params": {"company": "Acme Corp"},
          "reasoning": "Need to find the latest invoice from Acme Corp"
        }
        ```
    Falls back gracefully if JSON is malformed.
    """
    import re
    # Try to find a JSON block
    pattern = r"```(?:json)?\s*(\{.*?\})\s*```"
    match = re.search(pattern, text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            pass

    # Try to find any JSON-like object
    try:
        start = text.index("{")
        end = text.rindex("}") + 1
        return json.loads(text[start:end])
    except (ValueError, json.JSONDecodeError):
        pass

    # If the model says FINAL ANSWER, signal completion
    if "FINAL ANSWER" in text.upper():
        return {"action": "finish", "params": {"result": text}, "reasoning": "Task complete"}

    # Default — ask user for clarification
    return {
        "action": "ask_user",
        "params": {"question": "I'm not sure how to proceed. Can you clarify?"},
        "reasoning": "Could not parse LLM action",
    }


def needs_approval(action: str, config_list: list[str]) -> bool:
    """Check if the action requires human approval."""
    approval_map = {
        "delete": ["file_delete", "mock_delete"],
        "payment": ["mock_record_payment"],
        "send_email": ["api_post_email", "email_send"],
        "external_post": [],
    }
    for category in config_list:
        for pattern in approval_map.get(category, []):
            if action.startswith(pattern):
                return True
    return False


# ---------------------------------------------------------------------------
# Graph nodes
# ---------------------------------------------------------------------------

async def plan_node(state: AgentState) -> AgentState:
    """Generate initial reasoning and first action."""
    logger.info(f"[Plan] task={state.task[:60]!r}")
    state.scratchpad.append(f"Task received: {state.task}")

    llm = get_llm()
    messages = [
        SystemMessage(content=SYSTEM_PROMPT),
        HumanMessage(content=f"""Task: {state.task}

Context: {json.dumps(state.context, indent=2) if state.context else 'None'}

Available actions (use exactly these action names):
- mock_list_invoices: {{company?: str}} — list invoices from internal system
- mock_get_invoice: {{invoice_id: str}} — get invoice details
- mock_create_invoice: {{data: dict}} — create a new invoice
- mock_update_invoice: {{invoice_id: str, data: dict}} — update invoice
- mock_list_vendors: {{}} — list vendors
- mock_record_payment: {{data: dict}} — record a payment (REQUIRES APPROVAL)
- mock_list_payments: {{}} — list payments
- mock_create_task: {{data: dict}} — create a work task
- mock_list_tasks: {{}} — list tasks
- browser_navigate: {{url: str}} — navigate to a URL
- browser_click: {{selector: str}} — click an element
- browser_type: {{selector: str, text: str}} — type text
- browser_extract: {{selector?: str}} — extract text from page
- browser_extract_table: {{selector?: str}} — extract a table
- browser_get_page: {{}} — get full page text
- browser_fill_form: {{fields: dict}} — fill a form
- browser_screenshot: {{path?: str}} — take a screenshot
- file_read: {{filename: str}} — read a file
- file_write: {{filename: str, content: any}} — write a file
- file_list: {{}} — list files
- api_get: {{url: str, params?: dict}} — HTTP GET
- api_post: {{url: str, payload?: dict}} — HTTP POST
- memory_store: {{key: str, value: any}} — store a fact
- memory_recall: {{key: str}} — recall a stored fact
- memory_recall_all: {{}} — recall all stored facts
- ask_user: {{question: str}} — ask the user for clarification
- finish: {{result: str}} — task complete, return final result

Respond with your first action as JSON:
```json
{{
  "action": "action_name",
  "params": {{}},
  "reasoning": "why this action"
}}
```
"""),
    ]

    response = await llm.ainvoke(messages)
    action_data = parse_llm_action(response.content)

    state.scratchpad.append(f"Plan: {action_data.get('reasoning', '')}")
    state.context["_next_action"] = action_data
    return state


async def execute_node(state: AgentState) -> AgentState:
    """Execute the current action using the tool dispatcher."""
    action_data = state.context.get("_next_action", {})
    action = action_data.get("action", "ask_user")
    params = action_data.get("params", {})
    reasoning = action_data.get("reasoning", "")

    logger.info(f"[Execute] iter={state.iteration} action={action!r}")

    step = StepRecord(
        action_type=ActionType.VERIFY if action == "verify" else ActionType.ASK_USER if action == "ask_user" else ActionType.FINISH if action == "finish" else ActionType.MOCK_APP_READ,
        description=f"{action}: {reasoning}",
        input_data={"action": action, "params": params},
    )

    # Check if approval needed
    if needs_approval(action, config.REQUIRE_APPROVAL_FOR):
        step.status = StepStatus.PENDING
        state.status = TaskStatus.WAITING_APPROVAL
        state.pending_approval = ApprovalRequest(
            task_id=state.task_id,
            step_id=step.step_id,
            action_type=step.action_type,
            description=f"Agent wants to: {action}",
            details=params,
        )
        state.steps.append(step)
        return state

    # Get or create dispatcher from context
    if "_dispatcher" not in state.context:
        task_memory = TaskMemory()
        dispatcher = ToolDispatcher(task_memory)
        # Store dispatcher reference (not serialisable, but fine for in-process use)
        state.context["_dispatcher"] = dispatcher
        state.context["_task_memory"] = task_memory

    dispatcher: ToolDispatcher = state.context["_dispatcher"]

    start_ms = time.time() * 1000

    if action == "finish":
        step.status = StepStatus.SUCCESS
        step.output_data = {"result": params.get("result", "Task completed")}
        state.result = params.get("result", "Task completed")
        state.status = TaskStatus.COMPLETED
        step.duration_ms = time.time() * 1000 - start_ms
        state.steps.append(step)
        return state

    if action == "ask_user":
        step.status = StepStatus.SUCCESS
        step.output_data = {"question": params.get("question")}
        state.status = TaskStatus.WAITING_APPROVAL
        state.pending_approval = ApprovalRequest(
            task_id=state.task_id,
            step_id=step.step_id,
            action_type=ActionType.ASK_USER,
            description=params.get("question", "Agent needs clarification"),
            details=params,
            options=["answer"],
        )
        state.steps.append(step)
        return state

    # Execute tool
    result: ToolResult = await dispatcher.dispatch(action, params)
    step.duration_ms = time.time() * 1000 - start_ms

    if result.success:
        step.status = StepStatus.SUCCESS
        step.output_data = {"output": result.output, "metadata": result.metadata}
        state.scratchpad.append(f"✓ {action} → {str(result.output)[:200]}")
    else:
        step.status = StepStatus.FAILED
        step.error = result.error
        state.scratchpad.append(f"✗ {action} FAILED: {result.error}")

    # Store last result in context for reflect node
    state.context["_last_result"] = {
        "action": action,
        "success": result.success,
        "output": str(result.output)[:500] if result.output else None,
        "error": result.error,
    }

    state.iteration += 1
    state.steps.append(step)
    return state


async def reflect_node(state: AgentState) -> AgentState:
    """LLM reflects on progress and decides the next action."""
    logger.info(f"[Reflect] iter={state.iteration}")

    if state.iteration >= state.max_iterations:
        state.status = TaskStatus.FAILED
        state.error = f"Max iterations ({state.max_iterations}) reached"
        return state

    if state.status in (TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.WAITING_APPROVAL):
        return state

    steps_summary = "\n".join(
        f"  {i+1}. [{s.status}] {s.description[:80]}"
        + (f" → {str(s.output_data.get('output',''))[:100]}" if s.output_data else "")
        for i, s in enumerate(state.steps[-10:])  # last 10 steps
    )

    dispatcher: ToolDispatcher = state.context.get("_dispatcher")
    memory_facts = dispatcher.memory.as_context_string() if dispatcher else "None"
    last_result = json.dumps(state.context.get("_last_result", {}), indent=2)

    llm = get_llm()
    prompt = REFLECTION_PROMPT.format(
        iteration=state.iteration,
        task=state.task,
        steps_summary=steps_summary or "No steps yet",
        memory_facts=memory_facts,
        last_result=last_result,
    )

    messages = [
        SystemMessage(content=SYSTEM_PROMPT),
        HumanMessage(content=prompt + """

Respond with your next action as JSON:
```json
{
  "action": "action_name",
  "params": {},
  "reasoning": "why this action"
}
```
If the task is complete, use action "finish" with params {"result": "summary of what was accomplished"}.
"""),
    ]

    response = await llm.ainvoke(messages)
    action_data = parse_llm_action(response.content)

    state.context["_next_action"] = action_data
    state.scratchpad.append(f"Reflect → {action_data.get('action')} ({action_data.get('reasoning','')[:80]})")
    return state


async def verify_node(state: AgentState) -> AgentState:
    """Verify that the task was actually completed."""
    logger.info("[Verify] running verification")

    if state.status == TaskStatus.FAILED:
        return state

    steps_summary = "\n".join(
        f"  {i+1}. [{s.status}] {s.description[:80]}"
        for i, s in enumerate(state.steps)
    )

    dispatcher: ToolDispatcher = state.context.get("_dispatcher")
    memory_facts = dispatcher.memory.as_context_string() if dispatcher else "None"

    evidence = state.result or "No explicit result captured"

    llm = get_llm()
    prompt = VERIFICATION_PROMPT.format(
        task=state.task,
        steps_summary=steps_summary,
        evidence=evidence,
        memory_facts=memory_facts,
    )

    response = await llm.ainvoke([
        SystemMessage(content=SYSTEM_PROMPT),
        HumanMessage(content=prompt),
    ])

    verification_text = response.content
    passed = "PASS" in verification_text.upper() and "FAIL" not in verification_text.upper().split("PASS")[0]

    state.verification_passed = passed
    state.verification_notes = verification_text[:500]
    state.scratchpad.append(f"Verification: {'PASS' if passed else 'FAIL'}")

    if not passed and state.status == TaskStatus.COMPLETED:
        state.status = TaskStatus.FAILED
        state.error = "Verification failed: " + verification_text[:200]

    return state


# ---------------------------------------------------------------------------
# Routing functions
# ---------------------------------------------------------------------------

def route_after_execute(state: AgentState) -> Literal["verify", "reflect", "approval_wait", "__end__"]:
    if state.status == TaskStatus.COMPLETED:
        return "verify"
    if state.status == TaskStatus.FAILED:
        return "__end__"
    if state.status == TaskStatus.WAITING_APPROVAL:
        return "approval_wait"
    return "reflect"


def route_after_reflect(state: AgentState) -> Literal["execute", "__end__"]:
    if state.status in (TaskStatus.COMPLETED, TaskStatus.FAILED):
        return "__end__"
    if state.iteration >= state.max_iterations:
        return "__end__"
    return "execute"


def approval_wait_node(state: AgentState) -> AgentState:
    """Placeholder node — actual waiting happens outside the graph."""
    return state


# ---------------------------------------------------------------------------
# Graph builder
# ---------------------------------------------------------------------------

def build_graph():
    workflow = StateGraph(AgentState)

    workflow.add_node("plan", plan_node)
    workflow.add_node("execute", execute_node)
    workflow.add_node("reflect", reflect_node)
    workflow.add_node("verify", verify_node)
    workflow.add_node("approval_wait", approval_wait_node)

    workflow.set_entry_point("plan")
    workflow.add_edge("plan", "execute")
    workflow.add_conditional_edges("execute", route_after_execute, {
        "verify": "verify",
        "reflect": "reflect",
        "approval_wait": "approval_wait",
        "__end__": END,
    })
    workflow.add_conditional_edges("reflect", route_after_reflect, {
        "execute": "execute",
        "__end__": END,
    })
    workflow.add_edge("verify", END)
    workflow.add_edge("approval_wait", END)

    return workflow.compile()


# ---------------------------------------------------------------------------
# Public runner
# ---------------------------------------------------------------------------

async def run_task(
    task: str,
    context: dict[str, Any] | None = None,
    max_iterations: int | None = None,
) -> AgentState:
    """Run a task through the agent graph and return the final state."""
    graph = build_graph()

    initial_state = AgentState(
        task_id=str(uuid.uuid4()),
        task=task,
        context=context or {},
        max_iterations=max_iterations or config.AGENT_MAX_ITERATIONS,
    )

    logger.info(f"[Runner] Starting task_id={initial_state.task_id!r}")
    logger.info(f"[Runner] Task: {task[:100]!r}")

    try:
        final_state = await graph.ainvoke(initial_state)
    except Exception as e:
        logger.error(f"[Runner] Unhandled error: {e}")
        initial_state.status = TaskStatus.FAILED
        initial_state.error = str(e)
        final_state = initial_state

    # Cleanup browser
    dispatcher = final_state.context.get("_dispatcher") if hasattr(final_state, "context") else None
    if dispatcher:
        await dispatcher.cleanup()

    logger.info(f"[Runner] Done. status={final_state.status} verified={final_state.verification_passed}")
    return final_state

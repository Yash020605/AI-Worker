"""
Tests for the agent executor — uses mocked LLM to avoid real API calls.

Run: pytest tests/test_executor.py -v
"""
from __future__ import annotations

import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from agent.executor import ToolDispatcher, parse_llm_action, needs_approval, build_graph
from agent.memory import TaskMemory
from agent.models import AgentState, TaskStatus


# ── parse_llm_action ─────────────────────────────────────────────────────────

class TestParseLlmAction:
    def test_parse_json_block(self):
        text = '''Here is my action:
```json
{
  "action": "mock_list_invoices",
  "params": {"company": "Acme"},
  "reasoning": "need to find invoices"
}
```'''
        result = parse_llm_action(text)
        assert result["action"] == "mock_list_invoices"
        assert result["params"]["company"] == "Acme"

    def test_parse_bare_json(self):
        text = '{"action": "memory_store", "params": {"key": "amount", "value": 1500}, "reasoning": "store it"}'
        result = parse_llm_action(text)
        assert result["action"] == "memory_store"

    def test_final_answer_detected(self):
        text = "FINAL ANSWER: The task is complete. Summary: Found invoice INV-001."
        result = parse_llm_action(text)
        assert result["action"] == "finish"

    def test_malformed_falls_back_to_ask_user(self):
        text = "I am not sure what to do here, the data is unclear"
        result = parse_llm_action(text)
        assert result["action"] == "ask_user"


# ── needs_approval ────────────────────────────────────────────────────────────

class TestNeedsApproval:
    def test_payment_needs_approval(self):
        assert needs_approval("mock_record_payment", ["payment"]) is True

    def test_navigate_no_approval(self):
        assert needs_approval("browser_navigate", ["payment", "delete"]) is False

    def test_delete_needs_approval(self):
        assert needs_approval("file_delete", ["delete"]) is True

    def test_empty_config_no_approval(self):
        assert needs_approval("mock_record_payment", []) is False


# ── ToolDispatcher ────────────────────────────────────────────────────────────

class TestToolDispatcher:
    def setup_method(self):
        self.memory = TaskMemory()
        self.dispatcher = ToolDispatcher(self.memory)

    def test_memory_store_and_recall(self):
        async def run():
            store_result = await self.dispatcher.dispatch("memory_store", {"key": "test", "value": "hello"})
            assert store_result.success

            recall_result = await self.dispatcher.dispatch("memory_recall", {"key": "test"})
            assert recall_result.success
            assert recall_result.output["test"] == "hello"

        asyncio.run(run())

    def test_unknown_action(self):
        async def run():
            result = await self.dispatcher.dispatch("totally_unknown_action", {})
            assert not result.success
            assert "Unknown action" in result.error

        asyncio.run(run())

    def test_file_write_and_read(self):
        async def run():
            write = await self.dispatcher.dispatch("file_write", {"filename": "test_exec.txt", "content": "agent test"})
            assert write.success

            read = await self.dispatcher.dispatch("file_read", {"filename": "test_exec.txt"})
            assert read.success
            assert read.output == "agent test"

            self.dispatcher.file.delete("test_exec.txt")

        asyncio.run(run())


# ── AgentState ────────────────────────────────────────────────────────────────

class TestAgentState:
    def test_default_state(self):
        state = AgentState(task_id="t1", task="do something")
        assert state.status == TaskStatus.RUNNING
        assert state.iteration == 0
        assert state.steps == []
        assert state.scratchpad == []

    def test_state_serialisation(self):
        state = AgentState(task_id="t1", task="test", context={"key": "val"})
        data = state.model_dump()
        assert data["task"] == "test"
        assert data["context"]["key"] == "val"


# ── Graph structure ───────────────────────────────────────────────────────────

class TestGraphStructure:
    def test_graph_builds_without_error(self):
        """Ensure the LangGraph compiles without raising."""
        graph = build_graph()
        assert graph is not None

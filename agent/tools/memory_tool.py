"""
Memory tool — LangChain-compatible wrapper around TaskMemory.
Allows the agent to store and recall facts during a run.
"""
from __future__ import annotations

from typing import Any

from agent.logger import logger
from agent.memory import TaskMemory
from agent.models import ToolResult


class MemoryTool:

    def __init__(self, task_memory: TaskMemory) -> None:
        self._mem = task_memory

    def store(self, key: str, value: Any) -> ToolResult:
        try:
            self._mem.facts.store(key, value)
            return ToolResult(success=True, output={"stored": {key: value}})
        except Exception as e:
            return ToolResult(success=False, error=str(e))

    def recall(self, key: str) -> ToolResult:
        try:
            value = self._mem.facts.recall(key)
            if value is None:
                return ToolResult(success=False, error=f"No value stored for key: {key!r}")
            return ToolResult(success=True, output={key: value})
        except Exception as e:
            return ToolResult(success=False, error=str(e))

    def recall_all(self) -> ToolResult:
        try:
            facts = self._mem.facts.recall_all()
            return ToolResult(success=True, output=facts)
        except Exception as e:
            return ToolResult(success=False, error=str(e))

    def as_context_string(self) -> str:
        return self._mem.facts.as_context_string()

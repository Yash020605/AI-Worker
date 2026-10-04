"""
Agent memory system.

Two layers:
  1. Short-term (in-process dict) — key/value store that lives for one task.
  2. Conversation window — keeps the last N messages for LLM context.
"""
from __future__ import annotations

from collections import deque
from typing import Any, Optional

from agent.config import config
from agent.logger import logger


class ShortTermMemory:
    """
    Simple key-value store for a single task execution.
    Stores facts the agent discovers during a run
    (e.g. invoice amount, due date, extracted values).
    """

    def __init__(self) -> None:
        self._store: dict[str, Any] = {}

    def store(self, key: str, value: Any) -> None:
        logger.debug(f"[Memory] store  {key!r} = {value!r}")
        self._store[key] = value

    def recall(self, key: str, default: Any = None) -> Any:
        value = self._store.get(key, default)
        logger.debug(f"[Memory] recall {key!r} → {value!r}")
        return value

    def recall_all(self) -> dict[str, Any]:
        return dict(self._store)

    def delete(self, key: str) -> None:
        self._store.pop(key, None)

    def clear(self) -> None:
        self._store.clear()

    def as_context_string(self) -> str:
        if not self._store:
            return "No facts stored yet."
        lines = [f"  • {k}: {v}" for k, v in self._store.items()]
        return "Known facts:\n" + "\n".join(lines)


class ConversationWindow:
    """
    Sliding window of recent agent messages for LLM context.
    Prevents token overflow for long-running tasks.
    """

    def __init__(self, max_size: int = config.MEMORY_WINDOW_SIZE) -> None:
        self._window: deque[dict[str, str]] = deque(maxlen=max_size)

    def add(self, role: str, content: str) -> None:
        self._window.append({"role": role, "content": content})

    def get_messages(self) -> list[dict[str, str]]:
        return list(self._window)

    def clear(self) -> None:
        self._window.clear()


class TaskMemory:
    """Combined memory object for one task run."""

    def __init__(self) -> None:
        self.facts = ShortTermMemory()
        self.conversation = ConversationWindow()

    def snapshot(self) -> dict[str, Any]:
        return {
            "facts": self.facts.recall_all(),
            "conversation_length": len(self.conversation.get_messages()),
        }

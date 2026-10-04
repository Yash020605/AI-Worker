"""
Unit tests for individual tools.
Run: pytest tests/test_tools.py -v
"""
import os
import pytest
from agent.tools.file_tool import FileTool
from agent.tools.memory_tool import MemoryTool
from agent.memory import TaskMemory
from agent.models import ToolResult


# ── FileTool ──────────────────────────────────────────────────────────────────

class TestFileTool:
    def setup_method(self):
        self.tool = FileTool()

    def test_write_and_read_text(self):
        result = self.tool.write("test_file.txt", "hello world")
        assert result.success

        result = self.tool.read("test_file.txt")
        assert result.success
        assert result.output == "hello world"

    def test_write_and_read_json(self):
        data = {"name": "Acme Corp", "amount": 1500.50}
        result = self.tool.write("test_data.json", data)
        assert result.success

        result = self.tool.read("test_data.json")
        assert result.success
        assert result.output["name"] == "Acme Corp"
        assert result.output["amount"] == 1500.50

    def test_write_and_read_csv(self):
        data = [{"id": "1", "name": "Alice"}, {"id": "2", "name": "Bob"}]
        result = self.tool.write("test_data.csv", data)
        assert result.success

        result = self.tool.read("test_data.csv")
        assert result.success
        assert len(result.output) == 2
        assert result.output[0]["name"] == "Alice"

    def test_read_nonexistent_file(self):
        result = self.tool.read("nonexistent_xyz.txt")
        assert not result.success
        assert "not found" in result.error.lower()

    def test_path_traversal_blocked(self):
        with pytest.raises(ValueError):
            self.tool._safe_path("../../etc/passwd")

    def test_list_files(self):
        self.tool.write("list_test.txt", "data")
        result = self.tool.list_files()
        assert result.success
        assert "list_test.txt" in result.output

    def teardown_method(self):
        for f in ["test_file.txt", "test_data.json", "test_data.csv", "list_test.txt"]:
            self.tool.delete(f)


# ── MemoryTool ────────────────────────────────────────────────────────────────

class TestMemoryTool:
    def setup_method(self):
        self.task_memory = TaskMemory()
        self.tool = MemoryTool(self.task_memory)

    def test_store_and_recall(self):
        result = self.tool.store("invoice_amount", 148500.0)
        assert result.success

        result = self.tool.recall("invoice_amount")
        assert result.success
        assert result.output["invoice_amount"] == 148500.0

    def test_recall_missing_key(self):
        result = self.tool.recall("nonexistent_key")
        assert not result.success

    def test_recall_all(self):
        self.tool.store("key1", "val1")
        self.tool.store("key2", "val2")
        result = self.tool.recall_all()
        assert result.success
        assert "key1" in result.output
        assert "key2" in result.output

    def test_store_various_types(self):
        self.tool.store("str_val", "hello")
        self.tool.store("int_val", 42)
        self.tool.store("dict_val", {"nested": True})
        self.tool.store("list_val", [1, 2, 3])

        assert self.tool.recall("str_val").output["str_val"] == "hello"
        assert self.tool.recall("int_val").output["int_val"] == 42

    def test_context_string(self):
        self.tool.store("due_date", "2024-12-15")
        ctx = self.tool.as_context_string()
        assert "due_date" in ctx
        assert "2024-12-15" in ctx


# ── Tool Result ───────────────────────────────────────────────────────────────

class TestToolResult:
    def test_success_result(self):
        r = ToolResult(success=True, output={"key": "val"})
        assert r.success
        assert r.output["key"] == "val"
        assert r.error is None

    def test_failure_result(self):
        r = ToolResult(success=False, error="Something went wrong")
        assert not r.success
        assert r.error == "Something went wrong"
        assert r.output is None

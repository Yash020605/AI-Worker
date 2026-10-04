"""
File tool — read and write local files.
Supports: txt, json, csv, pdf (text extraction).
"""
from __future__ import annotations

import csv
import io
import json
import os
from typing import Any

from agent.logger import logger
from agent.models import ToolResult


class FileTool:

    BASE_DIR = os.path.join(os.getcwd(), "workspace_files")

    def __init__(self) -> None:
        os.makedirs(self.BASE_DIR, exist_ok=True)

    def _safe_path(self, filename: str) -> str:
        """Resolve and sandbox to BASE_DIR."""
        full = os.path.realpath(os.path.join(self.BASE_DIR, filename))
        if not full.startswith(os.path.realpath(self.BASE_DIR)):
            raise ValueError(f"Path traversal attempt blocked: {filename}")
        return full

    # ------------------------------------------------------------------
    def read(self, filename: str) -> ToolResult:
        logger.info(f"[File] read ← {filename}")
        try:
            path = self._safe_path(filename)
            if not os.path.exists(path):
                return ToolResult(success=False, error=f"File not found: {filename}")
            ext = os.path.splitext(filename)[1].lower()
            if ext == ".json":
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                return ToolResult(success=True, output=data)
            elif ext == ".csv":
                with open(path, "r", encoding="utf-8", newline="") as f:
                    reader = csv.DictReader(f)
                    rows = list(reader)
                return ToolResult(success=True, output=rows)
            else:
                with open(path, "r", encoding="utf-8") as f:
                    text = f.read()
                return ToolResult(success=True, output=text)
        except Exception as e:
            logger.error(f"[File] read error: {e}")
            return ToolResult(success=False, error=str(e))

    def write(self, filename: str, content: Any) -> ToolResult:
        logger.info(f"[File] write → {filename}")
        try:
            path = self._safe_path(filename)
            os.makedirs(os.path.dirname(path), exist_ok=True)
            ext = os.path.splitext(filename)[1].lower()
            if ext == ".json":
                with open(path, "w", encoding="utf-8") as f:
                    json.dump(content, f, indent=2, default=str)
            elif ext == ".csv" and isinstance(content, list) and content:
                with open(path, "w", encoding="utf-8", newline="") as f:
                    writer = csv.DictWriter(f, fieldnames=content[0].keys())
                    writer.writeheader()
                    writer.writerows(content)
            else:
                with open(path, "w", encoding="utf-8") as f:
                    f.write(str(content))
            return ToolResult(success=True, output={"path": path})
        except Exception as e:
            logger.error(f"[File] write error: {e}")
            return ToolResult(success=False, error=str(e))

    def list_files(self) -> ToolResult:
        try:
            files = os.listdir(self.BASE_DIR)
            return ToolResult(success=True, output=files)
        except Exception as e:
            return ToolResult(success=False, error=str(e))

    def delete(self, filename: str) -> ToolResult:
        logger.info(f"[File] delete → {filename}")
        try:
            path = self._safe_path(filename)
            if os.path.exists(path):
                os.remove(path)
                return ToolResult(success=True, output={"deleted": filename})
            return ToolResult(success=False, error=f"File not found: {filename}")
        except Exception as e:
            return ToolResult(success=False, error=str(e))

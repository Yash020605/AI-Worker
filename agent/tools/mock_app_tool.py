"""
Mock App Tool — talks to the simulated company application
running at localhost:8001.

This abstracts the internal company system so the agent doesn't
need to do raw HTTP — it just calls high-level methods.
"""
from __future__ import annotations

from typing import Any, Optional

from agent.config import config
from agent.logger import logger
from agent.models import ToolResult
from agent.tools.api_tool import ApiTool


class MockAppTool:

    def __init__(self) -> None:
        self._api = ApiTool(base_url=f"http://localhost:{config.MOCK_APP_PORT}")

    # ------------------------------------------------------------------
    # Invoices
    # ------------------------------------------------------------------

    async def list_invoices(self, company: Optional[str] = None) -> ToolResult:
        """List all invoices, optionally filtered by company name."""
        logger.info(f"[MockApp] list_invoices company={company!r}")
        params = {"company": company} if company else None
        return await self._api.get("/api/invoices", params=params)

    async def get_invoice(self, invoice_id: str) -> ToolResult:
        logger.info(f"[MockApp] get_invoice id={invoice_id!r}")
        return await self._api.get(f"/api/invoices/{invoice_id}")

    async def create_invoice(self, data: dict[str, Any]) -> ToolResult:
        logger.info(f"[MockApp] create_invoice data={data}")
        return await self._api.post("/api/invoices", payload=data)

    async def update_invoice(self, invoice_id: str, data: dict[str, Any]) -> ToolResult:
        logger.info(f"[MockApp] update_invoice id={invoice_id!r}")
        return await self._api.put(f"/api/invoices/{invoice_id}", payload=data)

    # ------------------------------------------------------------------
    # Vendors / Contacts
    # ------------------------------------------------------------------

    async def list_vendors(self) -> ToolResult:
        return await self._api.get("/api/vendors")

    async def get_vendor(self, vendor_id: str) -> ToolResult:
        return await self._api.get(f"/api/vendors/{vendor_id}")

    # ------------------------------------------------------------------
    # Payments
    # ------------------------------------------------------------------

    async def record_payment(self, data: dict[str, Any]) -> ToolResult:
        logger.info(f"[MockApp] record_payment data={data}")
        return await self._api.post("/api/payments", payload=data)

    async def list_payments(self) -> ToolResult:
        return await self._api.get("/api/payments")

    # ------------------------------------------------------------------
    # Tasks / Work items
    # ------------------------------------------------------------------

    async def create_task(self, data: dict[str, Any]) -> ToolResult:
        return await self._api.post("/api/tasks", payload=data)

    async def list_tasks(self) -> ToolResult:
        return await self._api.get("/api/tasks")

    # ------------------------------------------------------------------
    # Generic read/write for extensibility
    # ------------------------------------------------------------------

    async def read(self, resource: str, resource_id: Optional[str] = None) -> ToolResult:
        endpoint = f"/api/{resource}"
        if resource_id:
            endpoint += f"/{resource_id}"
        return await self._api.get(endpoint)

    async def write(self, resource: str, data: dict[str, Any], resource_id: Optional[str] = None) -> ToolResult:
        if resource_id:
            return await self._api.put(f"/api/{resource}/{resource_id}", payload=data)
        return await self._api.post(f"/api/{resource}", payload=data)

"""
API tool — makes HTTP requests to external or internal REST APIs.
Includes retry logic with exponential backoff via tenacity.
"""
from __future__ import annotations

import json
from typing import Any, Optional

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from agent.logger import logger
from agent.models import ToolResult


class ApiTool:

    def __init__(self, base_url: str = "", default_headers: Optional[dict] = None) -> None:
        self.base_url = base_url.rstrip("/")
        self.default_headers = default_headers or {"Content-Type": "application/json"}

    # ------------------------------------------------------------------
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=8),
        retry=retry_if_exception_type((httpx.TimeoutException, httpx.ConnectError)),
        reraise=True,
    )
    async def get(
        self,
        endpoint: str,
        params: Optional[dict] = None,
        headers: Optional[dict] = None,
    ) -> ToolResult:
        url = self._url(endpoint)
        logger.info(f"[API] GET {url} params={params}")
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.get(url, params=params, headers={**self.default_headers, **(headers or {})})
                return self._parse(resp)
        except Exception as e:
            logger.error(f"[API] GET error: {e}")
            return ToolResult(success=False, error=str(e))

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=8),
        retry=retry_if_exception_type((httpx.TimeoutException, httpx.ConnectError)),
        reraise=True,
    )
    async def post(
        self,
        endpoint: str,
        payload: Optional[dict] = None,
        headers: Optional[dict] = None,
    ) -> ToolResult:
        url = self._url(endpoint)
        logger.info(f"[API] POST {url} payload={payload}")
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.post(
                    url,
                    json=payload,
                    headers={**self.default_headers, **(headers or {})},
                )
                return self._parse(resp)
        except Exception as e:
            logger.error(f"[API] POST error: {e}")
            return ToolResult(success=False, error=str(e))

    async def put(
        self,
        endpoint: str,
        payload: Optional[dict] = None,
        headers: Optional[dict] = None,
    ) -> ToolResult:
        url = self._url(endpoint)
        logger.info(f"[API] PUT {url}")
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.put(
                    url,
                    json=payload,
                    headers={**self.default_headers, **(headers or {})},
                )
                return self._parse(resp)
        except Exception as e:
            logger.error(f"[API] PUT error: {e}")
            return ToolResult(success=False, error=str(e))

    # ------------------------------------------------------------------
    def _url(self, endpoint: str) -> str:
        if endpoint.startswith("http://") or endpoint.startswith("https://"):
            return endpoint
        return f"{self.base_url}/{endpoint.lstrip('/')}"

    def _parse(self, resp: httpx.Response) -> ToolResult:
        success = 200 <= resp.status_code < 300
        try:
            data = resp.json()
        except Exception:
            data = resp.text
        if not success:
            return ToolResult(
                success=False,
                output=data,
                error=f"HTTP {resp.status_code}",
                metadata={"status_code": resp.status_code},
            )
        return ToolResult(
            success=True,
            output=data,
            metadata={"status_code": resp.status_code},
        )

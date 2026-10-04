"""
Browser tool — wraps Playwright for headless browser automation.

Capabilities:
  • navigate(url)
  • click(selector)
  • type_text(selector, text)
  • extract_text(selector)
  • extract_table(selector)
  • screenshot(path)
  • get_page_text()
  • fill_form(field_map)
"""
from __future__ import annotations

import asyncio
import os
from typing import Any, Optional

from agent.config import config
from agent.logger import logger
from agent.models import ToolResult


class BrowserTool:
    """
    Async Playwright wrapper.
    Call `await tool.start()` before use, `await tool.stop()` when done.
    """

    def __init__(self) -> None:
        self._playwright = None
        self._browser = None
        self._page = None
        self._started = False

    async def start(self) -> None:
        if self._started:
            return
        try:
            from playwright.async_api import async_playwright
            self._playwright = await async_playwright().start()
            self._browser = await self._playwright.chromium.launch(
                headless=config.BROWSER_HEADLESS,
                args=["--no-sandbox", "--disable-dev-shm-usage"],
            )
            self._page = await self._browser.new_page()
            self._page.set_default_timeout(config.BROWSER_TIMEOUT)
            self._started = True
            logger.info("[Browser] Started")
        except Exception as e:
            logger.error(f"[Browser] Failed to start: {e}")
            raise

    async def stop(self) -> None:
        if not self._started:
            return
        try:
            await self._browser.close()
            await self._playwright.stop()
            self._started = False
            logger.info("[Browser] Stopped")
        except Exception as e:
            logger.warning(f"[Browser] Error during stop: {e}")

    # ------------------------------------------------------------------
    # Core actions
    # ------------------------------------------------------------------

    async def navigate(self, url: str) -> ToolResult:
        logger.info(f"[Browser] navigate → {url}")
        try:
            await self._ensure_started()
            response = await self._page.goto(url, wait_until="domcontentloaded")
            status = response.status if response else 0
            title = await self._page.title()
            return ToolResult(
                success=True,
                output={"url": url, "status": status, "title": title},
            )
        except Exception as e:
            logger.error(f"[Browser] navigate error: {e}")
            return ToolResult(success=False, error=str(e))

    async def click(self, selector: str) -> ToolResult:
        logger.info(f"[Browser] click → {selector!r}")
        try:
            await self._ensure_started()
            await self._page.click(selector)
            return ToolResult(success=True, output={"clicked": selector})
        except Exception as e:
            logger.error(f"[Browser] click error: {e}")
            return ToolResult(success=False, error=str(e))

    async def type_text(self, selector: str, text: str, clear_first: bool = True) -> ToolResult:
        logger.info(f"[Browser] type → {selector!r} = {text!r}")
        try:
            await self._ensure_started()
            if clear_first:
                await self._page.fill(selector, "")
            await self._page.type(selector, text)
            return ToolResult(success=True, output={"typed": text})
        except Exception as e:
            logger.error(f"[Browser] type error: {e}")
            return ToolResult(success=False, error=str(e))

    async def extract_text(self, selector: str = "body") -> ToolResult:
        logger.info(f"[Browser] extract_text ← {selector!r}")
        try:
            await self._ensure_started()
            element = await self._page.query_selector(selector)
            if element is None:
                return ToolResult(success=False, error=f"Selector not found: {selector}")
            text = await element.inner_text()
            return ToolResult(success=True, output={"text": text})
        except Exception as e:
            logger.error(f"[Browser] extract_text error: {e}")
            return ToolResult(success=False, error=str(e))

    async def extract_table(self, selector: str = "table") -> ToolResult:
        """Extract an HTML table as a list of dicts."""
        logger.info(f"[Browser] extract_table ← {selector!r}")
        try:
            await self._ensure_started()
            rows = await self._page.eval_on_selector_all(
                f"{selector} tr",
                """rows => rows.map(row =>
                    Array.from(row.querySelectorAll('th,td')).map(c => c.innerText.trim())
                )"""
            )
            if not rows:
                return ToolResult(success=False, error="No table rows found")
            headers = rows[0]
            data = [dict(zip(headers, row)) for row in rows[1:] if row]
            return ToolResult(success=True, output={"headers": headers, "rows": data})
        except Exception as e:
            logger.error(f"[Browser] extract_table error: {e}")
            return ToolResult(success=False, error=str(e))

    async def get_page_text(self) -> ToolResult:
        logger.info("[Browser] get_page_text")
        try:
            await self._ensure_started()
            text = await self._page.inner_text("body")
            url = self._page.url
            title = await self._page.title()
            return ToolResult(success=True, output={"text": text, "url": url, "title": title})
        except Exception as e:
            logger.error(f"[Browser] get_page_text error: {e}")
            return ToolResult(success=False, error=str(e))

    async def screenshot(self, path: str = "screenshots/screenshot.png") -> ToolResult:
        logger.info(f"[Browser] screenshot → {path}")
        try:
            await self._ensure_started()
            os.makedirs(os.path.dirname(path) if os.path.dirname(path) else ".", exist_ok=True)
            await self._page.screenshot(path=path, full_page=True)
            return ToolResult(success=True, output={"path": path})
        except Exception as e:
            logger.error(f"[Browser] screenshot error: {e}")
            return ToolResult(success=False, error=str(e))

    async def fill_form(self, field_map: dict[str, str]) -> ToolResult:
        """Fill multiple form fields. field_map: {selector: value}"""
        logger.info(f"[Browser] fill_form {list(field_map.keys())}")
        results = {}
        errors = []
        try:
            await self._ensure_started()
            for selector, value in field_map.items():
                try:
                    await self._page.fill(selector, value)
                    results[selector] = "filled"
                except Exception as e:
                    errors.append(f"{selector}: {e}")
                    results[selector] = f"error: {e}"
            success = len(errors) == 0
            return ToolResult(success=success, output=results, error="; ".join(errors) if errors else None)
        except Exception as e:
            return ToolResult(success=False, error=str(e))

    async def wait_for_selector(self, selector: str, timeout: int = 5000) -> ToolResult:
        try:
            await self._ensure_started()
            await self._page.wait_for_selector(selector, timeout=timeout)
            return ToolResult(success=True, output={"found": selector})
        except Exception as e:
            return ToolResult(success=False, error=str(e))

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _ensure_started(self) -> None:
        if not self._started:
            await self.start()

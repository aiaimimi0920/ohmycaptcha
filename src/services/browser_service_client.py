"""HTTP adapter for delegating browser resource leasing to BrowserService/EasyBrowser."""

from __future__ import annotations

import asyncio
import logging
import uuid
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Any, AsyncIterator

import httpx
from playwright.async_api import Browser, BrowserContext, Page, Playwright, async_playwright

from ..core.config import Config

log = logging.getLogger(__name__)


@dataclass
class BrowserServiceLease:
    provider_id: str
    runtime_id: str
    task_id: str
    resource_id: str | None
    debug_port: int
    metadata: dict[str, Any]
    result: dict[str, Any]

    @property
    def cdp_url(self) -> str:
        return f"http://127.0.0.1:{self.debug_port}"


@dataclass
class AttachedBrowserPage:
    lease: BrowserServiceLease
    playwright: Playwright
    browser: Browser
    context: BrowserContext
    page: Page


class BrowserServiceClient:
    """HTTP client for the EasyBrowser public API."""

    def __init__(self, config: Config) -> None:
        self._config = config
        self._enabled = (
            config.browser_backend == "browserservice"
            and bool(config.browser_service_base_url)
        )

    @property
    def enabled(self) -> bool:
        return self._enabled

    async def solve(self, operation_kind: str, payload: dict[str, Any]) -> dict[str, Any]:
        if not self.enabled or not self._config.browser_service_base_url:
            raise RuntimeError("BrowserService adapter is not enabled")

        headers = self._build_headers()
        execute_body = self._build_execute_request(operation_kind, payload)

        async with httpx.AsyncClient(
            timeout=httpx.Timeout(float(self._config.browser_service_timeout)),
            trust_env=False,
        ) as client:
            task_id = await self._submit_execute(client, headers, execute_body)
            data = await self._poll_task_data(client, task_id, headers)
            return self._extract_result_payload(data)

    async def acquire_page_lease(self, url: str = "about:blank") -> BrowserServiceLease:
        if not self.enabled or not self._config.browser_service_base_url:
            raise RuntimeError("BrowserService adapter is not enabled")

        headers = self._build_headers()
        execute_body = self._build_execute_request(
            "open_page",
            {
                "action": "open_page",
                "resource_kind": "page",
                "url": url,
            },
        )

        async with httpx.AsyncClient(
            timeout=httpx.Timeout(float(self._config.browser_service_timeout)),
            trust_env=False,
        ) as client:
            task_id = await self._submit_execute(client, headers, execute_body)
            data = await self._poll_task_data(client, task_id, headers)
            return self._extract_lease(data)

    async def close_page_lease(self, lease: BrowserServiceLease) -> None:
        if not self.enabled or not self._config.browser_service_base_url:
            return
        if not lease.resource_id:
            return

        headers = self._build_headers()
        execute_body = self._build_execute_request(
            "close_resource",
            {
                "action": "close_resource",
                "resource_kind": "page",
                "resource_id": lease.resource_id,
            },
            runtime_id=lease.runtime_id,
            provider=lease.provider_id,
        )

        try:
            async with httpx.AsyncClient(
                timeout=httpx.Timeout(float(self._config.browser_service_timeout)),
                trust_env=False,
            ) as client:
                task_id = await self._submit_execute(client, headers, execute_body)
                await self._poll_task_data(client, task_id, headers)
        except Exception as exc:
            log.warning(
                "BrowserService failed to close leased page resource=%s runtime=%s: %s",
                lease.resource_id,
                lease.runtime_id,
                exc,
            )

    @asynccontextmanager
    async def open_attached_page(self, url: str = "about:blank") -> AsyncIterator[AttachedBrowserPage]:
        lease = await self.acquire_page_lease(url)
        playwright = await async_playwright().start()
        browser: Browser | None = None
        page: Page | None = None
        context: BrowserContext | None = None
        try:
            browser = await playwright.chromium.connect_over_cdp(lease.cdp_url)
            context, page = await self._resolve_leased_page(browser, lease)
            yield AttachedBrowserPage(
                lease=lease,
                playwright=playwright,
                browser=browser,
                context=context,
                page=page,
            )
        finally:
            if browser is not None:
                try:
                    await browser.close()
                except Exception:
                    pass
            try:
                await playwright.stop()
            except Exception:
                pass
            await self.close_page_lease(lease)

    async def _resolve_leased_page(
        self,
        browser: Browser,
        lease: BrowserServiceLease,
    ) -> tuple[BrowserContext, Page]:
        candidate_url = self._extract_lease_url(lease)
        if lease.resource_id:
            for context in browser.contexts:
                for page in context.pages:
                    if await self._page_matches_resource_id(context, page, lease.resource_id):
                        return context, page

        for context in browser.contexts:
            for page in context.pages:
                if candidate_url and page.url == candidate_url:
                    return context, page

        context = browser.contexts[0] if browser.contexts else await browser.new_context()
        page = await context.new_page()
        return context, page

    async def _page_matches_resource_id(
        self,
        context: BrowserContext,
        page: Page,
        resource_id: str,
    ) -> bool:
        try:
            session = await context.new_cdp_session(page)
            info = await session.send("Target.getTargetInfo")
            target_info = info.get("targetInfo") if isinstance(info, dict) else None
            target_id = (
                target_info.get("targetId")
                if isinstance(target_info, dict)
                else None
            )
            return bool(target_id and str(target_id) == resource_id)
        except Exception:
            return False

    def _extract_lease_url(self, lease: BrowserServiceLease) -> str | None:
        resource = lease.result.get("resource")
        if isinstance(resource, dict):
            url = resource.get("url")
            if isinstance(url, str) and url:
                return url

        provider_response = lease.result.get("provider_response")
        if isinstance(provider_response, dict):
            url = provider_response.get("url")
            if isinstance(url, str) and url:
                return url

        return None

    def _build_headers(self) -> dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self._config.browser_service_api_key:
            headers["Authorization"] = f"Bearer {self._config.browser_service_api_key}"
        return headers

    def _build_execute_request(
        self,
        operation_kind: str,
        payload: dict[str, Any],
        *,
        runtime_id: str | None = None,
        provider: str | None = None,
    ) -> dict[str, Any]:
        target = self._build_target(runtime_id=runtime_id, provider=provider)
        return {
            "request_id": str(uuid.uuid4()),
            "mode": "direct" if target.get("provider") else "strategy",
            "target": target,
            "operation": {
                "kind": operation_kind,
                "payload": payload,
            },
            "timeout": {
                "total_ms": self._config.browser_service_timeout * 1000,
                "startup_ms": min(self._config.browser_service_timeout, 30) * 1000,
            },
            "retry": {
                "allow_retry": True,
                "max_attempts": max(self._config.captcha_retries, 1),
            },
            "isolation": {
                "require_separate_process": True,
                "runtime_reuse": "prefer_reuse",
            },
            "metadata": {
                "caller": "ohmycaptcha",
                "tags": ["browser-session", operation_kind],
            },
        }

    def _build_target(
        self,
        *,
        runtime_id: str | None = None,
        provider: str | None = None,
    ) -> dict[str, Any]:
        target: dict[str, Any] = {}
        chosen_provider = provider or self._config.browser_service_provider
        if chosen_provider:
            target["provider"] = chosen_provider
        elif self._config.browser_service_allowed_providers:
            target["allowed_providers"] = list(self._config.browser_service_allowed_providers)
        if runtime_id:
            target["runtime_id"] = runtime_id
        return target

    async def _submit_execute(
        self,
        client: httpx.AsyncClient,
        headers: dict[str, str],
        execute_body: dict[str, Any],
    ) -> str:
        submit_response = await client.post(
            f"{self._config.browser_service_base_url.rstrip('/')}/v1/execute",
            headers=headers,
            json=execute_body,
        )
        submit_response.raise_for_status()
        submit_payload = submit_response.json()
        if not submit_payload.get("success"):
            raise RuntimeError(
                f"BrowserService rejected task: {submit_payload.get('message') or submit_payload}"
            )

        task_id = (
            submit_payload.get("data", {}).get("task_id")
            or submit_payload.get("trace", {}).get("task_id")
        )
        if not task_id:
            raise RuntimeError(f"BrowserService did not return task_id: {submit_payload}")
        return str(task_id)

    async def _poll_task_data(
        self,
        client: httpx.AsyncClient,
        task_id: str,
        headers: dict[str, str],
    ) -> dict[str, Any]:
        status_url = f"{self._config.browser_service_base_url.rstrip('/')}/v1/tasks/{task_id}"
        total_attempts = max(self._config.browser_service_timeout // 2, 10)

        last_payload: dict[str, Any] | None = None
        for _ in range(total_attempts):
            response = await client.get(status_url, headers=headers)
            response.raise_for_status()
            payload = response.json()
            last_payload = payload

            if not payload.get("success"):
                raise RuntimeError(
                    f"BrowserService status polling failed: {payload.get('message') or payload}"
                )

            data = payload.get("data", {})
            state = str(data.get("state", "")).lower()
            if state in {"succeeded", "ready", "completed"}:
                return data

            if state in {"failed", "error", "cancelled"}:
                error = data.get("error") or {}
                raise RuntimeError(
                    error.get("message")
                    or payload.get("message")
                    or f"BrowserService task ended with state={state}"
                )

            await asyncio.sleep(2)

        raise RuntimeError(f"BrowserService task timed out: {last_payload}")

    def _extract_result_payload(self, data: dict[str, Any]) -> dict[str, Any]:
        result = data.get("result")
        if isinstance(result, dict):
            provider_response = result.get("provider_response")
            if isinstance(provider_response, dict) and str(result.get("action", "")).startswith("captcha."):
                merged = dict(provider_response)
                merged.setdefault("_easybrowser", result)
                return merged
            return result
        return {"result": result}

    def _extract_lease(self, data: dict[str, Any]) -> BrowserServiceLease:
        result = data.get("result")
        if not isinstance(result, dict):
            raise RuntimeError(f"BrowserService lease result is not an object: {data}")

        metadata = result.get("metadata")
        if not isinstance(metadata, dict):
            metadata = {}

        debug_port_raw = metadata.get("debug_port")
        if debug_port_raw is None:
            raise RuntimeError(f"BrowserService did not return debug_port metadata: {result}")

        try:
            debug_port = int(debug_port_raw)
        except (TypeError, ValueError) as exc:
            raise RuntimeError(f"BrowserService returned invalid debug_port={debug_port_raw!r}") from exc

        resource_id = (
            result.get("resource_id")
            or (result.get("resource") or {}).get("id")
        )
        route = data.get("route") or {}

        return BrowserServiceLease(
            provider_id=str(route.get("selected_provider") or result.get("provider_id") or ""),
            runtime_id=str(route.get("runtime_id") or result.get("runtime_id") or ""),
            task_id=str(data.get("task_id") or ""),
            resource_id=str(resource_id) if resource_id else None,
            debug_port=debug_port,
            metadata=metadata,
            result=result,
        )

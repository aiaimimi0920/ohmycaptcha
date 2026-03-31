"""HTTP adapter for delegating browser automation to BrowserService/EasyBrowser."""

from __future__ import annotations

import asyncio
import logging
import uuid
from typing import Any

import httpx

from ..core.config import Config

log = logging.getLogger(__name__)


class BrowserServiceClient:
    """Small HTTP client for the EasyBrowser public API."""

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

        execute_body = self._build_execute_request(operation_kind, payload)
        headers = self._build_headers()

        async with httpx.AsyncClient(
            timeout=httpx.Timeout(float(self._config.browser_service_timeout)),
            trust_env=False,
        ) as client:
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

            return await self._poll_result(client, task_id, headers)

    def _build_headers(self) -> dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self._config.browser_service_api_key:
            headers["Authorization"] = f"Bearer {self._config.browser_service_api_key}"
        return headers

    def _build_execute_request(self, operation_kind: str, payload: dict[str, Any]) -> dict[str, Any]:
        mode = "direct" if self._config.browser_service_provider else "strategy"
        target: dict[str, Any] = {}
        if self._config.browser_service_provider:
            target["provider"] = self._config.browser_service_provider
        elif self._config.browser_service_allowed_providers:
            target["allowed_providers"] = list(self._config.browser_service_allowed_providers)

        return {
            "request_id": str(uuid.uuid4()),
            "mode": mode,
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
                "tags": ["captcha", operation_kind],
            },
        }

    async def _poll_result(
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
                result = data.get("result")
                if isinstance(result, dict):
                    provider_response = result.get("provider_response")
                    if isinstance(provider_response, dict) and str(result.get("action", "")).startswith("captcha."):
                        merged = dict(provider_response)
                        merged.setdefault("_easybrowser", result)
                        return merged
                    return result
                return {"result": result}

            if state in {"failed", "error", "cancelled"}:
                error = data.get("error") or {}
                raise RuntimeError(
                    error.get("message")
                    or payload.get("message")
                    or f"BrowserService task ended with state={state}"
                )

            await asyncio.sleep(2)

        raise RuntimeError(f"BrowserService task timed out: {last_payload}")

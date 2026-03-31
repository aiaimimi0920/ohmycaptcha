"""Shared helpers for OpenAI-compatible endpoints, including XFYun MaaS."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import httpx
from openai import AsyncOpenAI

from ..core.config import Config


@dataclass(frozen=True)
class OpenAIEndpointConfig:
    base_url: str
    api_key: str
    model: str
    resource_id: str | None = None


def get_cloud_endpoint(config: Config) -> OpenAIEndpointConfig:
    return OpenAIEndpointConfig(
        base_url=config.cloud_base_url,
        api_key=config.cloud_api_key,
        model=config.cloud_model,
        resource_id=config.cloud_resource_id,
    )


def get_local_endpoint(config: Config) -> OpenAIEndpointConfig:
    return OpenAIEndpointConfig(
        base_url=config.local_base_url,
        api_key=config.local_api_key,
        model=config.local_model,
        resource_id=config.local_resource_id,
    )


def build_extra_headers(endpoint: OpenAIEndpointConfig) -> dict[str, str]:
    headers: dict[str, str] = {}
    if endpoint.resource_id:
        headers["lora_id"] = endpoint.resource_id
    return headers


def create_async_openai_client(endpoint: OpenAIEndpointConfig, timeout_seconds: int) -> AsyncOpenAI:
    default_headers = build_extra_headers(endpoint) or None
    return AsyncOpenAI(
        base_url=endpoint.base_url,
        api_key=endpoint.api_key,
        max_retries=0,
        default_headers=default_headers,
        http_client=httpx.AsyncClient(
            timeout=httpx.Timeout(float(timeout_seconds)),
            trust_env=False,
        ),
    )


def apply_chat_options(
    endpoint: OpenAIEndpointConfig,
    payload: dict[str, Any],
) -> dict[str, Any]:
    request_payload = dict(payload)
    request_payload.setdefault("model", endpoint.model)
    extra_headers = build_extra_headers(endpoint)
    if extra_headers and "extra_headers" not in request_payload:
        request_payload["extra_headers"] = extra_headers
    return request_payload

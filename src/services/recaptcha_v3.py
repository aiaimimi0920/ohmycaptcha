"""reCAPTCHA v3 solver using Playwright browser automation."""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

from playwright.async_api import Browser, Playwright, async_playwright

from ..core.config import Config
from .browser_service_client import BrowserServiceClient

log = logging.getLogger(__name__)
_RECAPTCHA_V3_TOKEN_ATTR = "data-easybrowser-recaptcha-v3-token"

# JS executed inside the browser to obtain a reCAPTCHA v3 token.
# Handles both standard and enterprise reCAPTCHA libraries.
_EXECUTE_JS = """
([key, action]) => new Promise((resolve, reject) => {
    const gr = window.grecaptcha?.enterprise || window.grecaptcha;
    if (gr && typeof gr.execute === 'function') {
        gr.ready(() => {
            gr.execute(key, {action}).then(resolve).catch(reject);
        });
        return;
    }
    // grecaptcha not loaded yet — inject the script ourselves
    const script = document.createElement('script');
    script.src = 'https://www.google.com/recaptcha/api.js?render=' + key;
    script.onerror = () => reject(new Error('Failed to load reCAPTCHA script'));
    script.onload = () => {
        const g = window.grecaptcha;
        if (!g) { reject(new Error('grecaptcha still undefined after script load')); return; }
        g.ready(() => {
            g.execute(key, {action}).then(resolve).catch(reject);
        });
    };
    document.head.appendChild(script);
})
"""

# Basic anti-detection init script
_STEALTH_JS = """
Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
Object.defineProperty(navigator, 'languages', {get: () => ['en-US', 'en']});
Object.defineProperty(navigator, 'plugins', {get: () => [1, 2, 3, 4, 5]});
window.chrome = {runtime: {}, loadTimes: () => {}, csi: () => {}};
"""


class RecaptchaV3Solver:
    """Solves RecaptchaV3TaskProxyless tasks via headless Chromium."""

    def __init__(self, config: Config) -> None:
        self._config = config
        self._playwright: Playwright | None = None
        self._browser: Browser | None = None
        self._browser_service = BrowserServiceClient(config)

    async def start(self) -> None:
        if self._browser_service.enabled:
            log.info("RecaptchaV3Solver using BrowserService backend")
            return
        log.info("RecaptchaV3Solver defers local browser startup until first solve")

    async def stop(self) -> None:
        if self._browser_service.enabled:
            log.info("RecaptchaV3Solver BrowserService backend requires no local browser stop")
            return
        if self._browser:
            await self._browser.close()
        if self._playwright:
            await self._playwright.stop()
        log.info("Playwright browser stopped")

    async def solve(self, params: dict[str, Any]) -> dict[str, Any]:
        if self._browser_service.enabled:
            website_url = params["websiteURL"]
            website_key = params["websiteKey"]
            page_action = params.get("pageAction", "verify")

            async with self._browser_service.open_attached_page(website_url) as attached:
                token = await self._solve_on_page(
                    attached.page, website_url, website_key, page_action
                )
                return {"gRecaptchaResponse": token}

        await self._ensure_browser()
        website_url = params["websiteURL"]
        website_key = params["websiteKey"]
        page_action = params.get("pageAction", "verify")

        last_error: Exception | None = None
        for attempt in range(self._config.captcha_retries):
            try:
                token = await self._solve_once(
                    website_url, website_key, page_action
                )
                return {"gRecaptchaResponse": token}
            except Exception as exc:
                last_error = exc
                log.warning(
                    "Attempt %d/%d failed for %s: %s",
                    attempt + 1,
                    self._config.captcha_retries,
                    website_url,
                    exc,
                )
                if attempt < self._config.captcha_retries - 1:
                    await asyncio.sleep(2)

        raise RuntimeError(
            f"Failed after {self._config.captcha_retries} attempts: {last_error}"
        )

    async def _solve_once(
        self, website_url: str, website_key: str, page_action: str
    ) -> str:
        assert self._browser is not None

        context = await self._browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/131.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1920, "height": 1080},
            locale="en-US",
        )

        page = await context.new_page()
        await page.add_init_script(_STEALTH_JS)

        try:
            return await self._solve_on_page(page, website_url, website_key, page_action)
        finally:
            await context.close()

    async def _solve_on_page(
        self, page: Any, website_url: str, website_key: str, page_action: str
    ) -> str:
        timeout_ms = self._config.browser_timeout * 1000
        if page.url != website_url:
            await page.goto(website_url, wait_until="networkidle", timeout=timeout_ms)
        else:
            await page.wait_for_load_state("networkidle", timeout=timeout_ms)

        # Simulate minimal human-like behaviour to improve score
        await page.mouse.move(400, 300)
        await asyncio.sleep(1)
        await page.mouse.move(600, 400)
        await asyncio.sleep(0.5)
        token = await self._execute_token(page, website_key, page_action)

        if not isinstance(token, str) or len(token) < 20:
            raise RuntimeError(f"Invalid token received: {token!r}")

        log.info(
            "Got reCAPTCHA token for %s (len=%d)", website_url, len(token)
        )
        return token

    async def _execute_token(
        self,
        page: Any,
        website_key: str,
        page_action: str,
    ) -> Any:
        if getattr(page, "_easybrowser_browser_name", "") != "firefox":
            return await page.evaluate(_EXECUTE_JS, [website_key, page_action])

        expression = (
            "mw:(() => {"
            f"const key = {json.dumps(website_key)};"
            f"const action = {json.dumps(page_action)};"
            f"const attrName = {json.dumps(_RECAPTCHA_V3_TOKEN_ATTR)};"
            "document.documentElement.removeAttribute(attrName);"
            "const write = (value) => { document.documentElement.setAttribute(attrName, String(value ?? '')); };"
            "const run = () => {"
            "const gr = window.grecaptcha?.enterprise || window.grecaptcha;"
            "if (!gr || typeof gr.execute !== 'function') { throw new Error('grecaptcha still undefined after script load'); }"
            "gr.ready(() => { gr.execute(key, {action}).then(write).catch((error) => write('ERROR:' + String(error))); });"
            "};"
            "try {"
            "const gr = window.grecaptcha?.enterprise || window.grecaptcha;"
            "if (gr && typeof gr.execute === 'function') { run(); return; }"
            "const script = document.createElement('script');"
            "script.src = 'https://www.google.com/recaptcha/api.js?render=' + key;"
            "script.onerror = () => write('ERROR:Failed to load reCAPTCHA script');"
            "script.onload = () => { try { run(); } catch (error) { write('ERROR:' + String(error)); } };"
            "document.head.appendChild(script);"
            "} catch (error) { write('ERROR:' + String(error)); }"
            "})()"
        )
        await page.evaluate(expression)

        for _ in range(40):
            await asyncio.sleep(0.25)
            token = await page.evaluate(
                "([attrName]) => document.documentElement.getAttribute(attrName)",
                [_RECAPTCHA_V3_TOKEN_ATTR],
            )
            if isinstance(token, str) and token.startswith("ERROR:"):
                raise RuntimeError(token[6:])
            if isinstance(token, str) and token:
                return token

        raise RuntimeError("Timed out waiting for reCAPTCHA v3 token from main-world bridge")

    async def _ensure_browser(self) -> None:
        if self._browser is not None:
            return
        self._playwright = await async_playwright().start()
        self._browser = await self._playwright.chromium.launch(
            headless=self._config.browser_headless,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-dev-shm-usage",
                "--disable-gpu",
            ],
        )
        log.info("Playwright browser started lazily (headless=%s)", self._config.browser_headless)

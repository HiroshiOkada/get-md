"""Playwright を利用した単発・バッチ向けの HTML 取得。"""

from __future__ import annotations

import asyncio
import warnings
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from time import perf_counter

from playwright.async_api import Browser, Page, async_playwright
from playwright.async_api import Error as PlaywrightError
from playwright.async_api import TimeoutError as PlaywrightTimeoutError

_DEFAULT_TIMEOUT = 30  # seconds
_WAIT_UNTIL_VALUES = ("domcontentloaded", "load", "networkidle", "commit")
_RESOURCE_TYPES = frozenset(
    {"document", "stylesheet", "image", "media", "font", "script", "xhr", "fetch", "websocket"}
)
_DEFAULT_BLOCKED_RESOURCES = frozenset({"font", "media"})
_SCREENSHOT_RESOURCES = frozenset({"stylesheet", "image", "media", "font"})


class NavigationTimeoutWarning(UserWarning):
    """Navigation timed out, but a partial DOM was available."""


@dataclass(frozen=True)
class FetchMetrics:
    """ブラウザ起動時間と1ページの navigation 時間。"""

    browser_launch_seconds: float
    navigation_seconds: float


@dataclass(frozen=True)
class FetchRequest:
    """バッチ内の URL と、その URL 固有の出力指定。"""

    url: str
    screenshot_path: str | Path | None = None


@dataclass(frozen=True)
class FetchResult:
    """入力順を維持して返す、URL単位の取得結果。"""

    url: str
    html: str | None = None
    error: Exception | None = None


def fetch(
    url: str,
    *,
    wait: float = 0.0,
    timeout: int = _DEFAULT_TIMEOUT,
    screenshot_path: str | Path | None = None,
    wait_until: str = "domcontentloaded",
    wait_for_selector: str | None = None,
    block_resources: frozenset[str] = _DEFAULT_BLOCKED_RESOURCES,
    strict: bool = False,
    metrics_callback: Callable[[FetchMetrics], None] | None = None,
) -> str:
    """単一URLを取得する後方互換な同期API。"""
    results = asyncio.run(
        fetch_many(
            [FetchRequest(url, screenshot_path)],
            concurrency=1,
            wait=wait,
            timeout=timeout,
            wait_until=wait_until,
            wait_for_selector=wait_for_selector,
            block_resources=block_resources,
            strict=strict,
            metrics_callback=metrics_callback,
        )
    )
    result = results[0]
    if result.error is not None:
        raise result.error
    assert result.html is not None
    return result.html


async def fetch_many(
    requests: Sequence[FetchRequest],
    *,
    concurrency: int = 4,
    wait: float = 0.0,
    timeout: int = _DEFAULT_TIMEOUT,
    wait_until: str = "domcontentloaded",
    wait_for_selector: str | None = None,
    block_resources: frozenset[str] = _DEFAULT_BLOCKED_RESOURCES,
    strict: bool = False,
    metrics_callback: Callable[[FetchMetrics], None] | None = None,
) -> list[FetchResult]:
    """1つのChromiumを再利用して複数URLを並行取得する。

    個々の取得失敗は ``FetchResult.error`` に格納し、他のURLの処理を継続する。
    ``asyncio.gather`` の結果順により、返り値は常に入力順となる。
    """
    if concurrency < 1:
        raise ValueError("concurrency must be at least 1")
    if not requests:
        return []

    async with async_playwright() as playwright:
        launch_started = perf_counter()
        browser = await playwright.chromium.launch(headless=True)
        launch_seconds = perf_counter() - launch_started
        semaphore = asyncio.Semaphore(concurrency)

        async def run(request: FetchRequest) -> FetchResult:
            async with semaphore:
                try:
                    html = await _fetch_page(
                        browser,
                        request,
                        wait=wait,
                        timeout=timeout,
                        wait_until=wait_until,
                        wait_for_selector=wait_for_selector,
                        block_resources=block_resources,
                        strict=strict,
                        browser_launch_seconds=launch_seconds,
                        metrics_callback=metrics_callback,
                    )
                    return FetchResult(request.url, html=html)
                except (PlaywrightError, OSError) as exc:
                    return FetchResult(request.url, error=exc)

        try:
            return list(await asyncio.gather(*(run(request) for request in requests)))
        finally:
            await browser.close()


async def _fetch_page(
    browser: Browser,
    request: FetchRequest,
    *,
    wait: float,
    timeout: int,
    wait_until: str,
    wait_for_selector: str | None,
    block_resources: frozenset[str],
    strict: bool,
    browser_launch_seconds: float,
    metrics_callback: Callable[[FetchMetrics], None] | None,
) -> str:
    page = await browser.new_page()
    try:
        blocked = block_resources
        if request.screenshot_path is not None:
            blocked = blocked - _SCREENSHOT_RESOURCES
        if blocked:
            await page.route(
                "**/*",
                lambda route: route.abort()
                if route.request.resource_type in blocked
                else route.continue_(),
            )

        navigation_complete = True
        navigation_started = perf_counter()
        try:
            await page.goto(request.url, timeout=int(timeout * 1000), wait_until=wait_until)
        except PlaywrightTimeoutError:
            if strict:
                raise
            navigation_complete = False
            warnings.warn(
                "navigation timed out; using the DOM received so far",
                NavigationTimeoutWarning,
                stacklevel=2,
            )
        navigation_seconds = perf_counter() - navigation_started
        if metrics_callback is not None:
            metrics_callback(FetchMetrics(browser_launch_seconds, navigation_seconds))
        if navigation_complete:
            if wait_for_selector is not None:
                await page.wait_for_selector(wait_for_selector, timeout=int(timeout * 1000))
            else:
                await _wait_for_stable_body(page)
        if wait > 0:
            await page.wait_for_timeout(int(wait * 1000))
        if request.screenshot_path is not None:
            await page.screenshot(path=str(request.screenshot_path), full_page=True)
        return await page.content()
    finally:
        await page.close()


async def _wait_for_stable_body(page: Page, *, timeout_ms: int = 1000) -> None:
    """短い上限内で本文の文字量が安定するまで待つ。"""
    try:
        await page.wait_for_function(
            """() => {
                const body = document.body;
                if (!body) return false;
                const length = body.innerText.length;
                const previous = window.__getMdPreviousBodyLength;
                window.__getMdPreviousBodyLength = length;
                return previous === length;
            }""",
            timeout=timeout_ms,
            polling=100,
        )
    except PlaywrightTimeoutError:
        pass


__all__ = [
    "fetch",
    "fetch_many",
    "FetchMetrics",
    "FetchRequest",
    "FetchResult",
    "NavigationTimeoutWarning",
    "PlaywrightError",
    "_RESOURCE_TYPES",
    "_WAIT_UNTIL_VALUES",
]

"""Playwright-based fetching of rendered HTML with optional screenshot."""

from __future__ import annotations

import warnings
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from time import perf_counter

from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import sync_playwright

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
    """単発取得のブラウザ起動時間と navigation 時間。"""

    browser_launch_seconds: float
    navigation_seconds: float


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
    """Render ``url`` with a headless Chromium and return its HTML.

    Parameters
    ----------
    url:
        Page URL to load.
    wait:
        Extra seconds to wait after navigation for late JavaScript rendering.
    timeout:
        Navigation timeout in seconds.
    screenshot_path:
        When provided, a full-page PNG screenshot is saved there.
    wait_until:
        Playwright navigation lifecycle event to await.
    wait_for_selector:
        Optional selector that must become visible after navigation.
    block_resources:
        Playwright resource types to abort. Display resources are always allowed
        when taking a screenshot.
    strict:
        Raise a navigation timeout instead of returning the partial DOM.
    metrics_callback:
        Optional callback receiving browser launch and navigation durations.
    """
    with sync_playwright() as p:
        launch_started = perf_counter()
        browser = p.chromium.launch(headless=True)
        browser_launch_seconds = perf_counter() - launch_started
        try:
            page = browser.new_page()
            blocked = block_resources
            if screenshot_path is not None:
                blocked = blocked - _SCREENSHOT_RESOURCES
            if blocked:
                page.route(
                    "**/*",
                    lambda route: route.abort()
                    if route.request.resource_type in blocked
                    else route.continue_(),
                )
            navigation_complete = True
            navigation_started = perf_counter()
            try:
                page.goto(url, timeout=int(timeout * 1000), wait_until=wait_until)
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
                    page.wait_for_selector(wait_for_selector, timeout=int(timeout * 1000))
                else:
                    _wait_for_stable_body(page)
            if wait > 0:
                page.wait_for_timeout(int(wait * 1000))
            if screenshot_path is not None:
                page.screenshot(path=str(screenshot_path), full_page=True)
            html = page.content()
        finally:
            browser.close()
    return html


def _wait_for_stable_body(page: object, *, timeout_ms: int = 1000) -> None:
    """短い上限内で本文の文字量が安定するまで待つ。"""
    try:
        page.wait_for_function(
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
    "FetchMetrics",
    "NavigationTimeoutWarning",
    "PlaywrightError",
    "_RESOURCE_TYPES",
    "_WAIT_UNTIL_VALUES",
]

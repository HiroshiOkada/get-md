"""Playwright-based fetching of rendered HTML with optional screenshot."""

from __future__ import annotations

from pathlib import Path

from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import sync_playwright

_DEFAULT_TIMEOUT = 30  # seconds


def fetch(
    url: str,
    *,
    wait: float = 0.0,
    timeout: int = _DEFAULT_TIMEOUT,
    screenshot_path: str | Path | None = None,
) -> str:
    """Render ``url`` with a headless Chromium and return its HTML.

    Parameters
    ----------
    url:
        Page URL to load.
    wait:
        Extra seconds to wait after ``load`` for late JavaScript rendering.
    timeout:
        Navigation timeout in seconds.
    screenshot_path:
        When provided, a full-page PNG screenshot is saved there.
    """
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        try:
            page = browser.new_page()
            page.goto(url, timeout=int(timeout * 1000))
            if wait > 0:
                page.wait_for_timeout(int(wait * 1000))
            if screenshot_path is not None:
                page.screenshot(path=str(screenshot_path), full_page=True)
            html = page.content()
        finally:
            browser.close()
    return html


__all__ = ["fetch", "PlaywrightError"]

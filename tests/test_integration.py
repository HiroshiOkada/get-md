from __future__ import annotations

import asyncio
import os
import re
import subprocess
import sys
import threading
import time
from collections.abc import Iterator
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError

from get_md.fetcher import (
    FetchMetrics,
    FetchRequest,
    NavigationTimeoutWarning,
    fetch,
    fetch_many,
)

_YOUTUBE_LIVE_URL = "https://www.youtube.com/@OpenAI/videos"
_YOUTUBE_VIEW_COUNT = re.compile(
    r"(?:[\d,.]+\s*[KMB]?\s+views?|[\d,.]+\s*万?\s*回視聴)", re.I
)
_YOUTUBE_RELATIVE_AGE = re.compile(
    r"(?:\d+\s+(?:minutes?|hours?|days?|weeks?|months?|years?)\s+ago|\d+\s*(?:分|時間|日|週間|か月|年)前)",
    re.I,
)
_YOUTUBE_VIDEO_LINK = re.compile(
    r"\[([^\]\n]{2,})\]\(https://www\.youtube\.com/watch\?v=([A-Za-z0-9_-]{11})"
)
_MINIMUM_MEANINGFUL_VIDEOS = 3

_PAGE = b"""<!doctype html>
<html lang="en">
<head><title>Local integration page</title></head>
<body>
  <header>Site navigation outside the article</header>
  <main id="content">
    <h1>Local integration article</h1>
    <p>This server-rendered paragraph has enough detail for conservative DOM extraction.</p>
    <a href="/guide">Local guide</a>
  </main>
  <script>document.querySelector('#content').insertAdjacentHTML(
    'beforeend', '<p id="rendered">Rendered by JavaScript.</p>'
  );</script>
</body>
</html>
"""

_NETWORK_PAGE = b"""<!doctype html><html><body><main>Partial content is ready.</main>
<script>fetch('/slow')</script></body></html>"""
_ASSET_PAGE = b"""<!doctype html><html><body><main>Asset page.</main>
<img src="/pixel.png" alt="pixel"></body></html>"""
_PNG = bytes.fromhex("89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c489")


class _Handler(BaseHTTPRequestHandler):
    requested_paths: list[str] = []
    active_requests = 0
    max_active_requests = 0
    activity_lock = threading.Lock()

    def do_GET(self) -> None:  # noqa: N802
        self.requested_paths.append(self.path)
        if self.path.startswith("/batch/"):
            with self.activity_lock:
                type(self).active_requests += 1
                type(self).max_active_requests = max(
                    type(self).max_active_requests, type(self).active_requests
                )
            time.sleep(0.3)
            body = f"<html><body><h1>{self.path}</h1></body></html>".encode()
            content_type = "text/html; charset=utf-8"
            with self.activity_lock:
                type(self).active_requests -= 1
        elif self.path == "/slow":
            time.sleep(2)
            body = b"done"
            content_type = "text/plain"
        elif self.path == "/network":
            body = _NETWORK_PAGE
            content_type = "text/html; charset=utf-8"
        elif self.path == "/assets":
            body = _ASSET_PAGE
            content_type = "text/html; charset=utf-8"
        elif self.path == "/pixel.png":
            body = _PNG
            content_type = "image/png"
        else:
            body = _PAGE
            content_type = "text/html; charset=utf-8"
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args: object) -> None:
        pass


@contextmanager
def local_page() -> Iterator[str]:
    _Handler.requested_paths = []
    _Handler.active_requests = 0
    _Handler.max_active_requests = 0
    server = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
    thread = threading.Thread(target=server.serve_forever)
    thread.start()
    try:
        host, port = server.server_address
        yield f"http://{host}:{port}/article"
    finally:
        server.shutdown()
        thread.join()
        server.server_close()


def test_fetch_renders_local_javascript_page() -> None:
    with local_page() as url:
        html = fetch(url)

    assert '<p id="rendered">Rendered by JavaScript.</p>' in html


def test_fetch_reports_separate_launch_and_navigation_metrics() -> None:
    metrics: list[FetchMetrics] = []
    with local_page() as url:
        fetch(url, metrics_callback=metrics.append)

    assert len(metrics) == 1
    assert metrics[0].browser_launch_seconds > 0
    assert metrics[0].navigation_seconds > 0


def test_fetch_many_reuses_browser_limits_concurrency_and_preserves_order() -> None:
    metrics: list[FetchMetrics] = []
    with local_page() as url:
        base_url = url.rsplit("/", 1)[0]
        expected_urls = [f"{base_url}/batch/{index}" for index in range(3)]
        results = asyncio.run(
            fetch_many(
                [FetchRequest(target) for target in expected_urls],
                concurrency=2,
                metrics_callback=metrics.append,
            )
        )

    assert [result.url for result in results] == expected_urls
    assert all(result.error is None for result in results)
    assert [f"/batch/{index}" in (result.html or "") for index, result in enumerate(results)] == [
        True,
        True,
        True,
    ]
    assert _Handler.max_active_requests == 2
    assert len(metrics) == 3
    assert len({metric.browser_launch_seconds for metric in metrics}) == 1


def test_fetch_uses_partial_dom_after_navigation_timeout() -> None:
    with local_page() as url, pytest.warns(NavigationTimeoutWarning):
        html = fetch(f"{url.rsplit('/', 1)[0]}/network", wait_until="networkidle", timeout=1)

    assert "Partial content is ready." in html


def test_fetch_strict_mode_raises_navigation_timeout() -> None:
    with local_page() as url, pytest.raises(PlaywrightTimeoutError):
        fetch(f"{url.rsplit('/', 1)[0]}/network", wait_until="networkidle", timeout=1, strict=True)


def test_screenshot_allows_blocked_display_resources(tmp_path: Path) -> None:
    screenshot = tmp_path / "assets.png"
    with local_page() as url:
        asset_url = f"{url.rsplit('/', 1)[0]}/assets"
        fetch(asset_url, block_resources=frozenset({"image"}))
        assert "/pixel.png" not in _Handler.requested_paths
        fetch(asset_url, block_resources=frozenset({"image"}), screenshot_path=screenshot)

    assert "/pixel.png" in _Handler.requested_paths
    assert screenshot.read_bytes().startswith(b"\x89PNG")


def test_cli_end_to_end_writes_configured_markdown(tmp_path: Path) -> None:
    output = tmp_path / "article.md"
    with local_page() as url:
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "get_md.cli",
                url,
                "-o",
                str(output),
            "--front-matter",
            "--fetch",
            "browser",
                "--links",
                "text",
                "--content",
                "dom",
                "--debug-extraction",
            ],
            check=False,
            capture_output=True,
            text=True,
        )

    assert result.returncode == 0, result.stderr
    markdown = output.read_text(encoding="utf-8")
    assert "title: Local integration page" in markdown
    assert "Local guide" in markdown
    assert "Rendered by JavaScript." in markdown
    assert "Site navigation outside the article" not in markdown
    assert "](" not in markdown
    assert "extraction: mode=dom selected=main#content" in result.stderr


@pytest.mark.live
@pytest.mark.skipif(
    os.environ.get("GET_MD_RUN_LIVE_TESTS") != "1",
    reason="GET_MD_RUN_LIVE_TESTS=1 のときだけ実サイトへ接続する",
)
def test_youtube_openai_videos_include_meaningful_metadata(tmp_path: Path) -> None:
    """実際の動画一覧でタイトル、視聴回数、公開からの経過時間を確認する。"""
    output = tmp_path / "openai-videos.md"
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "get_md.cli",
            _YOUTUBE_LIVE_URL,
            "-o",
            str(output),
            "--content",
            "full",
            "--wait",
            "5",
        ],
        check=False,
        capture_output=True,
        text=True,
        timeout=60,
    )

    assert result.returncode == 0, result.stderr
    markdown = output.read_text(encoding="utf-8")
    videos = {video_id: title.strip() for title, video_id in _YOUTUBE_VIDEO_LINK.findall(markdown)}
    view_counts = _YOUTUBE_VIEW_COUNT.findall(markdown)
    relative_ages = _YOUTUBE_RELATIVE_AGE.findall(markdown)

    assert len(videos) >= _MINIMUM_MEANINGFUL_VIDEOS, (
        f"タイトル付きの異なる動画が {_MINIMUM_MEANINGFUL_VIDEOS} 件未満: {videos}"
    )
    assert len(view_counts) >= _MINIMUM_MEANINGFUL_VIDEOS, (
        f"視聴回数が {_MINIMUM_MEANINGFUL_VIDEOS} 件未満: {view_counts}"
    )
    assert len(relative_ages) >= _MINIMUM_MEANINGFUL_VIDEOS, (
        f"公開からの経過時間が {_MINIMUM_MEANINGFUL_VIDEOS} 件未満: {relative_ages}"
    )

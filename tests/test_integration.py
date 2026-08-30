from __future__ import annotations

import os
import re
import subprocess
import sys
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

from get_md.fetcher import fetch

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


class _Handler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:  # noqa: N802
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(_PAGE)))
        self.end_headers()
        self.wfile.write(_PAGE)

    def log_message(self, format: str, *args: object) -> None:
        pass


@contextmanager
def local_page() -> Iterator[str]:
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

from __future__ import annotations

import subprocess
import sys
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from get_md.fetcher import fetch

_PAGE = b"""<!doctype html>
<html lang="en">
<head><title>Local integration page</title></head>
<body>
  <main id="content"><a href="/guide">Local guide</a></main>
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
    assert "](" not in markdown

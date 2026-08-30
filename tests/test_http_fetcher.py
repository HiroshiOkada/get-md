from __future__ import annotations

import gzip
import threading
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from get_md.http_fetcher import fetch_http, is_meaningful_html


class _HttpHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:  # noqa: N802
        if self.path == "/redirect":
            self.send_response(302)
            self.send_header("Location", "/latin")
            self.end_headers()
            return
        if self.path == "/binary":
            body = b"not html"
            content_type = "application/octet-stream"
        elif self.path == "/gzip":
            body = gzip.compress(
                b"<main>" + ("圧縮された本文。" * 20).encode() + b"</main>"
            )
            content_type = "text/html; charset=utf-8"
        else:
            body = ("<meta charset=iso-8859-1><main>" + "caf\xe9 " * 30 + "</main>").encode(
                "iso-8859-1"
            )
            content_type = "text/html"
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        if self.path == "/gzip":
            self.send_header("Content-Encoding", "gzip")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args: object) -> None:
        pass


@contextmanager
def http_server():
    server = ThreadingHTTPServer(("127.0.0.1", 0), _HttpHandler)
    thread = threading.Thread(target=server.serve_forever)
    thread.start()
    try:
        host, port = server.server_address
        yield f"http://{host}:{port}"
    finally:
        server.shutdown()
        thread.join()
        server.server_close()


def test_fetch_http_follows_redirect_and_honors_meta_charset() -> None:
    with http_server() as base_url:
        result = fetch_http(f"{base_url}/redirect")

    assert result.final_url == f"{base_url}/latin"
    assert "café" in result.html


def test_fetch_http_decompresses_gzip() -> None:
    with http_server() as base_url:
        result = fetch_http(f"{base_url}/gzip")

    assert "圧縮された本文。" in result.html


def test_fetch_http_rejects_non_html_content() -> None:
    with http_server() as base_url, pytest.raises(ValueError, match="content type"):
        fetch_http(f"{base_url}/binary")


@pytest.mark.parametrize(
    ("html", "expected"),
    [
        ("<main>" + "Useful article sentence. " * 12 + "</main>", True),
        ("<div id=root></div><noscript>You need to enable JavaScript</noscript>", False),
        ("<html><body>Loading...</body></html>", False),
    ],
)
def test_meaningful_html_detection(html: str, expected: bool) -> None:
    assert is_meaningful_html(html) is expected

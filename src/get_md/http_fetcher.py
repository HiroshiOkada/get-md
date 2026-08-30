"""静的ページ向けの軽量な HTTP 取得とブラウザ要否判定。"""

from __future__ import annotations

import gzip
import re
import zlib
from dataclasses import dataclass
from urllib.request import Request, urlopen

from bs4 import BeautifulSoup

_USER_AGENT = "get-md/0.1 (+https://github.com/HiroshiOkada/get-md)"
_JS_SHELL_MARKERS = (
    "enable javascript",
    "javascript is required",
    "please turn on javascript",
    "you need to enable javascript",
)


@dataclass(frozen=True)
class HttpFetchResult:
    """HTTP 取得で得た HTML と redirect 後の URL。"""

    html: str
    final_url: str


def fetch_http(url: str, *, timeout: int = 30) -> HttpFetchResult:
    """HTML を HTTP で取得し、圧縮と宣言文字コードを処理する。"""
    request = Request(
        url,
        headers={"User-Agent": _USER_AGENT, "Accept-Encoding": "gzip, deflate"},
    )
    with urlopen(request, timeout=timeout) as response:  # noqa: S310 - URL は CLI 入力
        content_type = response.headers.get_content_type().lower()
        if content_type not in {"text/html", "application/xhtml+xml"}:
            raise ValueError(f"unsupported content type: {content_type}")
        payload = response.read()
        encoding = (response.headers.get("Content-Encoding") or "").lower()
        if encoding == "gzip":
            payload = gzip.decompress(payload)
        elif encoding == "deflate":
            payload = zlib.decompress(payload)
        charset = response.headers.get_content_charset() or _charset_from_html(payload) or "utf-8"
        return HttpFetchResult(payload.decode(charset, errors="replace"), response.geturl())


def is_meaningful_html(html: str) -> bool:
    """HTTP HTML が変換に十分かを保守的に判定する。"""
    soup = BeautifulSoup(html, "html.parser")
    for element in soup(["script", "style", "template", "noscript"]):
        element.decompose()
    text = " ".join(soup.get_text(" ", strip=True).split())
    lowered = text.lower()
    if any(marker in lowered for marker in _JS_SHELL_MARKERS):
        return False
    root = soup.select_one("main, article, [role=main]")
    paragraphs = len(soup.find_all("p"))
    return len(text) >= 200 or (root is not None and len(text) >= 80) or paragraphs >= 2


def _charset_from_html(payload: bytes) -> str | None:
    """先頭部分の meta charset を HTTP header の次候補として読む。"""
    match = re.search(
        br"<meta[^>]+charset\s*=\s*['\"]?\s*([\w.-]+)", payload[:4096], re.I
    )
    return match.group(1).decode("ascii", errors="ignore") if match else None


__all__ = ["HttpFetchResult", "fetch_http", "is_meaningful_html"]

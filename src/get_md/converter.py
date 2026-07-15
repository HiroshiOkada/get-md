"""HTML to Markdown conversion and output-path derivation."""

from __future__ import annotations

import re
from urllib.parse import unquote, urlsplit

from bs4 import BeautifulSoup
from markdownify import markdownify

# Tags whose entire subtree (content included) is dropped before conversion.
_DROP_TAGS = ("script", "style", "noscript", "template", "svg", "link", "meta")

_BLANK_LINES = re.compile(r"\n{3,}")


def to_markdown(html: str) -> str:
    """Convert raw ``html`` into Markdown text.

    The document head and non-content elements (scripts, styles, ...) are
    removed entirely before conversion so their text never leaks into output.
    """
    soup = BeautifulSoup(html, "html.parser")

    for name in _DROP_TAGS:
        for tag in soup.find_all(name):
            tag.decompose()

    root = soup.body or soup
    md = markdownify(str(root), heading_style="ATX")
    md = _BLANK_LINES.sub("\n\n", md).strip()
    return md + "\n"


def derive_output_path(url: str) -> str:
    """Derive a ``.md`` filename from ``url``.

    Uses the last non-empty path segment (percent-decoded), stripping any
    file extension. Returns ``index.md`` when the path has no useful segment.
    Query strings and fragments are ignored.
    """
    path = urlsplit(url).path
    segment = path.rstrip("/").rsplit("/", 1)[-1]
    if not segment:
        return "index.md"
    segment = unquote(segment)
    if "." in segment:
        segment = segment.rsplit(".", 1)[0]
    if not segment:
        return "index.md"
    return f"{segment}.md"


__all__ = ["to_markdown", "derive_output_path"]

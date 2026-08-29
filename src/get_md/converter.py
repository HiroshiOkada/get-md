"""HTML to Markdown conversion and output-path derivation."""

from __future__ import annotations

import re
from urllib.parse import unquote, urljoin, urlsplit

from bs4 import BeautifulSoup
from bs4.element import Tag
from markdownify import markdownify

# Tags whose entire subtree (content included) is dropped before conversion.
_DROP_TAGS = ("script", "style", "noscript", "template", "svg", "link", "meta")
_DROP_ROLES = {"banner", "contentinfo", "dialog", "navigation"}
_NOISE_TOKEN_RE = re.compile(
    r"(^|[-_])("
    r"ad|ads|advert|advertisement|"
    r"cookie|consent|"
    r"social-share|share-buttons"
    r")($|[-_])"
)
_HIDDEN_STYLE_RE = re.compile(r"(display\s*:\s*none|visibility\s*:\s*hidden)", re.I)

_BLANK_LINES = re.compile(r"\n{3,}")


def to_markdown(html: str, *, base_url: str | None = None) -> str:
    """Convert raw ``html`` into Markdown text.

    The document head and non-content elements (scripts, styles, ...) are
    removed entirely before conversion so their text never leaks into output.
    When ``base_url`` is provided, document-relative links and images are
    made absolute before Markdown conversion.
    """
    soup = BeautifulSoup(html, "html.parser")

    for name in _DROP_TAGS:
        for tag in soup.find_all(name):
            tag.decompose()

    _drop_hidden_and_noise(soup)

    if base_url is not None:
        _absolutize_urls(soup, base_url)

    root = soup.body or soup
    md = markdownify(str(root), heading_style="ATX")
    md = _BLANK_LINES.sub("\n\n", md).strip()
    return md + "\n"


def _drop_hidden_and_noise(soup: BeautifulSoup) -> None:
    for tag in soup.find_all(attrs={"hidden": True}):
        tag.decompose()
    for tag in soup.find_all(attrs={"aria-hidden": True}):
        if str(tag.get("aria-hidden", "")).lower() == "true":
            tag.decompose()
    for tag in soup.find_all(attrs={"style": True}):
        if _HIDDEN_STYLE_RE.search(str(tag["style"])):
            tag.decompose()
    for tag in soup.find_all(attrs={"role": True}):
        if str(tag.get("role", "")).lower() in _DROP_ROLES:
            tag.decompose()
    for tag in soup.find_all(_is_noise_tag):
        tag.decompose()


def _is_noise_tag(tag: Tag) -> bool:
    tokens: list[str] = []
    for attr in ("id", "class"):
        value = tag.get(attr)
        if isinstance(value, list):
            tokens.extend(str(item).lower() for item in value)
        elif value:
            tokens.append(str(value).lower())
    return any(_NOISE_TOKEN_RE.search(token) for token in tokens)


def _absolutize_urls(soup: BeautifulSoup, base_url: str) -> None:
    for tag in soup.find_all(attrs={"href": True}):
        tag["href"] = urljoin(base_url, tag["href"])
    for tag in soup.find_all(attrs={"src": True}):
        tag["src"] = urljoin(base_url, tag["src"])
    for tag in soup.find_all(attrs={"srcset": True}):
        tag["srcset"] = _absolutize_srcset(str(tag["srcset"]), base_url)


def _absolutize_srcset(srcset: str, base_url: str) -> str:
    candidates: list[str] = []
    for candidate in srcset.split(","):
        parts = candidate.strip().split()
        if not parts:
            continue
        parts[0] = urljoin(base_url, parts[0])
        candidates.append(" ".join(parts))
    return ", ".join(candidates)


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

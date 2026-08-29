"""HTML to Markdown conversion and output-path derivation."""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Literal
from urllib.parse import unquote, urljoin, urlsplit

from bs4 import BeautifulSoup
from bs4.element import Tag
from markdownify import markdownify
from yaml import safe_dump

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
_LANGUAGE_RE = re.compile(r"^(?:language-|lang-)([A-Za-z0-9_+.-]+)$", re.I)
_SAFE_LANGUAGE_RE = re.compile(r"^[A-Za-z0-9_+.-]+$")

_BLANK_LINES = re.compile(r"\n{3,}")
_TRAILING_WHITESPACE = re.compile(r"[ \t]+$", re.MULTILINE)


@dataclass(frozen=True, slots=True)
class ConversionOptions:
    """Optional Markdown features; defaults preserve the historical output."""

    front_matter: bool = False
    links: Literal["keep", "text", "strip"] = "keep"
    images: Literal["keep", "alt", "strip"] = "keep"


@dataclass(frozen=True, slots=True)
class PageMetadata:
    """Metadata discovered in an HTML document."""

    title: str | None = None
    description: str | None = None
    canonical_url: str | None = None
    author: str | None = None
    published_time: str | None = None
    language: str | None = None
    fetched_at: str | None = None


def to_markdown(
    html: str,
    *,
    base_url: str | None = None,
    options: ConversionOptions | None = None,
    fetched_at: datetime | None = None,
) -> str:
    """Convert raw ``html`` into Markdown text.

    The document head and non-content elements (scripts, styles, ...) are
    removed entirely before conversion so their text never leaks into output.
    When ``base_url`` is provided, document-relative links and images are
    made absolute before Markdown conversion.
    """
    options = options or ConversionOptions()
    soup = BeautifulSoup(html, "html.parser")

    if base_url is not None:
        _absolutize_urls(soup, base_url)
    metadata = extract_metadata(soup, fetched_at=fetched_at)

    for name in _DROP_TAGS:
        for tag in soup.find_all(name):
            tag.decompose()

    _drop_hidden_and_noise(soup)
    _drop_empty_elements(soup)
    _apply_content_policies(soup, options)

    root = soup.body or soup
    md = markdownify(
        str(root),
        heading_style="ATX",
        code_language_callback=_code_language,
    )
    md = _TRAILING_WHITESPACE.sub("", md)
    md = _BLANK_LINES.sub("\n\n", md).strip()
    result = md + "\n"
    if options.front_matter:
        result = _format_front_matter(metadata) + result
    return result


def extract_metadata(
    html: str | BeautifulSoup,
    *,
    fetched_at: datetime | None = None,
) -> PageMetadata:
    """Extract common page metadata without performing any I/O."""
    soup = html if isinstance(html, BeautifulSoup) else BeautifulSoup(html, "html.parser")

    def meta(*keys: tuple[str, str]) -> str | None:
        for attribute, value in keys:
            tag = soup.find("meta", attrs={attribute: value})
            if tag and str(tag.get("content", "")).strip():
                return str(tag["content"]).strip()
        return None

    title_tag = soup.find("title")
    heading = soup.find("h1")
    title = meta(("property", "og:title"))
    if title is None and title_tag:
        title = title_tag.get_text(" ", strip=True) or None
    if title is None and heading:
        title = heading.get_text(" ", strip=True) or None

    canonical = soup.find("link", rel=lambda value: value and "canonical" in value)
    canonical_url = str(canonical.get("href", "")).strip() if canonical else None
    html_tag = soup.find("html")
    language = str(html_tag.get("lang", "")).strip() if html_tag else None

    return PageMetadata(
        title=title,
        description=meta(("name", "description"), ("property", "og:description")),
        canonical_url=canonical_url or None,
        author=meta(("name", "author"), ("property", "article:author")),
        published_time=meta(
            ("property", "article:published_time"),
            ("name", "date"),
            ("name", "datePublished"),
        ),
        language=language or None,
        fetched_at=fetched_at.isoformat() if fetched_at else None,
    )


def _format_front_matter(metadata: PageMetadata) -> str:
    values = {key: value for key, value in asdict(metadata).items() if value is not None}
    yaml = safe_dump(values, allow_unicode=True, sort_keys=False).rstrip()
    return f"---\n{yaml}\n---\n\n"


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


def _drop_empty_elements(soup: BeautifulSoup) -> None:
    """Remove elements that cannot contribute meaningful Markdown."""
    for tag in soup.find_all(["a", "h1", "h2", "h3", "h4", "h5", "h6"]):
        if not tag.get_text(strip=True) and tag.find("img") is None:
            tag.decompose()
    for image in soup.find_all("img"):
        if not str(image.get("alt", "")).strip():
            image.decompose()


def _code_language(pre: Tag) -> str | None:
    """Return a safe fenced-code language declared on ``pre`` or its code child."""
    code = pre.find("code")
    for tag in (code, pre):
        if tag is None:
            continue
        for class_name in tag.get("class", []):
            match = _LANGUAGE_RE.fullmatch(str(class_name))
            if match:
                return match.group(1)
        for attribute in ("data-language", "data-lang"):
            value = str(tag.get(attribute, "")).strip()
            if _SAFE_LANGUAGE_RE.fullmatch(value):
                return value
    return None


def _apply_content_policies(soup: BeautifulSoup, options: ConversionOptions) -> None:
    if options.links == "text":
        for link in soup.find_all("a"):
            link.unwrap()
    elif options.links == "strip":
        for link in soup.find_all("a"):
            link.decompose()

    if options.images == "alt":
        for image in soup.find_all("img"):
            image.replace_with(str(image.get("alt", "")).strip())
    elif options.images == "strip":
        for image in soup.find_all("img"):
            image.decompose()


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


__all__ = [
    "ConversionOptions",
    "PageMetadata",
    "derive_output_path",
    "extract_metadata",
    "to_markdown",
]

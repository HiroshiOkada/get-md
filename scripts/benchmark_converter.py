"""Benchmark HTML fixture conversion without network access."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from time import perf_counter

from get_md.converter import to_markdown

_MARKDOWN_LINK_RE = re.compile(r"(?<!!)\[[^\]]+\]\([^)]+\)")


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "paths",
        nargs="+",
        type=Path,
        help="HTML fixture files or directories containing .html files.",
    )
    parser.add_argument(
        "--base-url",
        default=None,
        help="Optional base URL passed to to_markdown().",
    )
    return parser


def _iter_html_files(paths: list[Path]) -> list[Path]:
    files: list[Path] = []
    for path in paths:
        if path.is_dir():
            files.extend(sorted(path.glob("*.html")))
        else:
            files.append(path)
    return files


def _measure(path: Path, base_url: str | None) -> dict[str, object]:
    html = path.read_text(encoding="utf-8")
    started = perf_counter()
    markdown = to_markdown(html, base_url=base_url)
    elapsed_ms = (perf_counter() - started) * 1000
    return {
        "path": str(path),
        "elapsed_ms": round(elapsed_ms, 3),
        "html_chars": len(html),
        "markdown_chars": len(markdown),
        "markdown_links": len(_MARKDOWN_LINK_RE.findall(markdown)),
    }


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    paths = _iter_html_files(args.paths)
    if not paths:
        print("error: no HTML files found", file=sys.stderr)
        return 1

    for path in paths:
        print(json.dumps(_measure(path, args.base_url), ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

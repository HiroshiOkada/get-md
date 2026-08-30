"""Command-line interface for get-md."""

from __future__ import annotations

import argparse
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

from . import __version__
from .converter import ConversionOptions, ExtractionDecision, derive_output_path, to_markdown
from .fetcher import _RESOURCE_TYPES, _WAIT_UNTIL_VALUES, PlaywrightError, fetch

_EPILOG = (
    "First-time setup (installs the Chromium binary, needed once):\n"
    "  get-md --install-browser\n"
    "\n"
    "Examples:\n"
    "  get-md https://example.com/page\n"
    "  get-md https://example.com/page -o page.md\n"
    "  get-md https://example.com/page -o -      # print to stdout\n"
    "  get-md https://example.com/page --wait 3 --screenshot\n"
)


def install_browser() -> int:
    """Install the Chromium binary required by Playwright.

    Runs ``python -m playwright install chromium`` in the current interpreter
    environment so the browser lands in Playwright's shared cache regardless
    of how get-md itself was installed (uv tool install / uvx / uv add / pip).
    """
    print("Installing Chromium for Playwright ...", file=sys.stderr)
    try:
        subprocess.run(
            [sys.executable, "-m", "playwright", "install", "chromium"],
            check=True,
        )
    except subprocess.CalledProcessError as exc:
        print(f"error: playwright install failed: {exc}", file=sys.stderr)
        return exc.returncode or 1
    except OSError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print("Chromium installed.", file=sys.stderr)
    return 0


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="get-md",
        description="Fetch a JavaScript-rendered web page and convert it to Markdown.",
        epilog=_EPILOG,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "url",
        nargs="?",
        default=None,
        help="URL of the page to fetch. Required unless --install-browser is given.",
    )
    parser.add_argument(
        "--install-browser",
        action="store_true",
        help="Install the Chromium binary required by Playwright, then exit.",
    )
    parser.add_argument(
        "-o",
        "--output",
        default=None,
        help="Output Markdown path. Use '-' for stdout. Defaults to a name derived from the URL.",
    )
    parser.add_argument(
        "--wait",
        type=float,
        default=0.0,
        help="Extra seconds to wait for JavaScript rendering after page load.",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=30,
        help="Navigation timeout in seconds (default: 30).",
    )
    parser.add_argument(
        "--wait-until",
        choices=_WAIT_UNTIL_VALUES,
        default="domcontentloaded",
        help="Navigation lifecycle event to await (default: domcontentloaded).",
    )
    parser.add_argument(
        "--wait-for-selector",
        default=None,
        help="Wait for a selector to become visible after navigation.",
    )
    parser.add_argument(
        "--screenshot",
        action="store_true",
        help="Also save a full-page PNG screenshot next to the Markdown output.",
    )
    parser.add_argument(
        "--block-resources",
        type=_parse_resource_types,
        default=frozenset({"font", "media"}),
        metavar="TYPE[,TYPE...]",
        help="Resource types to block (default: font,media; use 'none' to disable).",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Fail instead of using a partial DOM when navigation times out.",
    )
    parser.add_argument(
        "--front-matter",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="Include page metadata as YAML front matter (default: disabled).",
    )
    parser.add_argument(
        "--links",
        choices=("keep", "text", "strip"),
        default="keep",
        help="How to render links: keep Markdown links, keep text only, or strip them.",
    )
    parser.add_argument(
        "--images",
        choices=("keep", "alt", "strip"),
        default="keep",
        help="How to render images: keep Markdown images, keep alt text only, or strip them.",
    )
    parser.add_argument(
        "--content",
        choices=("full", "dom", "readability", "auto"),
        default="full",
        help="Content extraction mode: full, DOM, Readability, or automatic (default: full).",
    )
    parser.add_argument(
        "--debug-extraction",
        action="store_true",
        help="Print content candidate scores and the extraction decision to stderr.",
    )
    parser.add_argument(
        "-V",
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    if args.install_browser:
        return install_browser()

    if args.url is None:
        parser.error("the following arguments are required: url")

    output = args.output
    to_stdout = output == "-"
    if output is None:
        output = derive_output_path(args.url)

    screenshot_path: Path | None = None
    if args.screenshot:
        if to_stdout:
            parser.error("--screenshot is incompatible with -o -")
        screenshot_path = Path(output).with_suffix(".png")

    try:
        html = fetch(
            args.url,
            wait=args.wait,
            timeout=args.timeout,
            screenshot_path=screenshot_path,
            wait_until=args.wait_until,
            wait_for_selector=args.wait_for_selector,
            block_resources=args.block_resources,
            strict=args.strict,
        )
    except PlaywrightError as exc:
        print(f"error: failed to render page: {exc}", file=sys.stderr)
        return 1
    except OSError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    md = to_markdown(
        html,
        base_url=args.url,
        options=ConversionOptions(
            front_matter=args.front_matter,
            links=args.links,
            images=args.images,
            content=args.content,
        ),
        fetched_at=datetime.now(UTC),
        extraction_callback=_print_extraction_debug if args.debug_extraction else None,
    )

    if to_stdout:
        sys.stdout.write(md)
    else:
        Path(output).write_text(md, encoding="utf-8")
        print(f"saved: {output}")
        if screenshot_path is not None:
            print(f"saved: {screenshot_path}")
    return 0


def _print_extraction_debug(decision: ExtractionDecision) -> None:
    print(
        f"extraction: mode={decision.requested_mode} selected={decision.selected} "
        f"reason={decision.reason}",
        file=sys.stderr,
    )
    for candidate in decision.candidates:
        print(
            f"candidate: selector={candidate.selector} score={candidate.score:.2f} "
            f"text={candidate.text_length} paragraphs={candidate.paragraphs} "
            f"links={candidate.link_density:.3f} punctuation={candidate.punctuation} "
            f"structure={candidate.structural_elements}",
            file=sys.stderr,
        )


def _parse_resource_types(value: str) -> frozenset[str]:
    if value == "none":
        return frozenset()
    resource_types = frozenset(part.strip() for part in value.split(",") if part.strip())
    invalid = resource_types - _RESOURCE_TYPES
    if invalid:
        raise argparse.ArgumentTypeError(f"unknown resource type(s): {', '.join(sorted(invalid))}")
    if not resource_types:
        raise argparse.ArgumentTypeError("specify resource types or 'none'")
    return resource_types


if __name__ == "__main__":
    sys.exit(main())

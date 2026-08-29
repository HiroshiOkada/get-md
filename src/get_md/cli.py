"""Command-line interface for get-md."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

from . import __version__
from .converter import derive_output_path, to_markdown
from .fetcher import PlaywrightError, fetch

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
        "--screenshot",
        action="store_true",
        help="Also save a full-page PNG screenshot next to the Markdown output.",
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
        )
    except PlaywrightError as exc:
        print(f"error: failed to render page: {exc}", file=sys.stderr)
        return 1
    except OSError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    md = to_markdown(html, base_url=args.url)

    if to_stdout:
        sys.stdout.write(md)
    else:
        Path(output).write_text(md, encoding="utf-8")
        print(f"saved: {output}")
        if screenshot_path is not None:
            print(f"saved: {screenshot_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

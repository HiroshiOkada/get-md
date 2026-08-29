# get-md

Fetch a JavaScript-rendered web page with Playwright and convert it to Markdown using [`markdownify`](https://github.com/matthewwithanm/python-markdownify).

## Requirements

- Python 3.14+
- A Chromium browser installed for Playwright (see [First-time setup](#first-time-setup))

## Installation

`get-md` can be installed or run in several ways. Pick whichever fits your workflow, then perform the [First-time setup](#first-time-setup) once.

### With uv tool (recommended)

Installs `get-md` as a standalone command on your PATH (pipx-style, with its own isolated environment):

```sh
uv tool install git+https://github.com/<your-github-username>/get-md
get-md https://example.com/page
```

### Run directly without installing (uvx)

```sh
uvx --from git+https://github.com/<your-github-username>/get-md get-md https://example.com/page
```

### Add to a uv project

```sh
uv add git+https://github.com/<your-github-username>/get-md
```

### Add to a pip-managed project

```sh
pip install git+https://github.com/<your-github-username>/get-md
```

## First-time setup

Playwright needs its Chromium binary once before first use. It is **not** installed automatically. After installing `get-md` by any method above, run:

```sh
get-md --install-browser
```

This works regardless of how `get-md` was installed (`uv tool install`, `uvx`, `uv add`, or `pip`), because the browser lands in Playwright's shared cache.

> Tip: When running via `uvx` without installing, use `--install-browser` the same way:
>
> ```sh
> uvx --from git+https://github.com/<your-github-username>/get-md get-md --install-browser
> ```

## Usage

```sh
get-md <URL> [options]
```

### Options

| Option | Description |
| --- | --- |
| `<URL>` | URL of the page to fetch (required, unless `--install-browser` is given). |
| `--install-browser` | Install the Chromium binary required by Playwright, then exit. |
| `-o, --output PATH` | Output Markdown file path. Use `-` to print to stdout. Defaults to a name derived from the URL. |
| `--wait SECONDS` | Extra seconds to wait for JavaScript rendering after the page loads. |
| `--timeout SECONDS` | Navigation timeout in seconds (default: 30). |
| `--screenshot` | Also save a full-page PNG screenshot next to the Markdown output. Incompatible with `-o -`. |
| `--front-matter`, `--no-front-matter` | Include page metadata as safe YAML front matter. Disabled by default. |
| `--links keep\|text\|strip` | Keep Markdown links, keep only their text, or remove linked content (default: `keep`). |
| `--images keep\|alt\|strip` | Keep Markdown images, keep only alt text, or remove images (default: `keep`). |
| `-V, --version` | Show the version and exit. |

### Examples

Save Markdown to a URL-derived filename:

```sh
get-md https://example.com/some/deep/page
# -> writes "page.md" in the current directory
```

Specify an output path:

```sh
get-md https://example.com/page -o page.md
```

Print Markdown to stdout:

```sh
get-md https://example.com/page -o -
```

Wait for late rendering and also capture a screenshot:

```sh
get-md https://example.com/page --wait 3 --screenshot
# -> writes "page.md" and "page.png"
```

Create an LLM-friendly document with source metadata and without link or image URLs:

```sh
get-md https://example.com/article --front-matter --links text --images alt
```

Front matter may contain the page title, description, canonical URL, author, publication
time, language, and fetch time when those values are available. Values are YAML-encoded,
and metadata remains opt-in so existing output is unchanged by default.

## How it works

1. The page is rendered with a headless Chromium via Playwright, so JavaScript-generated content is captured.
2. The resulting HTML is converted to Markdown with `markdownify`, stripping non-content tags (`script`, `style`, `noscript`, `template`, `svg`, `link`, `meta`).
3. Hidden elements, ARIA-hidden content, and obvious UI noise such as cookie banners, navigation roles, dialogs, ads, and share buttons are removed conservatively before conversion.
4. Relative link and image URLs are resolved against the requested page URL so the Markdown remains portable.
5. Empty headings, links, and decorative images are removed; code block language declarations are preserved.
6. Links, images, and YAML front matter are rendered according to the selected output options.
7. The Markdown is written to the chosen file path (or stdout).

## Development

Development rules are defined in [AGENTS.md](AGENTS.md). The improvement roadmap and its
supporting research are indexed in [docs/README.md](docs/README.md).

Standard checks:

```sh
uv run python -m pytest
uv run ruff check .
```

Run the fixture conversion benchmark:

```sh
uv run python scripts/benchmark_converter.py tests/fixtures
```

## License

MIT

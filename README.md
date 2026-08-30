# get-md

Fetch a web page over HTTP when possible, fall back to Playwright for JavaScript-rendered pages,
and convert the result to Markdown using [`markdownify`](https://github.com/matthewwithanm/python-markdownify).

## Requirements

- Python 3.14+
- A Chromium browser installed for automatic fallback and `--fetch browser` (see [First-time setup](#first-time-setup))

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
get-md <URL> [URL ...] [options]
```

### Options

| Option | Description |
| --- | --- |
| `<URL>` | One or more URLs to fetch (unless `--input` or `--install-browser` is given). |
| `--input PATH` | Read additional URLs from a UTF-8 file, one URL per line. Empty lines and `#` comments are ignored. |
| `--install-browser` | Install the Chromium binary required by Playwright, then exit. |
| `-o, --output PATH` | Output Markdown file path. Use `-` to print to stdout. Defaults to a name derived from the URL. |
| `--output-dir DIR` | Save URL-derived output files in this directory. Multiple URLs require this or `-o DIR`. |
| `--concurrency N` | Maximum pages fetched concurrently in a batch (default: `4`). |
| `--fetch auto\|http\|browser` | Use a static HTTP request, Chromium, or HTTP with automatic browser fallback (default: `auto`). |
| `--wait SECONDS` | Extra seconds to wait for JavaScript rendering after the page loads. |
| `--timeout SECONDS` | Navigation timeout in seconds (default: 30). |
| `--wait-until EVENT` | Navigation event to await: `domcontentloaded`, `load`, `networkidle`, or `commit` (default: `domcontentloaded`). |
| `--wait-for-selector SELECTOR` | Wait until a selector becomes visible after navigation. |
| `--screenshot` | Also save a full-page PNG screenshot next to the Markdown output. Incompatible with `-o -`. |
| `--block-resources TYPE[,TYPE...]` | Block resource types while fetching (default: `font,media`; use `none` to disable). Display resources are allowed for screenshots. |
| `--strict` | Fail instead of using an available partial DOM after a navigation timeout. |
| `--front-matter`, `--no-front-matter` | Include page metadata as safe YAML front matter. Disabled by default. |
| `--links keep\|text\|strip` | Keep Markdown links, keep only their text, or remove linked content (default: `keep`). |
| `--images keep\|alt\|strip` | Keep Markdown images, keep only alt text, or remove images (default: `keep`). |
| `--content full\|dom\|readability\|auto` | Convert the full document, use a scored DOM candidate, use Readability, or choose automatically (`full` by default). |
| `--debug-extraction` | Print candidate scores, the selected root, and fallback reasons to stderr. |
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

Fetch multiple pages from arguments and a file:

```sh
get-md https://example.com/one --input urls.txt --output-dir exported --concurrency 4
```

Batch mode launches Chromium once, reuses it for every URL, and preserves input order while
limiting active pages with `--concurrency`. A failed URL is reported to stderr without cancelling
the remaining URLs; the command exits nonzero after saving all successful results. Progress,
warnings, and output paths are written to stderr.

### Fetch selection and browser requirements

With the default `--fetch auto`, each URL is first requested over HTTP. HTML with enough visible
text or article structure is converted immediately without starting Chromium. Short app shells,
empty root elements, common JavaScript-required messages, HTTP failures, and non-HTML responses
fall back to the shared browser. Use `--fetch http` for predictable browser-free operation, or
`--fetch browser` when JavaScript enhancements must always be captured. Screenshots always use the
browser. HTTP mode follows redirects, decodes gzip/deflate responses, honors declared character
sets, and uses the redirect destination as the base for relative URLs.

`--wait`, `--wait-until`, `--wait-for-selector`, `--block-resources`, and `--strict` apply to
browser fetches. They have no effect when HTTP content is accepted without fallback. The
`networkidle` event is opt-in because pages with continuous network activity may not reach it.
Browser navigation allows a usable partial DOM after a timeout unless `--strict` is supplied.

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

Extract the primary article or main element while inspecting the selection decision:

```sh
get-md https://example.com/article --content auto --debug-extraction
```

`readability` and `auto` first use `readability-lxml`, which was selected by comparing article,
technical-document, and table fixtures. Its result must pass checks for text length, paragraphs,
link density, and document structure. Otherwise conversion falls back to the scored DOM candidates,
and then to the full document if no candidate is suitable. `dom` skips Readability and starts with
the DOM candidates. The default remains `full` for compatibility.

Front matter may contain the page title, description, canonical URL, author, publication
time, language, and fetch time when those values are available. Values are YAML-encoded,
and metadata remains opt-in so existing output is unchanged by default.

### Output rules and exit status

- A single URL defaults to a sanitized filename derived from its path, or `index.md` when the path
  has no filename. `-o -` writes Markdown only to stdout.
- For multiple URLs, `--output-dir DIR` and `-o DIR` are equivalent. The command rejects derived
  filename collisions rather than overwriting an earlier result.
- `--screenshot` requires a file output and always uses Chromium. The PNG uses the Markdown
  filename with a `.png` suffix.
- Status messages and per-URL errors go to stderr. A successful run exits with status `0`.
  Argument errors, startup/fetch failures, or any failed URL in a batch produce a nonzero status;
  successful batch results are still saved.

### Current limitations

- Browser installation is separate from Python package installation, and browser fallback cannot
  run until `get-md --install-browser` has completed.
- HTTP fetching does not execute JavaScript. Automatic mode uses conservative heuristics, but a
  page whose incomplete static HTML looks substantial may require an explicit `--fetch browser`.
- Content extraction is conservative rather than lossless. Use `--content full` when navigation,
  appendices, or other page-wide material must be retained.
- Authenticated pages, cookie/session reuse, persistent browser profiles, and result caching are
  not currently supported.

## How it works

1. The page is requested over HTTP and checked for meaningful visible content; insufficient app shells fall back to headless Chromium via Playwright.
2. The resulting HTML is converted to Markdown with `markdownify`, stripping non-content tags (`script`, `style`, `noscript`, `template`, `svg`, `link`, `meta`).
3. Hidden elements, ARIA-hidden content, and obvious UI noise such as cookie banners, navigation roles, dialogs, ads, and share buttons are removed conservatively before conversion.
4. Relative link and image URLs are resolved against the requested page URL so the Markdown remains portable.
5. Empty headings, links, and decorative images are removed; code block language declarations are preserved.
6. When requested, semantic content candidates are scored and the best suitable root is selected.
7. Links, images, and YAML front matter are rendered according to the selected output options.
8. The Markdown is written to the chosen file path (or stdout).

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

Measure browser cold-start and navigation time separately:

```sh
uv run python scripts/benchmark_fetch.py https://example.com --runs 3
```

Compare sequential browser launches with a browser-reusing batch:

```sh
uv run python scripts/benchmark_batch.py \
  https://example.com/one https://example.com/two --concurrency 2
```

Compare the optional article extraction libraries:

```sh
uv run python scripts/compare_extractors.py
```

## License

MIT

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

## How it works

1. The page is rendered with a headless Chromium via Playwright, so JavaScript-generated content is captured.
2. The resulting HTML is converted to Markdown with `markdownify`, stripping non-content tags (`script`, `style`, `noscript`, `template`, `svg`, `link`, `meta`).
3. The Markdown is written to the chosen file path (or stdout).

## License

MIT
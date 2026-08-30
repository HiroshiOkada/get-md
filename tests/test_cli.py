from __future__ import annotations

from pathlib import Path

import pytest

from get_md import cli
from get_md.fetcher import FetchResult
from get_md.http_fetcher import HttpFetchResult


def test_readme_documents_public_cli_options() -> None:
    readme = (Path(__file__).parents[1] / "README.md").read_text(encoding="utf-8")
    help_text = cli._build_parser().format_help()
    public_options = (
        "--fetch",
        "--input",
        "--install-browser",
        "--output",
        "--output-dir",
        "--concurrency",
        "--wait",
        "--timeout",
        "--wait-until",
        "--wait-for-selector",
        "--screenshot",
        "--block-resources",
        "--strict",
        "--front-matter",
        "--no-front-matter",
        "--links",
        "--images",
        "--content",
        "--debug-extraction",
        "--version",
    )

    for option in public_options:
        assert option in help_text
        assert option in readme


def test_cli_auto_uses_http_without_starting_browser(monkeypatch, capsys) -> None:
    html = "<main>" + "A complete static article sentence. " * 12 + "</main>"
    monkeypatch.setattr(
        cli, "fetch_http", lambda *args, **kwargs: HttpFetchResult(html, "https://example.com/final")
    )
    monkeypatch.setattr(cli, "fetch", lambda *args, **kwargs: pytest.fail("browser started"))

    result = cli.main(["https://example.com/start", "-o", "-"])

    assert result == 0
    assert "complete static article" in capsys.readouterr().out


def test_cli_auto_falls_back_to_browser_for_spa_shell(monkeypatch, capsys) -> None:
    monkeypatch.setattr(
        cli,
        "fetch_http",
        lambda *args, **kwargs: HttpFetchResult(
            "<div id=root></div><noscript>You need to enable JavaScript</noscript>",
            "https://example.com/app",
        ),
    )
    monkeypatch.setattr(cli, "fetch", lambda *args, **kwargs: "<main>Rendered application</main>")

    result = cli.main(["https://example.com/app", "-o", "-"])

    assert result == 0
    assert "Rendered application" in capsys.readouterr().out


def test_cli_passes_markdown_options(monkeypatch, capsys) -> None:
    monkeypatch.setattr(
        cli,
        "fetch",
        lambda *args, **kwargs: (
            "<html><head><title>Example</title></head>"
            '<body><a href="/guide">Guide</a><img src="image.png" alt="Image"></body></html>'
        ),
    )

    result = cli.main(
        [
            "https://example.com/page",
            "--fetch",
            "browser",
            "-o",
            "-",
            "--front-matter",
            "--links",
            "text",
            "--images",
            "alt",
        ]
    )

    output = capsys.readouterr().out
    assert result == 0
    assert output.startswith("---\ntitle: Example\n")
    assert "GuideImage" in output
    assert "](https://" not in output


def test_cli_selects_dom_content_and_prints_extraction_debug(monkeypatch, capsys) -> None:
    monkeypatch.setattr(
        cli,
        "fetch",
        lambda *args, **kwargs: """
            <body><header>Site chrome</header><article id="guide">
              <h1>Useful guide</h1>
              <p>This paragraph contains enough meaningful detail for content extraction.</p>
              <p>A second paragraph provides more useful information for the reader.</p>
            </article></body>
        """,
    )

    result = cli.main(
        [
            "https://example.com/guide",
            "-o",
            "-",
            "--fetch",
            "browser",
            "--content",
            "dom",
            "--debug-extraction",
        ]
    )

    captured = capsys.readouterr()
    assert result == 0
    assert "Useful guide" in captured.out
    assert "Site chrome" not in captured.out
    assert "extraction: mode=dom selected=article#guide" in captured.err
    assert "candidate: selector=article#guide" in captured.err


def test_cli_reads_multiple_urls_and_writes_to_output_directory(
    monkeypatch, tmp_path, capsys
) -> None:
    input_path = tmp_path / "urls.txt"
    input_path.write_text("# targets\nhttps://example.com/second\n\n", encoding="utf-8")
    fetched: list[str] = []
    received_concurrency: list[int] = []

    async def fake_fetch_many(requests, *, concurrency: int, **kwargs):
        received_concurrency.append(concurrency)
        fetched.extend(request.url for request in requests)
        return [
            FetchResult(request.url, html=f"<html><body><h1>{request.url}</h1></body></html>")
            for request in requests
        ]

    monkeypatch.setattr(cli, "fetch_many", fake_fetch_many)
    output_dir = tmp_path / "results"

    result = cli.main(
        [
            "https://example.com/first",
            "--input",
            str(input_path),
            "--output-dir",
            str(output_dir),
            "--concurrency",
            "2",
            "--fetch",
            "browser",
        ]
    )

    assert result == 0
    assert fetched == ["https://example.com/first", "https://example.com/second"]
    assert received_concurrency == [2]
    assert "https://example.com/first" in (output_dir / "first.md").read_text()
    assert "https://example.com/second" in (output_dir / "second.md").read_text()
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err.count("saved:") == 2


def test_cli_accepts_output_as_directory_for_multiple_urls(monkeypatch, tmp_path) -> None:
    async def fake_fetch_many(requests, **kwargs):
        return [FetchResult(request.url, html="<p>content</p>") for request in requests]

    monkeypatch.setattr(cli, "fetch_many", fake_fetch_many)
    output_dir = tmp_path / "results"

    result = cli.main(
        [
            "https://example.com/one",
            "https://example.com/two",
            "-o",
            str(output_dir),
            "--fetch",
            "browser",
        ]
    )

    assert result == 0
    assert (output_dir / "one.md").is_file()
    assert (output_dir / "two.md").is_file()


def test_cli_batch_continues_after_error_and_preserves_result_order(
    monkeypatch, tmp_path, capsys
) -> None:
    async def fake_fetch_many(requests, **kwargs):
        return [
            FetchResult(requests[0].url, html="<h1>First</h1>"),
            FetchResult(requests[1].url, error=OSError("unreachable")),
            FetchResult(requests[2].url, html="<h1>Third</h1>"),
        ]

    monkeypatch.setattr(cli, "fetch_many", fake_fetch_many)
    output_dir = tmp_path / "results"

    result = cli.main(
        [
            "https://example.com/first",
            "https://example.com/failed",
            "https://example.com/third",
            "--output-dir",
            str(output_dir),
            "--fetch",
            "browser",
        ]
    )

    assert result == 1
    assert (output_dir / "first.md").read_text(encoding="utf-8").startswith("# First")
    assert not (output_dir / "failed.md").exists()
    assert (output_dir / "third.md").read_text(encoding="utf-8").startswith("# Third")
    captured = capsys.readouterr()
    assert captured.err.index("saved: ") < captured.err.index("error: failed")
    assert captured.err.rindex("saved: ") > captured.err.index("error: failed")


def test_cli_single_url_keeps_fetch_and_output_compatibility(monkeypatch, tmp_path) -> None:
    called: list[str] = []

    def fake_fetch(url: str, **kwargs) -> str:
        called.append(url)
        return "<h1>Single</h1>"

    monkeypatch.setattr(cli, "fetch", fake_fetch)
    output = tmp_path / "custom.md"

    result = cli.main(
        ["https://example.com/single", "-o", str(output), "--fetch", "browser"]
    )

    assert result == 0
    assert called == ["https://example.com/single"]
    assert output.read_text(encoding="utf-8").startswith("# Single")


def test_cli_rejects_batch_output_filename_collision(tmp_path) -> None:
    with pytest.raises(SystemExit):
        cli.main(
            [
                "https://first.example/article",
                "https://second.example/article",
                "--output-dir",
                str(tmp_path),
            ]
        )


def test_cli_rejects_non_positive_concurrency() -> None:
    with pytest.raises(SystemExit):
        cli.main(["https://example.com", "--concurrency", "0"])

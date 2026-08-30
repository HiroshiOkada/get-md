from __future__ import annotations

from get_md import cli


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
        ["https://example.com/guide", "-o", "-", "--content", "dom", "--debug-extraction"]
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

    def fake_fetch(url: str, **kwargs: object) -> str:
        fetched.append(url)
        return f"<html><body><h1>{url}</h1></body></html>"

    monkeypatch.setattr(cli, "fetch", fake_fetch)
    output_dir = tmp_path / "results"

    result = cli.main(
        [
            "https://example.com/first",
            "--input",
            str(input_path),
            "--output-dir",
            str(output_dir),
        ]
    )

    assert result == 0
    assert fetched == ["https://example.com/first", "https://example.com/second"]
    assert "https://example.com/first" in (output_dir / "first.md").read_text()
    assert "https://example.com/second" in (output_dir / "second.md").read_text()
    assert capsys.readouterr().out.count("saved:") == 2


def test_cli_accepts_output_as_directory_for_multiple_urls(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(cli, "fetch", lambda *args, **kwargs: "<p>content</p>")
    output_dir = tmp_path / "results"

    result = cli.main(
        ["https://example.com/one", "https://example.com/two", "-o", str(output_dir)]
    )

    assert result == 0
    assert (output_dir / "one.md").is_file()
    assert (output_dir / "two.md").is_file()

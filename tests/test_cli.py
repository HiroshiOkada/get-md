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

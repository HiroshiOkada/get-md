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

from __future__ import annotations

from pathlib import Path

from get_md.converter import to_markdown


FIXTURE_DIR = Path(__file__).parent / "fixtures"


def read_fixture(name: str) -> str:
    return (FIXTURE_DIR / name).read_text(encoding="utf-8")


def test_to_markdown_keeps_current_basic_output() -> None:
    html = read_fixture("basic_article.html")

    assert to_markdown(html) == (
        "Site Header\n\n"
        "# Fixture Article\n\n"
        "This page keeps headings, paragraphs, links, images, code, and tables.\n\n"
        "Read the [getting started guide](/docs/start).\n\n"
        "![Chart](images/chart.png)\n\n"
        "```\n"
        'print("hello")\n'
        "```\n\n"
        "| Name | Value |\n"
        "| --- | --- |\n"
        "| alpha | 1 |\n"
        "\n"
    )

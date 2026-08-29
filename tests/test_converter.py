from __future__ import annotations

from pathlib import Path

from get_md.converter import _absolutize_srcset, to_markdown

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
    )


def test_to_markdown_absolutizes_links_and_images_with_base_url() -> None:
    html = """
    <main>
      <a href="/docs/start">Guide</a>
      <a href="../api">API</a>
      <img src="images/chart.png" alt="Chart">
      <img
        srcset="small.png 1x, /assets/large.png 2x"
        src="fallback.png"
        alt="Responsive chart"
      >
    </main>
    """

    md = to_markdown(html, base_url="https://example.com/products/page/")

    assert "[Guide](https://example.com/docs/start)" in md
    assert "[API](https://example.com/products/api)" in md
    assert "![Chart](https://example.com/products/page/images/chart.png)" in md
    assert "![Responsive chart](https://example.com/products/page/fallback.png)" in md


def test_absolutize_srcset_preserves_descriptors() -> None:
    assert _absolutize_srcset(
        "small.png 480w, /assets/large.png 960w",
        "https://example.com/products/page/",
    ) == (
        "https://example.com/products/page/small.png 480w, "
        "https://example.com/assets/large.png 960w"
    )


def test_to_markdown_drops_hidden_and_obvious_noise() -> None:
    html = """
    <main>
      <p>Visible article text.</p>
      <p hidden>Hidden text.</p>
      <p aria-hidden="true">Aria hidden text.</p>
      <p style="display: none">Display hidden text.</p>
      <p style="visibility:hidden">Visibility hidden text.</p>
      <nav role="navigation">Navigation links</nav>
      <aside class="cookie-banner">Cookie settings</aside>
      <div id="ad-slot">Advertisement</div>
      <div class="share-buttons">Share this page</div>
      <p class="shared-context">This paragraph should stay.</p>
    </main>
    """

    md = to_markdown(html)

    assert "Visible article text." in md
    assert "This paragraph should stay." in md
    assert "Hidden text." not in md
    assert "Aria hidden text." not in md
    assert "Display hidden text." not in md
    assert "Visibility hidden text." not in md
    assert "Navigation links" not in md
    assert "Cookie settings" not in md
    assert "Advertisement" not in md
    assert "Share this page" not in md

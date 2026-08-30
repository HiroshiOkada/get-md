from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from yaml import safe_load

from get_md.converter import ConversionOptions, _absolutize_srcset, extract_metadata, to_markdown

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


def test_to_markdown_cleans_empty_elements_and_trailing_whitespace() -> None:
    html = """
    <main>
      <h2>   </h2>
      <a href="/empty"> </a>
      <img src="decorative.png" alt="">
      <p>Meaningful text.<br>Next line.   </p>
    </main>
    """

    md = to_markdown(html)

    assert md == "Meaningful text.\nNext line.\n"
    assert all(line == line.rstrip() for line in md.splitlines())


def test_to_markdown_preserves_code_language() -> None:
    html = """
    <main>
      <pre><code class="highlight language-python">print("hello")</code></pre>
      <pre data-language="typescript"><code>const ready = true;</code></pre>
      <pre><code class="language-python;bad">unsafe()</code></pre>
    </main>
    """

    md = to_markdown(html)

    assert '```python\nprint("hello")\n```' in md
    assert "```typescript\nconst ready = true;\n```" in md
    assert "```\nunsafe()\n```" in md


def test_extract_metadata_uses_document_metadata() -> None:
    html = """
    <html lang="ja"><head>
      <title>Fallback title</title>
      <meta property="og:title" content="A title: with YAML syntax">
      <meta name="description" content="Summary #1">
      <meta name="author" content="Example Author">
      <meta property="article:published_time" content="2026-08-29T12:00:00Z">
      <link rel="canonical" href="/canonical/page">
    </head><body><h1>Heading</h1></body></html>
    """
    fetched_at = datetime(2026, 8, 29, 13, 0, tzinfo=UTC)

    metadata = extract_metadata(html, fetched_at=fetched_at)

    assert metadata.title == "A title: with YAML syntax"
    assert metadata.description == "Summary #1"
    assert metadata.author == "Example Author"
    assert metadata.published_time == "2026-08-29T12:00:00Z"
    assert metadata.canonical_url == "/canonical/page"
    assert metadata.language == "ja"
    assert metadata.fetched_at == "2026-08-29T13:00:00+00:00"


def test_to_markdown_adds_safe_front_matter_only_when_requested() -> None:
    html = """
    <html lang="ja"><head>
      <meta property="og:title" content="A title: with YAML syntax">
      <link rel="canonical" href="/canonical/page">
    </head><body><p>Content.</p></body></html>
    """

    plain = to_markdown(html, base_url="https://example.com/source")
    with_metadata = to_markdown(
        html,
        base_url="https://example.com/source",
        options=ConversionOptions(front_matter=True),
    )

    assert plain == "Content.\n"
    _, yaml, body = with_metadata.split("---", 2)
    assert safe_load(yaml) == {
        "title": "A title: with YAML syntax",
        "canonical_url": "https://example.com/canonical/page",
        "language": "ja",
    }
    assert body.strip() == "Content."


def test_to_markdown_applies_link_and_image_policies() -> None:
    html = """
    <p>Read <a href="/guide">the guide</a>.</p>
    <p><img src="diagram.png" alt="System diagram"></p>
    """

    text_only = to_markdown(
        html,
        options=ConversionOptions(links="text", images="alt"),
    )
    stripped = to_markdown(
        html,
        options=ConversionOptions(links="strip", images="strip"),
    )

    assert text_only == "Read the guide.\n\nSystem diagram\n"
    assert stripped == "Read .\n"


def test_dom_content_selects_the_highest_quality_candidate() -> None:
    html = """
    <body>
      <main><p>Short introduction that should not win this candidate comparison.</p></main>
      <article id="story">
        <h1>Primary story</h1>
        <p>This is the first substantial paragraph. It contains useful article details.</p>
        <p>This is another substantial paragraph, with enough text to identify the body.</p>
      </article>
      <footer>Unrelated footer text.</footer>
    </body>
    """
    decisions = []

    md = to_markdown(
        html,
        options=ConversionOptions(content="dom"),
        extraction_callback=decisions.append,
    )

    assert "Primary story" in md
    assert "Short introduction" not in md
    assert "Unrelated footer" not in md
    assert decisions[0].selected == "article#story"
    assert decisions[0].candidates[0].paragraphs == 2


def test_dom_content_falls_back_for_short_or_link_heavy_candidates() -> None:
    short_html = "<body><header>Site name</header><main><p>Brief.</p></main></body>"
    link_html = """
    <body><p>Page context outside candidate.</p><main>
      <a href="/1">A long navigation destination one</a>
      <a href="/2">A long navigation destination two</a>
      <a href="/3">A long navigation destination three</a>
    </main></body>
    """
    decisions = []

    short_md = to_markdown(
        short_html,
        options=ConversionOptions(content="auto"),
        extraction_callback=decisions.append,
    )
    link_md = to_markdown(
        link_html,
        options=ConversionOptions(content="dom"),
        extraction_callback=decisions.append,
    )

    assert "Site name" in short_md
    assert "Page context outside candidate" in link_md
    assert decisions[0].selected == "full"
    assert "too short" in decisions[0].reason
    assert decisions[1].selected == "full"
    assert "link density" in decisions[1].reason


def test_readability_content_preserves_technical_structure() -> None:
    decisions = []

    md = to_markdown(
        read_fixture("extractor_technical.html"),
        options=ConversionOptions(content="readability"),
        extraction_callback=decisions.append,
    )

    assert "# Client configuration" in md
    assert '```python\nclient = Client(timeout=30)' in md
    assert "Documentation menu" not in md
    assert decisions[0].selected == "readability"


def test_readability_falls_back_to_full_when_all_candidates_are_short() -> None:
    decisions = []
    html = "<body><header>Site</header><main><p>Brief.</p></main></body>"

    md = to_markdown(
        html,
        options=ConversionOptions(content="readability"),
        extraction_callback=decisions.append,
    )

    assert "Site" in md
    assert decisions[0].selected == "full"


def test_dom_content_fixture_preserves_article_structure_and_removes_chrome() -> None:
    md = to_markdown(
        read_fixture("content_extraction.html"),
        options=ConversionOptions(content="auto"),
    )

    assert "# Reliable content extraction" in md
    assert '```python\nprint("content remains")\n```' in md
    assert "Global product navigation" not in md
    assert "Recommended products" not in md
    assert "Company links" not in md

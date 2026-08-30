"""記事抽出ライブラリを共通 fixture と指標で比較する。"""

from __future__ import annotations

import json
import statistics
import time
from pathlib import Path

import trafilatura
from bs4 import BeautifulSoup
from readability import Document

FIXTURES = Path(__file__).parents[1] / "tests" / "fixtures"
CASES = {
    "article": ("extractor_article.html", ("Reliable Article Extraction", "second paragraph")),
    "technical": ("extractor_technical.html", ("Client configuration", "client.fetch()")),
    "table": ("extractor_table.html", ("Compatibility matrix", "CPython 3.14")),
}


def _run(name: str, html: str) -> str:
    if name == "trafilatura":
        return trafilatura.extract(
            html, output_format="html", include_images=True, include_tables=True
        ) or ""
    return Document(html).summary(html_partial=True)


def compare(iterations: int = 10) -> dict[str, dict[str, dict[str, object]]]:
    """各抽出器の保持率、構造要素数、実行時間を返す。"""
    report: dict[str, dict[str, dict[str, object]]] = {}
    for case, (filename, markers) in CASES.items():
        html = (FIXTURES / filename).read_text(encoding="utf-8")
        report[case] = {}
        for extractor in ("trafilatura", "readability-lxml"):
            timings: list[float] = []
            output = ""
            for _ in range(iterations):
                started = time.perf_counter()
                output = _run(extractor, html)
                timings.append((time.perf_counter() - started) * 1000)
            soup = BeautifulSoup(output, "html.parser")
            text = soup.get_text(" ", strip=True)
            report[case][extractor] = {
                "marker_retention": sum(marker in output for marker in markers) / len(markers),
                "text_length": len(text),
                "headings": len(soup.find_all(["h1", "h2", "h3"])),
                "code_blocks": len(soup.find_all(["pre", "code"])),
                "tables": len(soup.find_all("table")),
                "images": len(soup.find_all("img")),
                "median_ms": round(statistics.median(timings), 3),
            }
    return report


if __name__ == "__main__":
    print(json.dumps(compare(), ensure_ascii=False, indent=2))

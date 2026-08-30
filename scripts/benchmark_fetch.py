"""Playwright 単発取得のブラウザ起動時間と navigation 時間を計測する。"""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict

from get_md.fetcher import FetchMetrics, fetch


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("url", help="計測対象 URL")
    parser.add_argument("--runs", type=int, default=3, help="実行回数 (default: 3)")
    args = parser.parse_args()
    if args.runs < 1:
        parser.error("--runs must be at least 1")

    results: list[FetchMetrics] = []
    for _ in range(args.runs):
        fetch(args.url, metrics_callback=results.append)

    records = [asdict(result) for result in results]
    records.append(
        {
            "browser_launch_seconds": sum(r.browser_launch_seconds for r in results) / len(results),
            "navigation_seconds": sum(r.navigation_seconds for r in results) / len(results),
            "summary": "mean",
        }
    )
    print(json.dumps(records, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

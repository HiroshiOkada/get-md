"""逐次取得とブラウザ再利用バッチの所要時間を比較する。"""

from __future__ import annotations

import argparse
import asyncio
import json
from time import perf_counter

from get_md.fetcher import FetchRequest, fetch, fetch_many


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("urls", nargs="+", help="計測対象URL（2件以上を推奨）")
    parser.add_argument("--concurrency", type=int, default=4, help="バッチ同時実行数")
    args = parser.parse_args()
    if args.concurrency < 1:
        parser.error("--concurrency must be at least 1")

    sequential_started = perf_counter()
    for url in args.urls:
        fetch(url)
    sequential_seconds = perf_counter() - sequential_started

    batch_started = perf_counter()
    results = asyncio.run(
        fetch_many(
            [FetchRequest(url) for url in args.urls],
            concurrency=args.concurrency,
        )
    )
    batch_seconds = perf_counter() - batch_started
    failures = [result.url for result in results if result.error is not None]
    print(
        json.dumps(
            {
                "url_count": len(args.urls),
                "concurrency": args.concurrency,
                "sequential_seconds": round(sequential_seconds, 3),
                "batch_seconds": round(batch_seconds, 3),
                "speedup": round(sequential_seconds / batch_seconds, 3),
                "failed_urls": failures,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())

# Phase 5 HTTP fast path 実装計画

## チェックリスト

- [x] redirect、文字コード、content type、圧縮に対応する HTTP fetcher と静的 HTML 品質判定を追加する。
- [x] `--fetch auto|http|browser` とバッチの選択・フォールバック処理を追加する。
- [x] 静的 HTML、SPA shell、redirect、文字コード、エラーを含む単体・統合テストを追加する。
- [x] README に取得方式、既定値、フォールバック条件、制約を記載する。
- [x] 全テスト、統合・E2E テスト、実サイトテスト、lint を実行して結果を記録する。

## 検証結果

2026-08-30 に通常テスト（統合・E2E を含む）38件が成功し、live テスト1件は通常実行では
想定どおり skip された。Ruff の全検査も成功した。

`GET_MD_RUN_LIVE_TESTS=1 uv run pytest -m live` も実行したが、YouTube への接続が
`net::ERR_TUNNEL_CONNECTION_FAILED` となった。HTTP fast path が静的応答を採用できず
Playwright へフォールバックした後、ブラウザが対象サイトへ到達する前に失敗しており、
以前のフェーズと同じ実行環境のネットワーク制約である。

その後、YouTube に接続可能な環境（Python 3.14.5）で同じ live テストを実行し、
1件が 7.30 秒で成功した。これにより、HTTP fast path 導入後も自動フォールバックを経由して、
OpenAI の動画一覧からタイトル、視聴回数、公開からの経過時間を取得できることを確認した。

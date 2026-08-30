# HTTP fast path とブラウザフォールバック

## ゴール

静的 HTML は Chromium を起動せず高速に取得し、JavaScript 描画が必要なページだけ既存の
Playwright 経路へ安全にフォールバックできるようにする。

## 完了条件

- HTTP 取得で redirect 後 URL、文字コード、content type、圧縮を扱える。
- CLI から `auto`、`http`、`browser` を明示選択できる。
- `auto` は十分な静的 HTML を採用し、不十分な shell をブラウザで再取得する。
- バッチでも入力順と個別エラー処理を維持し、不要な Chromium 起動を避ける。
- 単体テスト、統合・E2E テスト、実サイトテスト、lint が実行される。

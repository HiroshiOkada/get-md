# Playwright 単発取得の高速化計画

## チェックリスト

- [x] 待機条件、本文安定待機、selector 待機を fetcher と CLI に追加する。
- [x] リソース遮断を追加し、スクリーンショット時に表示用リソースを許可する。
- [x] navigation timeout 時の部分 DOM 取得と strict mode を追加する。
- [x] ローカル fixture の統合テストと単発取得ベンチマークを追加する。
- [x] 単体テスト、統合・E2E テスト、実サイトテスト、lint を実行する。

## 検証結果

2026-08-30 に通常テスト 23 件と lint が成功した。単発取得ベンチマークも data URL に対して
実行し、ブラウザ起動時間と navigation 時間が別々に出力されることを確認した。

実サイトテストは実行したが、YouTube への navigation が
`net::ERR_TUNNEL_CONNECTION_FAILED` となった。Phase 4 と同じくブラウザが対象サイトへ到達する
前の実行環境のネットワーク制約であり、接続可能な環境で再確認する。

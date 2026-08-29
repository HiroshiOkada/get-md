# Markdown 構造保持と出力オプション

## ゴール

`docs/plans/統合改善計画.md` の Phase 1 を完了し、技術文書の構造を保ちながら、
用途に応じてリンク・画像・メタデータの出力を選択できる Markdown 変換を提供する。

## 対象範囲

- 空要素、行末空白、過剰な空行の整理
- fenced code block の言語情報保持
- ページメタデータの抽出と安全な YAML front matter
- リンク・画像ポリシーの変換 API と CLI オプション

## 完了条件

- コードブロックの言語が Markdown のフェンスに保持される。
- title、description、canonical URL、author、published time、language、fetched time を抽出できる。
- front matter は明示指定時だけ付与され、特殊文字を含む値も安全な YAML になる。
- リンクと画像を用途別に保持、テキスト化、除去できる。
- 従来相当の出力を既定値で維持する。
- 単体テスト、統合テスト、E2E テストと lint が成功する。

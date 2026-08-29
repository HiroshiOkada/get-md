# OpenCode による改善アイデア

`get-md` の現状実装(`src/get_md/fetcher.py`, `converter.py`, `cli.py`)を分析し、
**速度** と **Markdown の意味のある品質** の両面から改善案を整理した。

---

## 1. 速度の改善

### 1-1. 不要リソースのブロック(効果: 大 / 難易度: 低)

現在はページ内の全リソース(画像・フォント・広告・解析スクリプト等)を
ロードしてから `page.content()` を取得している。
Markdown 変換に不要なリソースを route で遮断すると読み込みが大幅に速くなる。

```python
def _block(route):
    if route.request.resource_type in {"image", "font", "media"}:
        return route.abort()
    return route.continue_()

page.route("**/*", _block)
```

- 画像・Web フォント・動画は Markdown に原則不要
- `--assets` フラグで無効化できるようにすると柔軟

### 1-2. 固定待機(`--wait`)から「準備完了の検知」へ(効果: 大 / 難易度: 中)

`page.wait_for_timeout(wait * 1000)` は、遅いページでは足りず、
速いページでは無駄な時間待ってしまう。

- `wait_until="networkidle"`(または `domcontentloaded`)を `goto` に渡す
- `page.wait_for_load_state("networkidle")` を併用し、
  ネットワークが静かになった時点で即取得
- さらに特定セレクタの描画完了を待つ `--wait-for SELECTOR` オプションを追加
  (SPA の「本文コンテナ」を待つのに有効)

### 1-3. 軽量ヘッドレスシェルの利用(効果: 中 / 難易度: 低)

Playwright は `chromium-headless-shell` チャンネルを提供しており、
ヘッドレス専用バイナリは通常の Chromium より起動・実行が速い。

```python
p.chromium.launch(headless=True, channel="chromium-headless-shell")
```

### 1-4. ブラウザ起動コストの削減(効果: 大 / 難易度: 中〜高)

Chromium の起動は毎回 0.5〜2 秒程度かかる。

- **persistent context の検討**: `launch_persistent_context()` で
  プロファイルを再利用しキャッシュを効かせる
- **常駐モード**: `get-md --serve` でブラウザを起動し続け、
  後続の呼び出しを速くする(Unix socket / ローカル HTTP で受け付ける)
- 複数 URL を一度に渡す `get-md URL1 URL2 ...` をサポートし、
  1 つのブラウザ・複数タブで並列処理(自然なバッチ化)

### 1-5. タイムアウト時の部分取得(効果: 中 / 難易度: 低)

ナビゲーションがタイムアウトしても、読み込み済み DOM から
Markdown を取得できればユーザーは再試行せず済む。
`goto` がタイムアウトしても `page.content()` を試みる fallback を追加
(`--strict` で厳格モードに切り替え可能に)。

---

## 2. Markdown の品質改善(「意味のある」出力)

### 2-1. 本文抽出(Readability)(効果: 特大 / 難易度: 中)

最大の課題。現状は `<body>` 全体を変換するため、
ナビゲーション・フッター・サイドバー・広告・関連記事がすべて混ざる。

- [`trafilatura`](https://github.com/adbar/trafilatura) または
  [`readability-lxml`](https://github.com/buriy/python-readability) で
  本文ノードだけを抽出してから `markdownify` に渡す
-抽出失敗時は現行動作(body 全体)に fallback
- `--full` オプションで従来通りの全文出力も選べるように

```
html → (trafilatura で本文抽出) → markdownify → Markdown
```

これだけで出力の「意味密度」が劇的に変わる。**最優先**。

### 2-2. YAML フロントマターの付与(効果: 大 / 難易度: 低)

下流(LLM への入力、Obsidian など)での利用価値が高まる。

```markdown
---
title: <title タグ or h1>
url: https://example.com/page
fetched_at: 2026-08-30T07:30:00Z
---
```

`page.title()` は Playwright 側で取得可能。`--no-front-matter` で無効化。

### 2-3. 非表示要素の除去(効果: 大 / 難易度: 中)

`display: none`・`visibility: hidden`・`aria-hidden="true"` の要素は
ユーザーに見えていないのに Markdown に混入する(モーダル、隠しメニュー等)。

```python
hidden = soup.select('[style*="display:none"], [style*="display: none"], '
                    '[aria-hidden="true"], [hidden]')
for tag in hidden:
    tag.decompose()
```

計算済みスタイルが必要な場合は Playwright 側で
`page.eval_on_selector_all()` を使って `data-get-md-hidden` 属性を付与する。

### 2-4. 相対 URL の絶対化(効果: 大 / 難易度: 低)

変換後の Markdown では `href="/docs/foo"` のような相対リンクや
`src="/img/a.png"` がページ閲覧コンテキストを失って無意味になる。
`urljoin(url, ...)` でベース URL に対して絶対化してから変換する。

### 2-5. ノイズ要素の除去(効果: 中 / 難易度: 低)

ヒューリスティックな除去でノイズを減らせる。

- `role="dialog"`, `role="navigation"`, `role="banner"`, `role="contentinfo"`
- `nav`, `footer`, `aside`(本文抽出が `--full` のときのみ)
- cookie 同意バナー(`id`/`class` に `cookie`, `consent`, `gdpr` を含む)
- トラッキングピクセル(`width="1" height="1"` の画像、alt 空の画像)

### 2-6. リンク・画像のポリシー option(効果: 中 / 難易度: 低)

用途によって欲しい形が違うためフラグ化する。

- `--no-links`: リンクをテキスト化(LLM 入力向けにノイズ激減)
- `--no-images`: 画像を除去
- `--image-alt-only`: 画像を `![alt](url)` ではなく alt の説明文に

### 2-7. コードブロックの改良(効果: 中 / 難易度: 中)

- `<pre><code class="language-xxx">` の言語情報を
  ```` ```python ```` のように保持
- GitHub 等の `data-lang` / `data-language` 属性にも対応
- インラインコードとブロックコードの区別を正確に(markdownify の既定は甘い)

### 2-8. テーブルの GFM 対応(効果: 中 / 難易度: 中)

`markdownify` のテーブル変換は列幅のパディングがなく読みにくい。
変換後のテーブルを検出してパイプ区切りを整形、
`<th>` からヘッダ行を正しく生成する(複雑なネストテーブルは HTML 保持も検討)。

### 2-9. 出力の整形オプション(効果: 小〜中 / 難易度: 低)

- `--wrap N`: 段落を N 文字で折り返し(diff フレンドリーに)
- 空の見出し・空のリンク・連続する同一リンクの重複除去
- `#` 見出しが存在しない場合、`<title>` を `# ` として先頭に追加

---

## 3. その他の改善

| 案 | 内容 |
| --- | --- |
| 複数 URL 対応 | 1 ブラウザで複数タブ並列フェッチ(`-o` はディレクトリ指定に) |
| キャッシュ | URL + 日付をキーに結果をキャッシュ(`--no-cache` で無効化) |
| stderr への進捗表示 | 現在 `saved: ...` は stdout。stdout が Markdown と混ざる設計のため、`-o` 未指定時のメッセージは stderr に統一するとパイプしやすい |
| テスト | `converter.py` の純粋関数はテストしやすい。`pytest` を dev 依存に追加し、HTML → MD のスナップショットテストを整備 |
| async 化 | playwright の async API + asyncio でバッチフェッチを効率化 |

---

## 4. 優先順位まとめ

| 優先 | 案 | 狙い |
| --- | --- | --- |
| ★★★ | 2-1 本文抽出(trafilatura) | 意味のある Markdown の核心 |
| ★★★ | 1-1 リソースブロック | 速度向上の低コストな打ち手 |
| ★★★ | 2-4 相対 URL の絶対化 | 正しさの低コスト改善 |
| ★★☆ | 2-2 フロントマター | 下流利用価値向上 |
| ★★☆ | 1-2 networkidle 待機 | 無駄待ち削減 |
| ★★☆ | 2-3 非表示要素除去 | ノイズ削減 |
| ★★☆ | 1-4 複数 URL・常駐 | バッチ利用時の速度 |
| ★☆☆ | 1-3 headless shell / 2-6〜2-9 | 仕上げ・快適性 |

# 🎓 授業構想キャンバス

AIと対話しながら授業を練り上げ、単元計画・本時案・ワークシート・小テスト・
板書用スライド構成などを出力できる Streamlit アプリです。
（旧「単元計画AI自動生成システム」の後継・拡張版）

## 特徴

- **対話型キャンバス**: チャットでAIと壁打ちしながら構想を練り、
  まとまった段階でボタン一つで成果物を生成（NotebookLMのCanvasに近い体験）
- **クイックスタート**: 初めて使う先生でも迷わないよう、よくある相談の
  きっかけをボタンで用意（単元をゼロから考える／教材をもとに考える 等）
- **複数AIプロバイダー対応**: Google Gemini / Anthropic Claude / OpenAI を
  切り替えて使用可能（資料読み込みはGemini、対話相談はClaude、など使い分け可）
- **複数の出力タイプ**: 単元計画・本時案・ワークシート・振り返り/小テスト・
  板書用スライド構成・個別最適化ワークシート（基礎/標準/発展の3段階）・
  学級通信/保護者向けお便り。小テストは生徒配布用（解答なし）/教師用（解答つき）を
  切り替え可能
- **配慮版（ふりがな）出力**: ワークシート/小テストの印刷用PDFで、
  漢字に読み仮名を自動付与した特別支援・日本語指導向けの配慮版を出力可能
- **複数AIによる品質ブラッシュアップ**: 生成した成果物を、最初とは別のAI
  （プロバイダー/モデル）に「厳しい指導主事」役でレビュー・推敲させ、
  新学習指導要領との整合性や表現の具体性を底上げできる
- **教材の統合管理**: 教科書画像・PDF・参考URL（実際に本文取得）を
  「教材」として登録し、対話の中でいつでも参照
- **セッションの保存・共有**: 相談内容と成果物をJSONファイルとして
  書き出し/読み込みでき、後日の再開や同僚間でのたたき台共有に使える
- **エラー時のわかりやすい案内**: APIキー不備・利用上限超過など、
  非エンジニアの先生にも分かる日本語メッセージと再試行ボタンを表示
- **著作権配慮**: システムプロンプトに要約・出典明記を常駐指示し、
  生成物には注記を自動挿入

## セットアップ

```bash
pip install -r requirements.txt
streamlit run app.py
```

## ディレクトリ構成

```
app.py                      ... メインページ（対話型キャンバス、2ペイン構成）
pages/
  2_教材ライブラリ.py         ... 複数教員での共有教材ライブラリ（Supabase連携）
sql/
  schema.sql                 ... 共有ライブラリ用のテーブル定義（Supabaseで実行）
core/
  ai/
    base.py                ... AIプロバイダーの共通インターフェース
    gemini_provider.py
    claude_provider.py
    openai_provider.py
    router.py               ... プロバイダー選択・フォールバック管理
  prompts.py                ... システムプロンプト・成果物別テンプレート・クイックスタート
  sources.py                 ... URL取得・PDF/画像の教材化
  session_store.py           ... 会話履歴・教材・成果物の状態管理
  session_io.py              ... セッションのJSON書き出し/読み込み（保存・共有用）
  db.py                       ... 共有教材ライブラリ（Supabase）とのやり取り
  refine.py                   ... 複数AI横断の品質ブラッシュアップ用プロンプト
  api_keys.py                ... 個人/学校共有APIキーの解決
  errors.py                  ... エラーメッセージの日本語変換
  md_parse.py                ... Markdown（見出し・表）の構造化パーサー
exporters/
  docx_builder.py            ... Markdown → Word変換（表・コードブロック対応）
  worksheet_pdf.py           ... ワークシート/小テストの印刷用PDF（記入欄・解答有無・ふりがな切替）
  pptx_builder.py             ... 板書用スライドのPowerPoint直接出力
```

## APIキーの取得

- Gemini: https://aistudio.google.com/app/apikey
- Claude: https://console.anthropic.com/
- OpenAI: https://platform.openai.com/api-keys

キーはブラウザセッション内でのみ使用され、サーバーに保存されません。

## 印刷用PDF・pptx出力について

- **ワークシート/小テスト**: 記入欄つきの印刷用PDFを出力できます。小テストは
  「生徒配布用（解答なし）」「教師用（解答つき）」を切り替えられるので、
  誤って解答を配布してしまう事故を防げます。
- **板書用スライド**: そのままPowerPoint(.pptx)として出力できます。
- 日本語フォントは reportlab / python-pptx の標準機能を利用しており、
  フォントファイルの同梱は不要です。

## 学校での共有運用（複数の先生に使ってもらう場合）

個人のAPIキーを毎回入力させたくない場合は、Streamlit Cloud の
「Settings → Secrets」に以下の形式で共有キーを設定してください。
設定すると、サイドバーに「学校共有のAPIキーを使う」という選択肢が
自動的に表示されます。

```toml
[shared_api_keys]
gemini = "your-gemini-api-key"
claude = "your-claude-api-key"
openai = "your-openai-api-key"
```

**注意**: 共有キーを使うと、全員分の利用量が1つのアカウントに合算されます。
Google AI Studio 等でクォータ（利用上限）を設定しておくことを推奨します。
不特定多数がアクセスできるURLで運用する場合は、Streamlit Cloud の
アクセス制限機能（Viewer認証）と併用することをおすすめします。

## 複数教員での共有ライブラリを使う（外部データベース連携）

「教材ライブラリ」ページでは、先生方が登録した教材を学年・教科で検索し、
授業構想キャンバスに取り込んで使えます。Streamlit Cloud自体はサーバー側の
保存領域を持たないため、無料で使える外部データベース [Supabase](https://supabase.com/)
と連携する構成にしています。

### セットアップ手順（管理担当の先生が一度だけ行う作業）

1. [supabase.com](https://supabase.com/) でアカウントを作成し、新しいプロジェクトを作成する
2. プロジェクトの「SQL Editor」を開き、`sql/schema.sql` の内容をそのまま実行する
   （教材ライブラリ用のテーブルと、学校内利用を想定した簡易アクセス設定が作られます）
3. 左メニュー「Storage」→「New bucket」で、名前を `materials` にしてバケットを作成する
   （Public bucketはオフのままでOK）
4. 作成したバケットの「Policies」で、アップロード・ダウンロードを許可するポリシーを追加する
   （学校内限定の簡易運用を想定しています。詳細は `sql/schema.sql` 内のコメントを参照）
5. プロジェクトの「Settings → API」から `Project URL` と `anon public key` を確認する
6. Streamlit Cloudの「Settings → Secrets」に以下を追加する:

```toml
[supabase]
url = "https://xxxxxxxx.supabase.co"
key = "your-anon-public-key"
```

設定が完了すると、アプリのサイドバーに表示される「教材ライブラリ」ページが
自動的に有効になります（未設定の場合はセットアップ案内が表示されるだけで、
アプリ本体の動作には影響しません）。

### 使い方（先生方の日常利用）

- **登録**: 「教材ライブラリ」ページの「このセッションの教材を登録する」タブから、
  授業構想キャンバスでアップロード済みの教材に学年・教科・単元名のタグをつけて登録
- **検索・利用**: 「探す・取り込む」タブで学年・教科から絞り込み、
  「この教材を使う」ボタンで自分のセッションに取り込んで相談を開始

### セキュリティ上の注意

`sql/schema.sql` のアクセス設定は、学校内の閉じた利用を想定した簡易的なものです
（誰でも読み書きできる設定）。より厳密な運用（教員ごとのログイン等）が必要な場合は、
Supabase Authの導入を検討してください。

## GitHubへの登録・Streamlit Cloudへのデプロイ

このリポジトリはそのまま `git init` してGitHubにプッシュできる状態になっています。
APIキーは `.streamlit/secrets.toml`（Git管理対象外）にのみ書くため、
公開リポジトリにしても鍵が漏れる心配はありません。

```bash
git init
git add .
git commit -m "Initial commit: 授業構想キャンバス"
git branch -M main
git remote add origin https://github.com/<あなたのアカウント>/<リポジトリ名>.git
git push -u origin main
```

ローカルで動作確認する場合は、`.streamlit/secrets.toml.example` を
`.streamlit/secrets.toml` としてコピーし、必要なキーを書き込んでください。

```bash
cp .streamlit/secrets.toml.example .streamlit/secrets.toml
# secrets.toml を編集後
pip install -r requirements.txt
streamlit run app.py
```

Streamlit Cloudへのデプロイ手順は、前述の「学校での共有運用」セクションおよび
share.streamlit.io の「New app」からこのリポジトリを選択する手順に従ってください。

## ライセンス

MIT License（`LICENSE` ファイルを参照）

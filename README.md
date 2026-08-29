# 🎓 授業構想キャンバス

AIと対話しながら授業を練り上げ、単元計画・本時案・ワークシート・小テスト・
板書用スライド構成などを出力できる Streamlit アプリです。
（旧「単元計画AI自動生成システム」の後継・拡張版）

## 特徴

- **対話型キャンバス**: チャットでAIと壁打ちしながら構想を練り、
  まとまった段階でボタン一つで成果物を生成（NotebookLMのCanvasに近い体験）
- **クイックスタート**: 初めて使う先生でも迷わないよう、よくある相談の
  きっかけをボタンで用意（単元をゼロから考える／教材をもとに考える 等）
- **事前情報フォーム**: 学年・教科・単元名・総時数・児童生徒の実態などを
  最初にまとめて入力でき、AIが同じ質問を繰り返さずに具体的な提案から
  始められる
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
- **単元マップ・板書イメージの可視化**: 単元計画から学習の流れを図解した
  「単元マップ」、本時案の板書計画から黒板風のビジュアルを生成できる
  （追加のシステムライブラリ不要、SVGとして表示・ダウンロード可能）
- **バージョン比較**: 同じ成果物について、切り口の異なる「別パターン」を
  もう1つ生成し、並べて見比べてから良い方を採用できる
- **英語版の自動生成**: ALT・外国籍家庭向けに、成果物を自然な英語に
  書き直した版をワンクリックで追加生成できる
- **管理職の確認・承認フロー**: 成果物を管理職に確認依頼として送信し、
  コメント付きで承認/差し戻しができる（共有教材ライブラリと同じ
  Supabaseプロジェクトを利用）
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
app.py                      ... エントリーポイント（ページナビゲーションの定義）
pages/
  canvas.py                  ... 授業構想キャンバス（対話型メイン画面）
  library.py                  ... 複数教員での共有教材ライブラリ（Supabase連携）
  approval.py                  ... 管理職の確認・承認フロー（Supabase連携）
sql/
  schema.sql                 ... 共有ライブラリ・承認フロー用のテーブル定義（Supabaseで実行）
core/
  ai/
    base.py                ... AIプロバイダーの共通インターフェース
    gemini_provider.py
    claude_provider.py
    openai_provider.py
    router.py               ... プロバイダー選択・フォールバック管理
  prompts.py                ... システムプロンプト・成果物別テンプレート・クイックスタート・別パターン生成
  intake.py                  ... 事前情報フォームの項目定義とプロンプト整形
  translate.py                ... 英語版生成用プロンプト
  sources.py                 ... URL取得・PDF/画像の教材化
  session_store.py           ... 会話履歴・教材・成果物の状態管理（バージョン管理含む）
  session_io.py              ... セッションのJSON書き出し/読み込み（保存・共有用）
  db.py                       ... 共有教材ライブラリ・承認フロー（Supabase）とのやり取り
  refine.py                   ... 複数AI横断の品質ブラッシュアップ用プロンプト
  api_keys.py                ... 個人/学校共有APIキーの解決
  errors.py                  ... エラーメッセージの日本語変換
  md_parse.py                ... Markdown（見出し・表）の構造化パーサー
exporters/
  docx_builder.py            ... Markdown → Word変換（表・コードブロック対応）
  worksheet_pdf.py           ... ワークシート/小テストの印刷用PDF（記入欄・解答有無・ふりがな切替）
  pptx_builder.py             ... 板書用スライドのPowerPoint直接出力
  diagram_builder.py          ... 単元マップ・板書イメージのSVG生成
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
   （教材ライブラリ・確認承認フロー用のテーブルと、学校内利用を想定した簡易アクセス設定が作られます）
3. 左メニュー「Storage」→「New bucket」で、名前を `materials` にしてバケットを作成する
   （Public bucketはオフのままでOK）
4. 作成したバケットの「Policies」タブで「New policy」→「For full customization」を選び、
   SELECT・INSERT・UPDATE・DELETEすべてを許可するポリシー（USING/WITH CHECKに `true`）を追加する
   （学校内限定の簡易運用を想定しています）
5. 左メニュー「Integrations」→「Data API」を開き、「API URL」をコピーする
   （`https://xxxxxxxx.supabase.co/rest/v1/` の形。末尾の `/rest/v1/` は使わないので後で削除します）
6. 左メニュー「API Keys」を開き、**「Legacy API keys」**を選んで、`anon` というキー
   （`eyJ...` から始まる長い文字列）をコピーする

   ⚠️ **注意**: Supabaseの新しいAPI Keys画面では「Publishable key」（`sb_publishable_...`という短い形式）
   が前面に出ていますが、これは本アプリが使っているライブラリのバージョンでは正しく認識できず
   「Invalid API key」エラーになることがあります。必ず「Legacy API keys」から取得できる
   **`anon`（`eyJ...`形式）** の方を使ってください。
7. Streamlit Cloudの「Settings → Secrets」に以下を追加する（手順5でコピーしたURLは
   末尾の `/rest/v1/` を削除してから使ってください）:

```toml
[shared_api_keys]
gemini = ""
claude = ""
openai = ""

[supabase]
url = "https://xxxxxxxx.supabase.co"
key = "eyJ... から始まるanonキー"
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

## 管理職の確認・承認フローを使う

「確認・承認」ページでは、先生が作成した成果物を配布前に管理職が確認し、
コメント付きで承認/差し戻しができます。共有教材ライブラリと同じSupabase
プロジェクトを使い回せます（`sql/schema.sql` に承認フロー用のテーブル定義も
含まれているため、共有ライブラリのセットアップ時に一緒に実行済みであれば
追加設定は不要です）。

使い方は、授業構想キャンバスの成果物パネルにある「📤 管理職に確認を依頼」
ボタンから直接送信するか、「確認・承認」ページの「確認を依頼する」タブから
内容を貼り付けて送信します。管理職は「確認待ち一覧」タブで内容を確認し、
承認またはコメント付きで差し戻せます。

**注意**: このアプリには認証機能がないため、URLを知っていれば誰でも
「確認・承認」ページを操作できます。学校内の閉じた利用を前提とした
簡易的な仕組みである点にご留意ください。

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

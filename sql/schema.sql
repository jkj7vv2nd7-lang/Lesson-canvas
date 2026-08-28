-- 授業構想キャンバス: 共有教材ライブラリのテーブル定義
-- Supabaseプロジェクトの「SQL Editor」でこのファイルの内容を実行してください。

create table if not exists materials_library (
  id uuid primary key default gen_random_uuid(),
  teacher_name text not null,
  grade text default '',
  subject text default '',
  unit_name text default '',
  material_name text not null,
  kind text not null,               -- 'pdf' / 'image' / 'url'
  mime_type text default '',
  extracted_text text default '',
  source_url text default '',
  storage_path text,                -- Supabase Storage上のパス（urlの場合はnull）
  created_at timestamptz not null default now()
);

-- 学年・教科での絞り込みを高速化
create index if not exists idx_materials_library_grade on materials_library (grade);
create index if not exists idx_materials_library_subject on materials_library (subject);

-- ------------------------------------------------------------
-- Row Level Security（学校内利用の簡易設定）
-- ------------------------------------------------------------
-- 学校内の閉じた利用を想定し、匿名キー(anon key)からの読み書きを許可する
-- シンプルな設定にしています。より厳密なアクセス制御をしたい場合は、
-- Supabase Authでの教員ログインを導入し、ポリシーを teacher_id ベースに
-- 変更することを検討してください。

alter table materials_library enable row level security;

create policy "Allow read for all" on materials_library
  for select using (true);

create policy "Allow insert for all" on materials_library
  for insert with check (true);

create policy "Allow delete for all" on materials_library
  for delete using (true);

-- ------------------------------------------------------------
-- Storageバケットの作成（SQLではなくダッシュボードから行います）
-- ------------------------------------------------------------
-- 1. 左メニュー「Storage」→「New bucket」
-- 2. Name: materials
-- 3. Public bucket: オフのままでOK（アプリのAPIキー経由でのみアクセス）
-- 4. 作成後、Storageの「Policies」で以下と同様に
--    「全員がアップロード/ダウンロードできる」ポリシーを追加してください
--    （学校内限定利用を想定した簡易設定です）

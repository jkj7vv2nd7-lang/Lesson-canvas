"""
複数教員での教材ライブラリ共有を実現するための外部データベース連携層。

Streamlit Cloudはアプリのサーバー側に永続ストレージを持たないため、
教材のメタ情報は Supabase の Postgres テーブルに、
画像/PDFの実体は Supabase Storage のバケットに保存する。

セットアップ方法は README.md の「複数教員での共有ライブラリを使う」を参照。
未設定でもアプリ自体は動作し、ライブラリ機能だけが非表示になる。
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

import streamlit as st

TABLE_NAME = "materials_library"
BUCKET_NAME = "materials"


@dataclass
class LibraryMaterial:
    id: str
    teacher_name: str
    grade: str
    subject: str
    unit_name: str
    material_name: str
    kind: str              # "pdf" / "image" / "url"
    mime_type: str
    extracted_text: str
    source_url: str
    storage_path: str | None   # Supabase Storageのパス（url由来の場合はNone）
    created_at: str


class LibraryError(Exception):
    pass


def is_library_configured() -> bool:
    """Secretsに接続情報が設定されているかどうか。"""
    try:
        section = st.secrets.get("supabase", {})
        return bool(section.get("url")) and bool(section.get("key"))
    except Exception:
        return False


@st.cache_resource
def _get_client():
    from supabase import create_client
    section = st.secrets["supabase"]
    return create_client(section["url"], section["key"])


def list_materials(*, grade: str = "", subject: str = "") -> list[LibraryMaterial]:
    """条件（学年・教科）で絞り込んで共有ライブラリの教材一覧を取得する。空文字は絞り込みなし。"""
    try:
        client = _get_client()
        query = client.table(TABLE_NAME).select("*").order("created_at", desc=True)
        if grade:
            query = query.eq("grade", grade)
        if subject:
            query = query.eq("subject", subject)
        res = query.execute()
        return [LibraryMaterial(**row) for row in res.data]
    except Exception as e:
        raise LibraryError(f"教材ライブラリの取得に失敗しました: {e}") from e


def add_material_to_library(
    *,
    teacher_name: str,
    grade: str,
    subject: str,
    unit_name: str,
    material_name: str,
    kind: str,
    mime_type: str,
    extracted_text: str,
    source_url: str = "",
    raw_bytes: bytes | None = None,
) -> None:
    """教材1件を共有ライブラリに登録する。raw_bytesがあればStorageにもアップロードする。"""
    try:
        client = _get_client()
        storage_path = None

        if raw_bytes is not None:
            storage_path = f"{teacher_name}/{datetime.now(timezone.utc).timestamp()}_{material_name}"
            client.storage.from_(BUCKET_NAME).upload(
                storage_path, raw_bytes, {"content-type": mime_type}
            )

        client.table(TABLE_NAME).insert({
            "teacher_name": teacher_name,
            "grade": grade,
            "subject": subject,
            "unit_name": unit_name,
            "material_name": material_name,
            "kind": kind,
            "mime_type": mime_type,
            "extracted_text": extracted_text,
            "source_url": source_url,
            "storage_path": storage_path,
        }).execute()
    except Exception as e:
        raise LibraryError(f"教材ライブラリへの登録に失敗しました: {e}") from e


def download_material_bytes(storage_path: str) -> bytes:
    """Storageから教材の実体（画像/PDF）をダウンロードする。"""
    try:
        client = _get_client()
        return client.storage.from_(BUCKET_NAME).download(storage_path)
    except Exception as e:
        raise LibraryError(f"教材データの取得に失敗しました: {e}") from e


def delete_material(material_id: str, storage_path: str | None) -> None:
    """自分が登録した教材を削除する。"""
    try:
        client = _get_client()
        if storage_path:
            client.storage.from_(BUCKET_NAME).remove([storage_path])
        client.table(TABLE_NAME).delete().eq("id", material_id).execute()
    except Exception as e:
        raise LibraryError(f"教材の削除に失敗しました: {e}") from e


def list_grades_and_subjects() -> tuple[list[str], list[str]]:
    """絞り込み用に、登録済みの学年・教科の一覧を取得する（重複除去）。"""
    try:
        client = _get_client()
        res = client.table(TABLE_NAME).select("grade, subject").execute()
        grades = sorted({row["grade"] for row in res.data if row["grade"]})
        subjects = sorted({row["subject"] for row in res.data if row["subject"]})
        return grades, subjects
    except Exception:
        return [], []

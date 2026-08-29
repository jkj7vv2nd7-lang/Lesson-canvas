"""
共有教材ライブラリ — 複数の先生が登録した教材を検索し、
「授業構想キャンバス」のセッションに取り込んで使えるページ。

外部データベース(Supabase)に接続して動作する。未設定の場合は
セットアップ手順を案内する。
"""

from __future__ import annotations

import sys
from pathlib import Path

# pages/ 配下からでも core/ を import できるようにする
sys.path.append(str(Path(__file__).resolve().parent.parent))

import streamlit as st

from core.db import (
    LibraryError,
    add_material_to_library,
    delete_material,
    download_material_bytes,
    is_library_configured,
    list_grades_and_subjects,
    list_materials,
)
from core.session_store import add_material, init_session
from core.sources import Material

init_session()

st.title("📚 共有教材ライブラリ")
st.caption("学校の先生方が登録した教材を検索し、授業構想キャンバスに取り込めます。")

if not is_library_configured():
    st.warning(
        "共有ライブラリはまだ設定されていません。管理担当の先生に、"
        "README.md の「複数教員での共有ライブラリを使う」の手順で"
        "Supabaseの設定をしてもらってください。"
    )
    st.stop()

tab_browse, tab_add = st.tabs(["🔍 探す・取り込む", "📤 このセッションの教材を登録する"])

# ==========================================
# タブ1: 探す・取り込む
# ==========================================
with tab_browse:
    grades, subjects = list_grades_and_subjects()

    filter_cols = st.columns(2)
    with filter_cols[0]:
        selected_grade = st.selectbox("学年で絞り込み", options=["すべて"] + grades)
    with filter_cols[1]:
        selected_subject = st.selectbox("教科で絞り込み", options=["すべて"] + subjects)

    try:
        materials = list_materials(
            grade="" if selected_grade == "すべて" else selected_grade,
            subject="" if selected_subject == "すべて" else selected_subject,
        )
    except LibraryError as e:
        st.error(str(e))
        materials = []

    if not materials:
        st.info("該当する教材がまだ登録されていません。")

    for m in materials:
        with st.container(border=True):
            cols = st.columns([3, 1])
            with cols[0]:
                st.markdown(f"**{m.material_name}**（{m.kind}）")
                meta_bits = [b for b in [m.grade, m.subject, m.unit_name] if b]
                if meta_bits:
                    st.caption(" ／ ".join(meta_bits) + f" ・登録者: {m.teacher_name}")
                if m.extracted_text:
                    preview = m.extracted_text[:150]
                    st.caption(f"📄 {preview}{'…' if len(m.extracted_text) > 150 else ''}")
                if m.source_url:
                    st.caption(f"🔗 {m.source_url}")
            with cols[1]:
                if st.button("この教材を使う", key=f"use_{m.id}", use_container_width=True):
                    try:
                        raw_bytes = None
                        if m.storage_path:
                            with st.spinner("取得中..."):
                                raw_bytes = download_material_bytes(m.storage_path)
                        add_material(Material(
                            name=m.material_name,
                            kind=m.kind,
                            mime_type=m.mime_type or "text/plain",
                            data=raw_bytes,
                            extracted_text=m.extracted_text,
                            source=m.source_url,
                        ))
                        st.success("授業構想キャンバスの教材に追加しました。左のメニューから戻って使えます。")
                    except LibraryError as e:
                        st.error(str(e))

                if st.button("🗑 削除", key=f"del_{m.id}", use_container_width=True):
                    try:
                        delete_material(m.id, m.storage_path)
                        st.success("削除しました。")
                        st.rerun()
                    except LibraryError as e:
                        st.error(str(e))

# ==========================================
# タブ2: 登録する
# ==========================================
with tab_add:
    st.caption(
        "「授業構想キャンバス」でアップロード済みの教材、または新しくファイルを選んで、"
        "共有ライブラリに登録できます。登録すると他の先生も検索・利用できるようになります。"
    )

    teacher_name = st.text_input("お名前（登録者として表示されます）", key="lib_teacher_name")
    reg_cols = st.columns(3)
    with reg_cols[0]:
        reg_grade = st.text_input("学年（例: 4年）", key="lib_grade")
    with reg_cols[1]:
        reg_subject = st.text_input("教科（例: 算数）", key="lib_subject")
    with reg_cols[2]:
        reg_unit = st.text_input("単元名（例: がい数）", key="lib_unit")

    st.markdown("##### 現在のセッションの教材から登録")
    session_materials = st.session_state.get("materials", [])
    if not session_materials:
        st.caption("授業構想キャンバスでアップロード済みの教材はまだありません。")
    for i, sm in enumerate(session_materials):
        with st.container(border=True):
            st.markdown(f"**{sm.name}**（{sm.kind}）")
            if st.button("この内容で共有ライブラリに登録", key=f"reg_{i}", disabled=not teacher_name):
                try:
                    add_material_to_library(
                        teacher_name=teacher_name,
                        grade=reg_grade,
                        subject=reg_subject,
                        unit_name=reg_unit,
                        material_name=sm.name,
                        kind=sm.kind,
                        mime_type=sm.mime_type,
                        extracted_text=sm.extracted_text,
                        source_url=sm.source,
                        raw_bytes=sm.data,
                    )
                    st.success("共有ライブラリに登録しました。")
                except LibraryError as e:
                    st.error(str(e))
    if session_materials and not teacher_name:
        st.caption("⚠️ 登録するにはお名前を入力してください。")

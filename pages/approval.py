"""
管理職の確認・承認フロー — 先生が提出した成果物を、管理職が確認し
コメント・承認/差し戻しを行うページ。

外部データベース(Supabase)に接続して動作する。未設定の場合は
セットアップ手順を案内する（教材ライブラリと同じSupabaseプロジェクトを
利用できる。sql/schema.sql に追加のテーブル定義がある）。

注意: このアプリには認証機能がないため、「管理職タブ」も含めて
URLを知っていれば誰でも操作できる。学校内の閉じた利用を前提とした
簡易的な仕組みである点に留意すること。
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent))

import streamlit as st

from core.db import (
    LibraryError,
    is_library_configured,
    list_reviews,
    submit_for_review,
    update_review_status,
)
from core.session_store import init_session

st.set_page_config(page_title="確認・承認", page_icon="✅", layout="wide")
init_session()

st.title("✅ 確認・承認")
st.caption("先生方が提出した成果物を、管理職が確認・コメントできます。")

if not is_library_configured():
    st.warning(
        "確認・承認フローはまだ設定されていません。管理担当の先生に、"
        "README.md の「管理職の確認・承認フローを使う」の手順で"
        "Supabaseの設定をしてもらってください。"
    )
    st.stop()

tab_submit, tab_pending, tab_history = st.tabs(
    ["📤 確認を依頼する", "⏳ 確認待ち一覧", "📚 これまでの結果"]
)

# ==========================================
# タブ1: 確認を依頼する
# ==========================================
with tab_submit:
    st.caption(
        "「授業構想キャンバス」で生成した成果物を、テキストとして貼り付けて確認依頼を出せます。"
        "（キャンバス側の成果物パネルにある「📤 管理職に確認を依頼」ボタンからも直接送れます）"
    )
    with st.form("submit_review_form"):
        submitter_name = st.text_input("お名前")
        artifact_label = st.text_input("成果物の名前（例: がい数 単元計画）")
        artifact_type = st.selectbox(
            "種類",
            options=["unit_plan", "lesson_plan", "worksheet", "quiz", "slide_outline",
                     "differentiated_worksheet", "class_newsletter", "other"],
            format_func=lambda k: {
                "unit_plan": "単元計画", "lesson_plan": "本時案", "worksheet": "ワークシート",
                "quiz": "小テスト", "slide_outline": "板書用スライド構成",
                "differentiated_worksheet": "個別最適化ワークシート",
                "class_newsletter": "学級通信", "other": "その他",
            }.get(k, k),
        )
        content_md = st.text_area("内容", height=200)
        submitted = st.form_submit_button("この内容で確認を依頼する", type="primary")

    if submitted:
        if not submitter_name or not artifact_label or not content_md:
            st.warning("お名前・成果物の名前・内容は必須です。")
        else:
            try:
                submit_for_review(
                    submitter_name=submitter_name, artifact_label=artifact_label,
                    artifact_type=artifact_type, content_md=content_md,
                )
                st.success("確認依頼を送信しました。")
            except LibraryError as e:
                st.error(str(e))

# ==========================================
# タブ2: 確認待ち一覧（管理職向け）
# ==========================================
with tab_pending:
    st.caption("管理職の方はこちらから内容を確認し、承認またはコメント付きで差し戻せます。")
    try:
        pending = list_reviews(status="pending")
    except LibraryError as e:
        st.error(str(e))
        pending = []

    if not pending:
        st.info("現在、確認待ちの成果物はありません。")

    for r in pending:
        with st.container(border=True):
            st.markdown(f"**{r.artifact_label}**　提出者: {r.submitter_name}　({r.created_at[:16]})")
            with st.expander("内容を見る"):
                st.markdown(r.content_md)

            reviewer_name = st.text_input("確認者名", key=f"reviewer_{r.id}")
            comment = st.text_area("コメント（任意）", key=f"comment_{r.id}", height=80)
            btn_cols = st.columns(2)
            with btn_cols[0]:
                if st.button("✅ 承認する", key=f"approve_{r.id}", use_container_width=True):
                    if not reviewer_name:
                        st.warning("確認者名を入力してください。")
                    else:
                        try:
                            update_review_status(
                                r.id, status="approved",
                                reviewer_name=reviewer_name, reviewer_comment=comment,
                            )
                            st.success("承認しました。")
                            st.rerun()
                        except LibraryError as e:
                            st.error(str(e))
            with btn_cols[1]:
                if st.button("↩ 差し戻す", key=f"reject_{r.id}", use_container_width=True):
                    if not reviewer_name:
                        st.warning("確認者名を入力してください。")
                    elif not comment:
                        st.warning("差し戻す場合はコメントを入力してください。")
                    else:
                        try:
                            update_review_status(
                                r.id, status="rejected",
                                reviewer_name=reviewer_name, reviewer_comment=comment,
                            )
                            st.success("差し戻しました。")
                            st.rerun()
                        except LibraryError as e:
                            st.error(str(e))

# ==========================================
# タブ3: これまでの結果
# ==========================================
with tab_history:
    filter_name = st.text_input("自分の名前で絞り込む（任意）", key="history_filter")
    try:
        history = list_reviews(submitter_name=filter_name) if filter_name else list_reviews()
    except LibraryError as e:
        st.error(str(e))
        history = []

    status_labels = {"pending": "⏳ 確認待ち", "approved": "✅ 承認済み", "rejected": "↩ 差し戻し"}
    for r in history:
        with st.container(border=True):
            st.markdown(
                f"**{r.artifact_label}**　{status_labels.get(r.status, r.status)}　"
                f"提出者: {r.submitter_name}"
            )
            if r.status != "pending":
                st.caption(f"確認者: {r.reviewer_name}（{(r.reviewed_at or '')[:16]}）")
                if r.reviewer_comment:
                    st.caption(f"コメント: {r.reviewer_comment}")
    if not history:
        st.info("該当する記録がありません。")

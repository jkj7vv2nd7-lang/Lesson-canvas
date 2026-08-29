"""
授業構想キャンバス — AIと対話しながら授業を練り上げ、
本時案・ワークシート・小テスト・スライド構成などを出力するStreamlitアプリ。

画面構成:
  左ペイン: AIとのチャット（壁打ち）
  右ペイン: 生成された成果物（複数タブで管理・編集・ダウンロード）
"""

from __future__ import annotations

import uuid

import streamlit as st

from core.ai.router import AIRouter
from core.api_keys import resolve_api_keys
from core.errors import friendly_error_message
from core.prompts import (
    ARTIFACT_FORMATS,
    CANVAS_SYSTEM_PROMPT,
    QUICK_START_PROMPTS,
    build_artifact_instruction,
)
from core.refine import build_refine_prompt
from core.session_io import SessionImportError, export_session_json, import_session_json
from core.session_store import (
    Artifact,
    add_artifact,
    add_material,
    add_message,
    has_pending_user_turn,
    init_session,
    reset_conversation,
)
from core.sources import fetch_url_material, image_to_material, materials_to_context_text, pdf_to_material
from exporters.docx_builder import clean_html_tags, markdown_to_docx, sanitize_filename
from exporters.pptx_builder import build_slide_outline_pptx
from exporters.worksheet_pdf import build_worksheet_pdf

# 成果物タイプごとに、Word以外にどの追加出力を出せるか
EXTRA_EXPORTS = {
    "worksheet": "print_pdf",
    "quiz": "print_pdf",
    "slide_outline": "pptx",
    "differentiated_worksheet": "print_pdf",
}

FOOTER_NOTE = (
    "本資料は教材・参考資料をもとにAIが要約・作成したものです。"
    "一次資料の著作権にご留意の上、実際の配布・使用前に内容をご確認ください。"
)

init_session()

# ==========================================
# サイドバー: APIキー・モデル設定・教材アップロード
# ==========================================
with st.sidebar:
    st.title("⚙️ 設定")

    with st.expander("🔑 APIキー", expanded=True):
        resolved_keys = resolve_api_keys()

    router = AIRouter(resolved_keys)
    available = router.available_providers()

    if not available:
        st.info("💡 少なくとも1つのAPIキーを入力してください。")
        selected_provider_id, selected_model = None, None
    else:
        labels = {p.provider_id: f"{p.display_name}（{p.strengths}）" for p in available}
        selected_provider_id = st.selectbox(
            "使用するAI",
            options=[p.provider_id for p in available],
            format_func=lambda pid: labels[pid],
        )
        provider_info = next(p for p in available if p.provider_id == selected_provider_id)
        selected_model = st.selectbox("モデル", options=provider_info.models)

    st.markdown("---")
    st.subheader("📎 教材アップロード")
    uploaded_files = st.file_uploader(
        "教科書画像・PDF資料（複数可）",
        type=["jpg", "jpeg", "png", "pdf"],
        accept_multiple_files=True,
    )
    if uploaded_files:
        for f in uploaded_files:
            f.seek(0)
            raw = f.read()
            if f.type == "application/pdf":
                add_material(pdf_to_material(f.name, raw))
            else:
                add_material(image_to_material(f.name, raw, f.type))

    url_input = st.text_input("参考URL", placeholder="https://...")
    if st.button("URLを取り込む", disabled=not url_input):
        try:
            with st.spinner("取得中..."):
                add_material(fetch_url_material(url_input))
            st.success("取り込みました")
        except Exception as e:
            st.error(f"取得に失敗しました: {e}")

    if st.session_state.materials:
        st.caption("登録済み教材:")
        for m in st.session_state.materials:
            st.caption(f"・{m.name}（{m.kind}）")

    st.markdown("---")
    if st.button("🆕 新しい相談を始める", use_container_width=True,
                 help="会話と教材をクリアします。生成済みの成果物は残ります。"):
        reset_conversation(keep_artifacts=True)
        st.rerun()

    st.markdown("---")
    with st.expander("💾 保存・共有"):
        st.caption("相談の続きを後日再開したり、同僚の先生にたたき台として共有できます。")
        has_content = bool(st.session_state.chat_history or st.session_state.artifacts)
        st.download_button(
            "📤 現在の内容を書き出す",
            data=export_session_json(),
            file_name="lesson_canvas_session.json",
            mime="application/json",
            disabled=not has_content,
            use_container_width=True,
        )
        uploaded_session = st.file_uploader(
            "📥 書き出したファイルを読み込む", type=["json"], key="session_uploader"
        )
        if uploaded_session is not None:
            merge_mode = st.checkbox("今の内容に追加する（オフの場合は置き換え）", value=False)
            if st.button("読み込む", use_container_width=True):
                try:
                    import_session_json(
                        uploaded_session.getvalue().decode("utf-8"), merge=merge_mode
                    )
                    st.success("読み込みました。")
                    st.rerun()
                except SessionImportError as e:
                    st.error(str(e))

# ==========================================
# メイン: 2ペイン構成
# ==========================================
st.title("🎓 授業構想キャンバス")
st.caption("AIと対話しながら授業を練り上げ、必要な資料をその場で出力できます。")


def stream_assistant_reply(chat_box) -> bool:
    """st.session_state.chat_history の末尾(user)に対するAI応答をストリーム表示する。
    成功時True、失敗時Falseを返す。失敗時はメッセージ履歴に追加しない
    （次の描画で『もう一度試す』を出せるようにするため）。"""
    with chat_box:
        with st.chat_message("assistant"):
            placeholder = st.empty()
            full_text = ""
            try:
                for chunk in router.stream_chat(
                    selected_provider_id,
                    selected_model,
                    CANVAS_SYSTEM_PROMPT,
                    st.session_state.chat_history,
                ):
                    full_text += chunk
                    placeholder.markdown(clean_html_tags(full_text) + "▌")
                full_text = clean_html_tags(full_text)
                placeholder.markdown(full_text)
                add_message("assistant", full_text)
                return True
            except Exception as e:
                placeholder.empty()
                st.error(friendly_error_message(e))
                return False


def send_user_turn(display_text: str, composed_text: str | None = None) -> None:
    """ユーザーの発話をチャットに追加する（実際にAIに送るテキストと画面表示用テキストを分けられる）。"""
    attachments = []
    for m in st.session_state.materials:
        if m.data is not None:
            attachments.append({"mime_type": m.mime_type, "data": m.data, "name": m.name})
    add_message("user", composed_text or display_text, attachments)


chat_col, canvas_col = st.columns([1, 1], gap="large")

# ---------- 左ペイン: チャット ----------
with chat_col:
    st.subheader("💬 AIと相談する")

    chat_box = st.container(height=440)
    with chat_box:
        for msg in st.session_state.chat_history:
            with st.chat_message("user" if msg.role == "user" else "assistant"):
                st.markdown(msg.text)

    # ---- 初回のみ: クイックスタート（相談のきっかけ）----
    if not st.session_state.chat_history and selected_provider_id:
        st.caption("💡 まず何を相談するか、下のボタンから選べます（自由入力も可）")
        qs_cols = st.columns(2)
        for i, qp in enumerate(QUICK_START_PROMPTS):
            with qs_cols[i % 2]:
                if st.button(qp["label"], key=f"qs_{i}", use_container_width=True):
                    context_text = materials_to_context_text(st.session_state.materials)
                    composed = qp["text"]
                    if context_text:
                        composed = f"{composed}\n\n【参考教材の要約】\n{context_text}"
                    send_user_turn(qp["label"], composed)
                    with chat_box:
                        with st.chat_message("user"):
                            st.markdown(qp["label"])
                    stream_assistant_reply(chat_box)
                    st.rerun()

    user_input = st.chat_input(
        "授業の構想について相談してみましょう（例: 4年算数のがい数の単元、つまずきやすい点は？）"
    )

    if user_input:
        if not selected_provider_id:
            st.error("サイドバーでAPIキーを入力し、使用するAIを選択してください。")
        else:
            context_text = materials_to_context_text(st.session_state.materials)
            composed_text = user_input
            if context_text and len(st.session_state.chat_history) == 0:
                composed_text = f"{user_input}\n\n【参考教材の要約】\n{context_text}"
            send_user_turn(user_input, composed_text)

            with chat_box:
                with st.chat_message("user"):
                    st.markdown(user_input)
            stream_assistant_reply(chat_box)

    # ---- AI応答が失敗した/未生成のまま残っている場合、再試行ボタンを出す ----
    if has_pending_user_turn() and selected_provider_id:
        if st.button("🔄 もう一度試す", key="retry_chat"):
            stream_assistant_reply(chat_box)
            st.rerun()

    st.markdown("---")
    st.caption("会話がまとまったら、下のボタンで成果物を生成できます。")

    artifact_type = st.selectbox(
        "生成する成果物",
        options=list(ARTIFACT_FORMATS.keys()),
        format_func=lambda k: ARTIFACT_FORMATS[k]["label"],
    )
    generate_disabled = not selected_provider_id or len(st.session_state.chat_history) == 0
    if st.button("📄 この内容で成果物を作成", disabled=generate_disabled, type="primary"):
        instruction = build_artifact_instruction(artifact_type)
        add_message("user", instruction)
        with st.spinner("生成中..."):
            try:
                full_text = "".join(
                    router.stream_chat(
                        selected_provider_id,
                        selected_model,
                        CANVAS_SYSTEM_PROMPT,
                        st.session_state.chat_history,
                    )
                )
                full_text = clean_html_tags(full_text)
                add_message("assistant", full_text)
                add_artifact(
                    Artifact(
                        artifact_id=str(uuid.uuid4())[:8],
                        artifact_type=artifact_type,
                        label=ARTIFACT_FORMATS[artifact_type]["label"],
                        content_md=full_text,
                    )
                )
                st.rerun()
            except Exception as e:
                st.error(friendly_error_message(e))

# ---------- 右ペイン: 成果物パネル ----------
with canvas_col:
    st.subheader("📋 成果物")

    if not st.session_state.artifacts:
        st.info("チャットで相談し、成果物を生成するとここに表示されます。")
    else:
        tab_labels = [
            f"{a.label} #{i+1}" for i, a in enumerate(st.session_state.artifacts)
        ]
        tabs = st.tabs(tab_labels)
        for tab, artifact in zip(tabs, st.session_state.artifacts):
            with tab:
                edited = st.text_area(
                    "内容（直接編集できます）",
                    value=artifact.content_md,
                    height=400,
                    key=f"edit_{artifact.artifact_id}",
                )
                artifact.content_md = edited

                st.markdown("**プレビュー**")
                with st.container(height=300, border=True):
                    st.markdown(edited)

                title = st.text_input(
                    "文書タイトル", value=artifact.label, key=f"title_{artifact.artifact_id}"
                )

                # ---- 品質ブラッシュアップ（別のAIによる批評・推敲） ----
                with st.expander("🪄 別のAIで品質をブラッシュアップ"):
                    st.caption(
                        "新学習指導要領の観点との整合性・発問の具体性・学年適合性などを、"
                        "別のAIにレビュー・推敲させます。今と同じAIを選んでも構いません。"
                    )
                    if available:
                        refine_provider_id = st.selectbox(
                            "レビューさせるAI",
                            options=[p.provider_id for p in available],
                            format_func=lambda pid: labels[pid],
                            key=f"refine_provider_{artifact.artifact_id}",
                        )
                        refine_provider_info = next(
                            p for p in available if p.provider_id == refine_provider_id
                        )
                        refine_model = st.selectbox(
                            "モデル", options=refine_provider_info.models,
                            key=f"refine_model_{artifact.artifact_id}",
                        )
                        if st.button("ブラッシュアップを実行", key=f"refine_btn_{artifact.artifact_id}"):
                            with st.spinner("レビュー・推敲中..."):
                                try:
                                    from core.ai.base import ChatMessage
                                    refine_prompt = build_refine_prompt(artifact.label, edited)
                                    refined_text = "".join(
                                        router.stream_chat(
                                            refine_provider_id,
                                            refine_model,
                                            "あなたは日本の学校教育に精通した、厳格かつ的確な指導主事です。",
                                            [ChatMessage(role="user", text=refine_prompt)],
                                        )
                                    )
                                    artifact.content_md = clean_html_tags(refined_text)
                                    st.success("ブラッシュアップしました。内容を更新しました。")
                                    st.rerun()
                                except Exception as e:
                                    st.error(friendly_error_message(e))
                    else:
                        st.caption("APIキーを設定すると使えます。")

                extra_export = EXTRA_EXPORTS.get(artifact.artifact_type)
                dl_cols = st.columns(2 if extra_export else 1)

                with dl_cols[0]:
                    w_buf = markdown_to_docx(
                        title=title,
                        subtitle="",
                        content_text=edited,
                        footer_note=FOOTER_NOTE,
                    )
                    st.download_button(
                        "📥 Word (.docx)",
                        data=w_buf,
                        file_name=f"{sanitize_filename(title)}.docx",
                        mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                        key=f"dl_docx_{artifact.artifact_id}",
                        use_container_width=True,
                    )

                if extra_export == "print_pdf":
                    with dl_cols[1]:
                        pdf_variant = st.radio(
                            "PDFの種類",
                            options=["student", "teacher"],
                            format_func=lambda v: "生徒配布用（解答なし）" if v == "student" else "教師用（解答つき）",
                            key=f"variant_{artifact.artifact_id}",
                            horizontal=True,
                        )
                        use_furigana = st.checkbox(
                            "ふりがな配慮版（特別支援・日本語指導向け）",
                            value=False,
                            key=f"furigana_{artifact.artifact_id}",
                            help="漢字の後ろに読み仮名を括弧書きで自動付与します（簡易的なふりがなです）。",
                        )
                        is_student = pdf_variant == "student"
                        p_buf = build_worksheet_pdf(
                            title=title,
                            subtitle="",
                            content_text=edited,
                            footer_note=FOOTER_NOTE,
                            include_answer_lines=is_student,
                            exclude_answer_sections=is_student,
                            furigana=use_furigana,
                        )
                        file_suffix = "_生徒配布用" if is_student else "_教師用"
                        if use_furigana:
                            file_suffix += "_ふりがな版"
                        st.download_button(
                            "📥 印刷用PDF",
                            data=p_buf,
                            file_name=f"{sanitize_filename(title)}{file_suffix}.pdf",
                            mime="application/pdf",
                            key=f"dl_pdf_{artifact.artifact_id}",
                            use_container_width=True,
                        )
                elif extra_export == "pptx":
                    with dl_cols[1]:
                        s_buf = build_slide_outline_pptx(
                            deck_title=title,
                            content_text=edited,
                            footer_note=FOOTER_NOTE,
                        )
                        st.download_button(
                            "📥 PowerPoint (.pptx)",
                            data=s_buf,
                            file_name=f"{sanitize_filename(title)}.pptx",
                            mime="application/vnd.openxmlformats-officedocument.presentationml.presentation",
                            key=f"dl_pptx_{artifact.artifact_id}",
                            use_container_width=True,
                        )

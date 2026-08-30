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
from core.intake import UnitIntake, build_intake_prompt
from core.db import LibraryError, is_library_configured, submit_for_review
from core.prompts import (
    ARTIFACT_FORMATS,
    CANVAS_SYSTEM_PROMPT,
    QUICK_START_PROMPTS,
    build_artifact_instruction,
    build_variant_instruction,
)
from core.refine import build_refine_prompt
from core.session_io import SessionImportError, export_session_json, import_session_json
from core.session_store import (
    Artifact,
    add_artifact,
    add_material,
    add_message,
    artifacts_by_variant_group,
    delete_artifact,
    has_pending_user_turn,
    init_session,
    reset_conversation,
)
from core.sources import fetch_url_material, image_to_material, materials_to_context_text, pdf_to_material
from core.translate import build_translate_prompt
from exporters.docx_builder import clean_html_tags, markdown_to_docx, sanitize_filename
from exporters.diagram_builder import DiagramError, build_board_image_svg, build_unit_map_svg
from exporters.pptx_builder import build_slide_outline_pptx
from exporters.worksheet_pdf import build_worksheet_pdf

# 成果物タイプごとに、Word以外にどの追加出力を出せるか
EXTRA_EXPORTS = {
    "worksheet": "print_pdf",
    "quiz": "print_pdf",
    "slide_outline": "pptx",
    "differentiated_worksheet": "print_pdf",
}

# 成果物タイプごとに、どの図解を表示できるか
DIAGRAM_KIND = {
    "unit_plan": "unit_map",
    "lesson_plan": "board_image",
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
    """ユーザーの発話をチャットに追加する（実際にAIに送るテキストと画面表示用テキストを分けられる）。

    教材（画像/PDF）は「まだ送信していないもの」だけを添付する。会話履歴は毎回の
    API呼び出しでまるごと送信されるため、送信済みの教材を毎ターン添付し続けると
    同じデータを何度も再送信することになり、リクエストが際限なく肥大化してしまう
    （エラーや応答の遅さの原因になりうる）。1度送ればAIはその内容を踏まえて
    以降の会話にも応答できるため、同じ教材を繰り返し送る必要はない。
    """
    attachments = []
    for m in st.session_state.materials:
        if m.data is not None and m.name not in st.session_state.materials_sent:
            attachments.append({"mime_type": m.mime_type, "data": m.data, "name": m.name})
            st.session_state.materials_sent.add(m.name)
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

    # ---- 初回のみ: 事前情報フォーム + クイックスタート ----
    if not st.session_state.chat_history and selected_provider_id:
        st.markdown("##### 📝 まず事前情報を入力する（おすすめ）")
        st.caption("学年・教科・単元名などをまとめて入力しておくと、AIが同じ質問を繰り返さずに済みます。")
        with st.form("intake_form", clear_on_submit=False):
            f_cols1 = st.columns(3)
            with f_cols1[0]:
                f_grade = st.text_input("学年", placeholder="例: 4年")
            with f_cols1[1]:
                f_subject = st.text_input("教科", placeholder="例: 算数")
            with f_cols1[2]:
                f_hours = st.text_input("総時数", placeholder="例: 6時間")
            f_unit = st.text_input("単元名", placeholder="例: がい数")
            f_objectives = st.text_area(
                "単元のねらい・身につけさせたい力（任意）", placeholder="例: 四捨五入を使って概数を求められるようにする", height=70
            )
            f_situation = st.text_area(
                "児童生徒の実態・気になる点（任意）", placeholder="例: 計算は得意だが文章題でつまずきやすい", height=70
            )
            f_textbook = st.text_input("使用教科書・教材（任意）", placeholder="例: 東京書籍 新編算数")
            f_extra = st.text_area(
                "その他の要望（任意）", placeholder="例: グループ活動を取り入れたい、ICTを使いたい 等", height=70
            )
            submitted = st.form_submit_button("🚀 この内容で相談を始める", type="primary", use_container_width=True)

        if submitted:
            intake = UnitIntake(
                grade=f_grade, subject=f_subject, unit_name=f_unit, total_hours=f_hours,
                objectives=f_objectives, student_situation=f_situation,
                textbook=f_textbook, extra_requests=f_extra,
            )
            if intake.is_empty():
                st.warning("少なくとも1項目は入力してください。")
            else:
                context_text = materials_to_context_text(st.session_state.materials)
                composed = build_intake_prompt(intake)
                if context_text:
                    composed = f"{composed}\n\n【参考教材の要約】\n{context_text}"
                display_text = intake.summary_label()
                send_user_turn(display_text, composed)
                with chat_box:
                    with st.chat_message("user"):
                        st.markdown(display_text)
                stream_assistant_reply(chat_box)
                st.rerun()

        with st.expander("💬 またはボタンから気軽に始める"):
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
                full_text = router.chat_with_retry(
                    selected_provider_id,
                    selected_model,
                    CANVAS_SYSTEM_PROMPT,
                    st.session_state.chat_history,
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
        # ---- バージョン比較（別パターンが2件以上あるグループを並べて表示） ----
        seen_groups: set[str] = set()
        for a in st.session_state.artifacts:
            if a.variant_group and a.variant_group not in seen_groups:
                group_members = artifacts_by_variant_group(a.variant_group)
                if len(group_members) >= 2:
                    seen_groups.add(a.variant_group)
                    with st.expander(f"⚖️ 比較する: {a.label}（{len(group_members)}パターン）", expanded=True):
                        cmp_cols = st.columns(len(group_members))
                        for cmp_col, member in zip(cmp_cols, group_members):
                            with cmp_col:
                                st.markdown(f"**{member.variant_label or member.label}**")
                                with st.container(height=220, border=True):
                                    st.markdown(member.content_md)
                                if st.button(
                                    "この案を採用（他を削除）",
                                    key=f"adopt_{member.artifact_id}",
                                    use_container_width=True,
                                ):
                                    for other in group_members:
                                        if other.artifact_id != member.artifact_id:
                                            delete_artifact(other.artifact_id)
                                    member.variant_group = ""
                                    member.variant_label = ""
                                    st.rerun()

        tab_labels = [
            f"{a.label}"
            + (f"（{a.variant_label}）" if a.variant_label else "")
            + f" #{i+1}"
            for i, a in enumerate(st.session_state.artifacts)
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
                                    refined_text = router.chat_with_retry(
                                        refine_provider_id,
                                        refine_model,
                                        "あなたは日本の学校教育に精通した、厳格かつ的確な指導主事です。",
                                        [ChatMessage(role="user", text=refine_prompt)],
                                    )
                                    artifact.content_md = clean_html_tags(refined_text)
                                    st.success("ブラッシュアップしました。内容を更新しました。")
                                    st.rerun()
                                except Exception as e:
                                    st.error(friendly_error_message(e))
                    else:
                        st.caption("APIキーを設定すると使えます。")

                # ---- 別パターンを生成して比較 ----
                with st.expander("🔀 別パターンを生成して比較"):
                    st.caption(
                        "同じテーマで、切り口や活動の組み立てが異なる別案をもう1つ作成します。"
                        "両方できたら見比べて、良い方を採用できます。"
                    )
                    if selected_provider_id and st.button(
                        "別パターンを生成", key=f"variant_btn_{artifact.artifact_id}"
                    ):
                        with st.spinner("別パターンを生成中..."):
                            try:
                                from core.ai.base import ChatMessage
                                group_id = artifact.variant_group or artifact.artifact_id
                                if not artifact.variant_group:
                                    artifact.variant_group = group_id
                                    artifact.variant_label = "パターンA"
                                existing_in_group = artifacts_by_variant_group(group_id)
                                next_label = f"パターン{chr(65 + len(existing_in_group))}"

                                variant_prompt = build_variant_instruction(
                                    artifact.artifact_type, edited
                                )
                                variant_text = router.chat_with_retry(
                                    selected_provider_id, selected_model,
                                    CANVAS_SYSTEM_PROMPT,
                                    [ChatMessage(role="user", text=variant_prompt)],
                                )
                                add_artifact(Artifact(
                                    artifact_id=str(uuid.uuid4())[:8],
                                    artifact_type=artifact.artifact_type,
                                    label=artifact.label,
                                    content_md=clean_html_tags(variant_text),
                                    variant_group=group_id,
                                    variant_label=next_label,
                                ))
                                st.success(f"{next_label} を生成しました。下の「⚖️ 比較する」から見比べられます。")
                                st.rerun()
                            except Exception as e:
                                st.error(friendly_error_message(e))
                    elif not selected_provider_id:
                        st.caption("APIキーを設定すると使えます。")

                # ---- 英語版を生成（ALT・外国籍家庭向け） ----
                with st.expander("🌐 英語版を生成（ALT・外国籍家庭向け）"):
                    st.caption("同じ内容を、ALTや日本語がまだ得意でない家庭にも伝わる英語に書き直します。")
                    if selected_provider_id and st.button(
                        "英語版を生成", key=f"translate_btn_{artifact.artifact_id}"
                    ):
                        with st.spinner("英語版を作成中..."):
                            try:
                                from core.ai.base import ChatMessage
                                translate_prompt = build_translate_prompt(artifact.label, edited)
                                translated_text = router.chat_with_retry(
                                    selected_provider_id, selected_model,
                                    "You are a bilingual Japanese-English education assistant.",
                                    [ChatMessage(role="user", text=translate_prompt)],
                                )
                                add_artifact(Artifact(
                                    artifact_id=str(uuid.uuid4())[:8],
                                    artifact_type=artifact.artifact_type,
                                    label=f"{artifact.label} (English)",
                                    content_md=clean_html_tags(translated_text),
                                ))
                                st.success("英語版を生成しました。新しいタブに追加されました。")
                                st.rerun()
                            except Exception as e:
                                st.error(friendly_error_message(e))
                    elif not selected_provider_id:
                        st.caption("APIキーを設定すると使えます。")

                # ---- 管理職への確認依頼 ----
                with st.expander("📤 管理職に確認を依頼"):
                    if is_library_configured():
                        submitter_name = st.text_input(
                            "お名前", key=f"submitter_{artifact.artifact_id}"
                        )
                        if st.button("この内容で確認を依頼する", key=f"submit_review_{artifact.artifact_id}"):
                            if not submitter_name:
                                st.warning("お名前を入力してください。")
                            else:
                                try:
                                    submit_for_review(
                                        submitter_name=submitter_name,
                                        artifact_label=title,
                                        artifact_type=artifact.artifact_type,
                                        content_md=edited,
                                    )
                                    st.success("確認依頼を送信しました。「確認・承認」ページから状況を確認できます。")
                                except LibraryError as e:
                                    st.error(str(e))
                    else:
                        st.caption(
                            "この機能はまだ設定されていません。管理担当の先生に、"
                            "README.md の「管理職の確認・承認フローを使う」の手順で"
                            "設定してもらってください。"
                        )

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

                # ---- 図で見る（単元マップ / 板書イメージ） ----
                diagram_kind = DIAGRAM_KIND.get(artifact.artifact_type)
                if diagram_kind:
                    diagram_label = "🗺 単元マップを表示" if diagram_kind == "unit_map" else "🖼 板書イメージを表示"
                    with st.expander(diagram_label):
                        try:
                            if diagram_kind == "unit_map":
                                svg = build_unit_map_svg(edited, title=title)
                            else:
                                svg = build_board_image_svg(edited, title=title)
                            st.markdown(
                                f'<div style="max-width:100%;overflow-x:auto;">{svg}</div>',
                                unsafe_allow_html=True,
                            )
                            st.download_button(
                                "📥 SVGでダウンロード（拡大・印刷向き）",
                                data=svg,
                                file_name=f"{sanitize_filename(title)}_{diagram_kind}.svg",
                                mime="image/svg+xml",
                                key=f"dl_svg_{artifact.artifact_id}",
                            )
                        except DiagramError as e:
                            st.info(str(e))

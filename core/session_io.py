"""
セッション（対話履歴・成果物）をJSONファイルとして書き出し/読み込みする。

用途:
- ある先生が良い相談内容・成果物を作った後、続きを別の日に再開したい
- 良くできた相談の流れを、同僚の先生に「たたき台」として共有したい

Streamlit Cloudはサーバー側の永続ストレージを持たないため、
ここでは「ファイルとしてダウンロード/アップロードする」形で
簡易的な永続化・共有を実現する。

注意: 教材(materials)の生バイト列(画像/PDF)はサイズが大きくなりがちなため、
書き出し対象は「テキスト情報（抽出済みテキスト・URL）」のみとし、
画像/PDFの添付そのものは含めない（再開時は再アップロードが必要）。
"""

from __future__ import annotations

import json
from dataclasses import asdict

import streamlit as st

from .ai.base import ChatMessage
from .session_store import Artifact
from .sources import Material

SESSION_FORMAT_VERSION = 1


def export_session_json() -> str:
    """現在の会話履歴・成果物をJSON文字列として書き出す。"""
    data = {
        "format_version": SESSION_FORMAT_VERSION,
        "chat_history": [
            {"role": m.role, "text": m.text}  # 添付ファイルは書き出さない
            for m in st.session_state.get("chat_history", [])
        ],
        "materials_meta": [
            {"name": m.name, "kind": m.kind, "extracted_text": m.extracted_text, "source": m.source}
            for m in st.session_state.get("materials", [])
        ],
        "artifacts": [
            {
                "artifact_id": a.artifact_id,
                "artifact_type": a.artifact_type,
                "label": a.label,
                "content_md": a.content_md,
            }
            for a in st.session_state.get("artifacts", [])
        ],
    }
    return json.dumps(data, ensure_ascii=False, indent=2)


class SessionImportError(Exception):
    pass


def import_session_json(raw_json: str, *, merge: bool = False) -> None:
    """JSON文字列からセッションを復元する。

    merge=False: 現在の会話・成果物を置き換える
    merge=True : 現在の内容に追記する（同僚のテンプレートを自分の続きに取り込む場合など）
    """
    try:
        data = json.loads(raw_json)
    except json.JSONDecodeError as e:
        raise SessionImportError(f"JSONの形式が正しくありません: {e}") from e

    if "format_version" not in data:
        raise SessionImportError("このアプリで書き出されたファイルではないようです。")

    new_chat = [ChatMessage(role=m["role"], text=m["text"]) for m in data.get("chat_history", [])]
    new_materials = [
        Material(
            name=m["name"], kind=m["kind"], mime_type="text/plain",
            extracted_text=m.get("extracted_text", ""), source=m.get("source", ""),
        )
        for m in data.get("materials_meta", [])
    ]
    new_artifacts = [
        Artifact(
            artifact_id=a["artifact_id"], artifact_type=a["artifact_type"],
            label=a["label"], content_md=a["content_md"],
        )
        for a in data.get("artifacts", [])
    ]

    if merge:
        st.session_state.chat_history.extend(new_chat)
        existing_names = {m.name for m in st.session_state.materials}
        st.session_state.materials.extend(m for m in new_materials if m.name not in existing_names)
        st.session_state.artifacts.extend(new_artifacts)
    else:
        st.session_state.chat_history = new_chat
        st.session_state.materials = new_materials
        st.session_state.artifacts = new_artifacts

"""
Streamlitのsession_stateをラップし、
「対話履歴」「教材ライブラリ」「生成された成果物一覧」を型付きで扱う。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

import streamlit as st

from .ai.base import ChatMessage
from .sources import Material


@dataclass
class Artifact:
    """チャットから生成された成果物1件（Canvasのパネルに表示される）。"""
    artifact_id: str
    artifact_type: str      # "unit_plan" / "lesson_plan" / "worksheet" / "quiz" / "slide_outline"
    label: str
    content_md: str
    created_at: str = field(default_factory=lambda: datetime.now().strftime("%H:%M:%S"))
    title_meta: dict = field(default_factory=dict)  # docx出力用のタイトル/サブタイトル情報
    variant_group: str = ""     # 同じ成果物の別パターン比較用のグループID（空なら単独）
    variant_label: str = ""     # 比較UIでの表示名（例: "パターンA"）


def init_session() -> None:
    if "chat_history" not in st.session_state:
        st.session_state.chat_history: list[ChatMessage] = []
    if "materials" not in st.session_state:
        st.session_state.materials: list[Material] = []
    if "artifacts" not in st.session_state:
        st.session_state.artifacts: list[Artifact] = []
    if "active_artifact_id" not in st.session_state:
        st.session_state.active_artifact_id: str | None = None


def add_message(role: str, text: str, attachments: list[dict] | None = None) -> None:
    st.session_state.chat_history.append(
        ChatMessage(role=role, text=text, attachments=attachments or [])
    )


def add_material(material: Material) -> None:
    # 同名教材の重複登録を避ける
    existing_names = {m.name for m in st.session_state.materials}
    if material.name not in existing_names:
        st.session_state.materials.append(material)


def add_artifact(artifact: Artifact) -> None:
    st.session_state.artifacts.append(artifact)
    st.session_state.active_artifact_id = artifact.artifact_id


def get_artifact(artifact_id: str) -> Artifact | None:
    for a in st.session_state.artifacts:
        if a.artifact_id == artifact_id:
            return a
    return None


def update_artifact_content(artifact_id: str, new_content: str) -> None:
    for a in st.session_state.artifacts:
        if a.artifact_id == artifact_id:
            a.content_md = new_content
            return


def reset_conversation(keep_artifacts: bool = True) -> None:
    """新しい単元・トピックの相談を始めるために、会話と教材をクリアする。
    生成済みの成果物はデフォルトで保持する（ダウンロードし忘れ防止）。"""
    st.session_state.chat_history = []
    st.session_state.materials = []
    if not keep_artifacts:
        st.session_state.artifacts = []
        st.session_state.active_artifact_id = None


def has_pending_user_turn() -> bool:
    """直近のメッセージがuserのまま（AI応答が未生成/失敗）かどうか。"""
    history = st.session_state.chat_history
    return bool(history) and history[-1].role == "user"


def delete_artifact(artifact_id: str) -> None:
    st.session_state.artifacts = [
        a for a in st.session_state.artifacts if a.artifact_id != artifact_id
    ]
    if st.session_state.active_artifact_id == artifact_id:
        st.session_state.active_artifact_id = None


def artifacts_by_variant_group(group_id: str) -> list[Artifact]:
    return [a for a in st.session_state.artifacts if a.variant_group == group_id]

"""
APIキーの調達元を統合的に扱う。

夏休み中に同僚の先生にも使ってもらうことを想定し、
以下の優先順位でキーを解決する:

1. Streamlit Cloud の「Secrets」に学校共有キーが設定されていれば、
   先生は何も入力せずに使える（st.secrets["shared_api_keys"]）
2. 共有キーがない/使いたくない場合は、各自のAPIキーを入力する

共有キーを使う場合、そのキーでの利用量は全員分が合算される点に注意。
学校で1つのGoogle Cloud/Anthropic/OpenAIアカウントを共有する運用を想定し、
サイドバーにその旨を明示する。
"""

from __future__ import annotations

import streamlit as st


def get_shared_keys() -> dict[str, str]:
    """st.secrets に [shared_api_keys] セクションがあれば読み込む。
    未設定でもエラーにならない。"""
    try:
        section = st.secrets.get("shared_api_keys", {})
        return {
            "gemini": section.get("gemini", ""),
            "claude": section.get("claude", ""),
            "openai": section.get("openai", ""),
        }
    except Exception:
        return {"gemini": "", "claude": "", "openai": ""}


def resolve_api_keys() -> dict[str, str]:
    """サイドバーUIを描画しつつ、最終的に使うAPIキー一式を返す。"""
    shared = get_shared_keys()
    has_shared = any(shared.values())

    keys = {"gemini": "", "claude": "", "openai": ""}

    if has_shared:
        use_shared = st.checkbox("🏫 学校共有のAPIキーを使う", value=True)
        if use_shared:
            st.caption("共有キーでの利用量は学校全体で合算されます。")
            keys = shared
        else:
            keys["gemini"] = st.text_input("Google Gemini API Key", type="password")
            keys["claude"] = st.text_input("Anthropic Claude API Key", type="password")
            keys["openai"] = st.text_input("OpenAI API Key", type="password")
    else:
        st.caption("各自のAPIキーを入力してください（サーバーには保存されません）。")
        keys["gemini"] = st.text_input("Google Gemini API Key", type="password")
        keys["claude"] = st.text_input("Anthropic Claude API Key", type="password")
        keys["openai"] = st.text_input("OpenAI API Key", type="password")

    return keys

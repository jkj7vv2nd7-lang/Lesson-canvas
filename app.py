"""
授業構想キャンバス — エントリーポイント。

ページのタイトル・アイコンをファイル名に依存せずPythonコード側で明示的に
指定することで、日本語ファイル名に起因する文字コード関連の問題
（Windowsでのzip展開やアップロード時の文字化け等）を避けている。
"""

from __future__ import annotations

import streamlit as st

st.set_page_config(page_title="授業構想キャンバス", page_icon="🎓", layout="wide")

canvas_page = st.Page(
    "pages/canvas.py", title="授業構想キャンバス", icon="🎓", default=True
)
library_page = st.Page(
    "pages/library.py", title="共有教材ライブラリ", icon="📚"
)
approval_page = st.Page(
    "pages/approval.py", title="確認・承認", icon="✅"
)

pg = st.navigation([canvas_page, library_page, approval_page])
pg.run()

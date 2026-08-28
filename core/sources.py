"""
参照ソース（教材）の統合管理。

- URLは実際に本文を取得する（旧app.pyでは文字列を渡すだけで中身を読んでいなかった）
- PDF/画像は名前付きの「教材」としてsession_stateに登録し、
  チャットのどのターンでも参照できるようにする
"""

from __future__ import annotations

import io
from dataclasses import dataclass, field

import requests
from pypdf import PdfReader


@dataclass
class Material:
    """アップロード済み教材、またはURL由来の資料1件分。"""
    name: str
    kind: str            # "pdf" / "image" / "url"
    mime_type: str
    data: bytes | None = None      # 画像/PDFの生バイト列（AIへ直接渡す用）
    extracted_text: str = ""       # PDF/URLから抽出した本文（テキストモデル用フォールバック）
    source: str = ""               # URLの場合は元のURL


MAX_URL_CHARS = 6000  # 1URLあたり取得する本文の上限（プロンプト肥大化防止）


def fetch_url_material(url: str, timeout: int = 10) -> Material:
    """URLから本文テキストを取得してMaterial化する。失敗時は例外を投げる。"""
    resp = requests.get(url, timeout=timeout, headers={"User-Agent": "Mozilla/5.0"})
    resp.raise_for_status()

    text = resp.text
    # 簡易的なHTML本文抽出（軽量実装。より高精度にしたい場合は trafilatura 等に差し替え可）
    import re
    text = re.sub(r"<script.*?</script>", " ", text, flags=re.S | re.I)
    text = re.sub(r"<style.*?</style>", " ", text, flags=re.S | re.I)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text).strip()

    return Material(
        name=url,
        kind="url",
        mime_type="text/plain",
        extracted_text=text[:MAX_URL_CHARS],
        source=url,
    )


def pdf_to_material(name: str, raw_bytes: bytes) -> Material:
    """PDFファイルからテキストを抽出しつつ、生バイト列も保持する。"""
    text_parts = []
    try:
        reader = PdfReader(io.BytesIO(raw_bytes))
        for page in reader.pages:
            t = page.extract_text()
            if t:
                text_parts.append(t)
    except Exception:
        pass
    return Material(
        name=name,
        kind="pdf",
        mime_type="application/pdf",
        data=raw_bytes,
        extracted_text="\n".join(text_parts),
    )


def image_to_material(name: str, raw_bytes: bytes, mime_type: str) -> Material:
    return Material(name=name, kind="image", mime_type=mime_type, data=raw_bytes)


def materials_to_context_text(materials: list[Material], per_item_limit: int = 2000) -> str:
    """テキストベースでプロンプトに埋め込むための要約コンテキストを作る
    （画像/PDFを直接読めないプロバイダー向けのフォールバック）。"""
    if not materials:
        return ""
    blocks = []
    for m in materials:
        if m.kind == "url":
            blocks.append(f"[参考URL: {m.source}]\n{m.extracted_text[:per_item_limit]}")
        elif m.kind == "pdf" and m.extracted_text:
            blocks.append(f"[添付PDF: {m.name}]\n{m.extracted_text[:per_item_limit]}")
        elif m.kind == "image":
            blocks.append(f"[添付画像: {m.name}]（画像内容は別途モデルに渡されます）")
    return "\n\n".join(blocks)

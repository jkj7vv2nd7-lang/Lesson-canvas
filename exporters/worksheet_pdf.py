"""
「ワークシート」「振り返り・小テスト」のMarkdownを、
生徒が実際に書き込める印刷用PDFに変換する。

Word出力(docx_builder)と違い、こちらは:
- 設問ごとに記入欄（罫線）を自動で挿入する
- 日本語フォントは reportlab 組み込みのCIDフォントを使うため、
  フォントファイルの同梱が不要
- 特別支援・日本語指導が必要な児童向けに、漢字にふりがな（読み仮名）を
  自動付与した配慮版を出力できる（pykakasiによる形態素解析ベース）
"""

from __future__ import annotations

import io
import re

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.platypus import (
    HRFlowable,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from core.md_parse import extract_code_blocks, extract_tables, split_into_sections

_FONT_NAME = "HeiseiKakuGo-W5"   # ゴシック(見出し向き)
_FONT_NAME_MIN = "HeiseiMin-W3"  # 明朝(本文向き)

_fonts_registered = False
_kakasi_instance = None


def _ensure_fonts() -> None:
    global _fonts_registered
    if _fonts_registered:
        return
    pdfmetrics.registerFont(UnicodeCIDFont(_FONT_NAME))
    pdfmetrics.registerFont(UnicodeCIDFont(_FONT_NAME_MIN))
    _fonts_registered = True


def _get_kakasi():
    global _kakasi_instance
    if _kakasi_instance is None:
        import pykakasi
        _kakasi_instance = pykakasi.kakasi()
    return _kakasi_instance


_KANJI_RE = re.compile(r"[\u4E00-\u9FFF]")


def add_furigana(text: str) -> str:
    """漢字を含む単語のうしろに (ひらがな) を付与する（真のルビではなく、
    括弧書きの簡易ふりがな。reportlabのルビ機能は制約が多いため実用性を優先）。
    例: 「概数」→「概数(がいすう)」

    注意: pykakasiは複数行テキストを一括変換すると改行の扱いが崩れることがあるため、
    必ず1行ずつ処理する。
    """
    kks = _get_kakasi()

    def _convert_line(line: str) -> str:
        if not _KANJI_RE.search(line):
            return line
        result = kks.convert(line)
        out = []
        for item in result:
            orig = item["orig"]
            if _KANJI_RE.search(orig) and item["hira"] != orig:
                out.append(f"{orig}({item['hira']})")
            else:
                out.append(orig)
        return "".join(out)

    return "\n".join(_convert_line(line) for line in text.split("\n"))


def _styles() -> dict:
    _ensure_fonts()
    return {
        "title": ParagraphStyle(
            "title", fontName=_FONT_NAME, fontSize=20, leading=26,
            spaceAfter=4, alignment=1,
        ),
        "meta": ParagraphStyle(
            "meta", fontName=_FONT_NAME_MIN, fontSize=10, leading=14,
            alignment=1, textColor=colors.grey, spaceAfter=10,
        ),
        "h2": ParagraphStyle(
            "h2", fontName=_FONT_NAME, fontSize=14, leading=20,
            spaceBefore=12, spaceAfter=6, textColor=colors.HexColor("#2B5876"),
        ),
        "body": ParagraphStyle(
            "body", fontName=_FONT_NAME_MIN, fontSize=11, leading=18,
            spaceAfter=6,
        ),
        "question": ParagraphStyle(
            "question", fontName=_FONT_NAME, fontSize=11.5, leading=18,
            spaceBefore=10, spaceAfter=4,
        ),
        "note": ParagraphStyle(
            "note", fontName=_FONT_NAME_MIN, fontSize=8, leading=12,
            textColor=colors.grey,
        ),
        "cell": ParagraphStyle(
            "cell", fontName=_FONT_NAME_MIN, fontSize=9.5, leading=14,
        ),
        "cell_header": ParagraphStyle(
            "cell_header", fontName=_FONT_NAME, fontSize=9.5, leading=14,
            textColor=colors.white,
        ),
    }


def _answer_blank(height_mm: float = 16) -> Spacer:
    """記入欄の代わりの空白（下線はTableで表現する方が綺麗なため、
    実際の罫線は _lined_box を使う）。"""
    return Spacer(1, height_mm * mm)


def _lined_box(styles: dict, n_lines: int = 3) -> Table:
    """生徒が書き込むための罫線ボックス。"""
    rows = [[""] for _ in range(n_lines)]
    t = Table(rows, colWidths=[170 * mm], rowHeights=[8 * mm] * n_lines)
    t.setStyle(TableStyle([
        ("LINEBELOW", (0, 0), (-1, -1), 0.6, colors.HexColor("#BBBBBB")),
        ("TOPPADDING", (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
    ]))
    return t


def _render_table(rows: list[list[str]], styles: dict) -> Table:
    data = [
        [Paragraph(cell, styles["cell_header"] if r == 0 else styles["cell"]) for cell in row]
        for r, row in enumerate(rows)
    ]
    col_count = len(rows[0])
    col_width = 170 * mm / col_count
    t = Table(data, colWidths=[col_width] * col_count)
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2B5876")),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#999999")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    return t


_ANSWER_SECTION_KEYWORDS = ("解答", "採点", "評価規準", "評価ルーブリック")


def build_worksheet_pdf(
    *,
    title: str,
    subtitle: str,
    content_text: str,
    footer_note: str = "",
    include_answer_lines: bool = True,
    exclude_answer_sections: bool = False,
    furigana: bool = False,
) -> io.BytesIO:
    """
    ワークシート/小テストのMarkdownを印刷用PDFに変換する。

    - 見出し(##)ごとにセクション分けして表示
    - 表(|...|)がある場合はそのまま表として描画
    - 表がない本文段落は「設問」とみなし、下に記入欄（罫線）を追加する
      （include_answer_lines=False にすると記入欄なしのPDFになる）
    - exclude_answer_sections=True にすると、見出しに「解答」「採点」等を含む
      セクションを丸ごと除外する（生徒配布用に解答を隠すため）
    - furigana=True にすると、本文・設問中の漢字に括弧書きの読み仮名を
      自動付与する（特別支援・日本語指導が必要な児童向けの配慮版）
    """
    styles = _styles()
    if furigana:
        title = add_furigana(title)
        subtitle = add_furigana(subtitle)
        content_text = add_furigana(content_text)
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        topMargin=18 * mm, bottomMargin=16 * mm,
        leftMargin=20 * mm, rightMargin=20 * mm,
    )

    story = []
    story.append(Paragraph(title, styles["title"]))
    if subtitle:
        story.append(Paragraph(subtitle, styles["meta"]))
    story.append(HRFlowable(width="100%", color=colors.HexColor("#CCCCCC")))
    story.append(Spacer(1, 4 * mm))

    # 氏名欄（ワークシート/小テストなので定番で入れる）
    name_row = Table(
        [["", ""]],
        colWidths=[100 * mm, 70 * mm],
    )
    name_row.setStyle(TableStyle([
        ("LINEBELOW", (0, 0), (0, 0), 0.6, colors.HexColor("#999999")),
        ("LINEBELOW", (1, 0), (1, 0), 0.6, colors.HexColor("#999999")),
    ]))
    story.append(Paragraph("組（　　　） 番（　　　） 氏名：", styles["body"]))
    story.append(Spacer(1, 6 * mm))

    sections = split_into_sections(content_text)
    if not sections:
        sections = [type("S", (), {"heading": "", "level": 2, "body_lines": content_text.split("\n")})()]

    for sec in sections:
        if exclude_answer_sections and any(k in sec.heading for k in _ANSWER_SECTION_KEYWORDS):
            continue
        if sec.heading:
            story.append(Paragraph(sec.heading, styles["h2"]))

        tables = extract_tables(sec.body_lines)
        code_blocks = extract_code_blocks(sec.body_lines)

        # 表がある場合はそのまま描画（解答欄や配点表など）
        if tables:
            for t_rows in tables:
                story.append(_render_table(t_rows, styles))
                story.append(Spacer(1, 4 * mm))
            continue

        # コードブロック（板書等が混入した場合の保険）
        if code_blocks:
            for block in code_blocks:
                story.append(Paragraph(block.replace("\n", "<br/>"), styles["body"]))
                story.append(Spacer(1, 3 * mm))
            continue

        # 表でもコードでもない本文行 → 設問として扱い、記入欄を添える
        body_lines = [ln for ln in sec.body_lines if ln.strip()]
        for line in body_lines:
            stripped = line.strip()
            is_question = bool(re.match(r"^(\d+[.\).]|問\d+|[①-⑳])", stripped))
            style = styles["question"] if is_question else styles["body"]
            story.append(Paragraph(stripped, style))
            if include_answer_lines and is_question:
                story.append(_lined_box(styles, n_lines=2))
                story.append(Spacer(1, 3 * mm))

    if footer_note:
        story.append(Spacer(1, 8 * mm))
        story.append(Paragraph(footer_note, styles["note"]))

    doc.build(story)
    buf.seek(0)
    return buf

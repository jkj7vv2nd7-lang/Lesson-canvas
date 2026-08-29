"""
単元計画・本時案のMarkdownから、視覚的な図（SVG）を生成する。

- 単元マップ: 単元指導計画表(時数ごとの学習内容)を、時系列の流れ図として可視化
- 板書イメージ図: 本時案の「板書計画」を、黒板風のビジュアルとして再現

外部の描画ライブラリ(graphviz等のシステムバイナリ)に依存せず、
SVGを文字列として直接組み立てることで、Streamlit Cloud上でも
追加のシステムパッケージなしに動作するようにしている。
"""

from __future__ import annotations

import html
import textwrap

from core.md_parse import extract_code_blocks, extract_tables, find_section, split_into_sections

_UNIT_MAP_COLORS = ["#2B5876", "#3B7B9E", "#4A9DBF", "#5ABFDF"]


def _esc(text: str) -> str:
    return html.escape(text, quote=True)


def _wrap_lines(text: str, width: int = 16) -> list[str]:
    if not text:
        return [""]
    return textwrap.wrap(text, width=width) or [""]


class DiagramError(Exception):
    pass


def build_unit_map_svg(unit_plan_md: str, *, title: str = "単元マップ") -> str:
    """単元指導計画表を、時系列の流れ図(縦方向のフローチャート)としてSVG化する。"""
    sections = split_into_sections(unit_plan_md)
    target = find_section(sections, "指導計画") or find_section(sections, "単元")
    rows: list[list[str]] = []
    if target:
        tables = extract_tables(target.body_lines)
        if tables:
            rows = tables[0]
    if not rows:
        # フォールバック: 文書全体から最初に見つかった表を使う
        tables = extract_tables(unit_plan_md.split("\n"))
        if tables:
            rows = tables[0]

    if len(rows) < 2:
        raise DiagramError(
            "単元指導計画の表が見つかりませんでした。「単元計画」の成果物から生成してください。"
        )

    header = rows[0]
    data_rows = rows[1:]

    box_w, box_h, gap, margin = 560, 64, 28, 40
    width = box_w + margin * 2
    height = margin * 2 + len(data_rows) * (box_h + gap) - gap + 60

    parts = [
        f'<svg viewBox="0 0 {width} {height}" xmlns="http://www.w3.org/2000/svg" '
        f'font-family="sans-serif">',
        f'<rect width="{width}" height="{height}" fill="#FFFFFF"/>',
        f'<text x="{width/2}" y="30" text-anchor="middle" font-size="20" '
        f'font-weight="bold" fill="#1F3A52">{_esc(title)}</text>',
    ]

    y = 60
    for i, row in enumerate(data_rows):
        color = _UNIT_MAP_COLORS[i % len(_UNIT_MAP_COLORS)]
        label_cell = row[0] if row else ""
        content_cell = row[1] if len(row) > 1 else ""

        # 矢印(前のボックスから)
        if i > 0:
            arrow_y1 = y - gap
            arrow_y2 = y
            parts.append(
                f'<line x1="{margin + box_w/2}" y1="{arrow_y1}" '
                f'x2="{margin + box_w/2}" y2="{arrow_y2}" '
                f'stroke="#999999" stroke-width="2" marker-end="url(#arrow)"/>'
            )

        parts.append(
            f'<rect x="{margin}" y="{y}" width="{box_w}" height="{box_h}" rx="10" '
            f'fill="{color}" opacity="0.15" stroke="{color}" stroke-width="1.5"/>'
        )
        parts.append(
            f'<text x="{margin + 16}" y="{y + 24}" font-size="13" font-weight="bold" '
            f'fill="{color}">{_esc(label_cell)}</text>'
        )
        content_lines = _wrap_lines(content_cell, width=34)[:2]
        for li, line in enumerate(content_lines):
            parts.append(
                f'<text x="{margin + 16}" y="{y + 46 + li*18}" font-size="14" '
                f'fill="#222222">{_esc(line)}</text>'
            )
        y += box_h + gap

    parts.append(
        '<defs><marker id="arrow" markerWidth="10" markerHeight="10" refX="5" refY="3" '
        'orient="auto" markerUnits="strokeWidth"><path d="M0,0 L0,6 L6,3 z" fill="#999999"/>'
        '</marker></defs>'
    )
    parts.append("</svg>")
    return "".join(parts)


def build_board_image_svg(lesson_plan_md: str, *, title: str = "板書イメージ") -> str:
    """本時案の「板書計画」コードブロックを、黒板風のビジュアルとしてSVG化する。"""
    sections = split_into_sections(lesson_plan_md)
    target = find_section(sections, "板書")
    board_text = ""
    if target:
        blocks = extract_code_blocks(target.body_lines)
        if blocks:
            board_text = blocks[0]
    if not board_text:
        blocks = extract_code_blocks(lesson_plan_md.split("\n"))
        if blocks:
            board_text = blocks[0]

    if not board_text.strip():
        raise DiagramError(
            "板書計画のコードブロック（```text ... ```）が見つかりませんでした。"
            "「本時案」の成果物から生成してください。"
        )

    lines = board_text.split("\n")
    width, line_h, padding = 800, 34, 40
    height = padding * 2 + len(lines) * line_h + 40

    parts = [
        f'<svg viewBox="0 0 {width} {height}" xmlns="http://www.w3.org/2000/svg">',
        f'<rect width="{width}" height="{height}" fill="#EDE4D3"/>',  # 木枠風の背景
        f'<rect x="20" y="20" width="{width-40}" height="{height-40}" rx="6" '
        f'fill="#1B4332" stroke="#0B2818" stroke-width="8"/>',
        f'<text x="{width/2}" y="52" text-anchor="middle" font-size="16" '
        f'font-family="sans-serif" fill="#EAEAEA" opacity="0.7">{_esc(title)}</text>',
    ]
    y = padding + 50
    for line in lines:
        parts.append(
            f'<text x="{padding + 20}" y="{y}" font-size="22" '
            f'font-family=\'"Yu Mincho", "Hiragino Mincho ProN", serif\' '
            f'fill="#FFFFFF">{_esc(line)}</text>'
        )
        y += line_h
    parts.append("</svg>")
    return "".join(parts)

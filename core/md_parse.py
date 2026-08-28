"""
AIが生成したMarkdownテキストから、見出し単位のセクションや表データを
構造化して取り出す共通パーサー。

docx_builder.py は「行ごとに逐次docxへ書き出す」方式だったが、
pptx/PDF生成では「表だけ取り出す」「見出しごとにまとめる」といった
構造的なアクセスが必要になるため、ここに共通化する。
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field


@dataclass
class Section:
    heading: str
    level: int
    body_lines: list[str] = field(default_factory=list)


def _is_table_line(line: str) -> bool:
    stripped = line.strip()
    return stripped.startswith("|") and stripped.endswith("|")


def _is_table_separator(line: str) -> bool:
    stripped = line.strip()
    return re.match(r"^\|[\s:\-|_]+\|$", stripped) is not None


def split_into_sections(md_text: str) -> list[Section]:
    """## / ### 見出しごとにテキストを分割する。見出しの前の内容は無視。"""
    lines = md_text.split("\n")
    sections: list[Section] = []
    current: Section | None = None

    for line in lines:
        stripped = line.strip()
        m = re.match(r"^(#{1,4})\s+(.*)$", stripped)
        if m:
            if current is not None:
                sections.append(current)
            current = Section(heading=m.group(2), level=len(m.group(1)))
        elif current is not None:
            current.body_lines.append(line)

    if current is not None:
        sections.append(current)
    return sections


def extract_tables(lines: list[str]) -> list[list[list[str]]]:
    """行のリストから、複数の表（それぞれ行×列のセル文字列）を抽出する。
    区切り行(|---|---|)は結果から除外する。"""
    tables: list[list[list[str]]] = []
    i = 0
    while i < len(lines):
        if _is_table_line(lines[i]):
            table_lines = []
            while i < len(lines) and _is_table_line(lines[i]):
                table_lines.append(lines[i].strip())
                i += 1
            valid_rows = [r for r in table_lines if not _is_table_separator(r)]
            rows_data = []
            for r in valid_rows:
                content = r[1:-1]
                cells = [c.strip() for c in content.split("|")]
                rows_data.append(cells)
            if rows_data:
                col_count = max(len(r) for r in rows_data)
                for row in rows_data:
                    while len(row) < col_count:
                        row.append("")
                tables.append(rows_data)
        else:
            i += 1
    return tables


def extract_code_blocks(lines: list[str]) -> list[str]:
    """```text ... ``` で囲まれたコードブロックの中身をそれぞれ1文字列として抽出。"""
    blocks = []
    buf: list[str] | None = None
    for line in lines:
        if line.strip().startswith("```"):
            if buf is None:
                buf = []
            else:
                blocks.append("\n".join(buf))
                buf = None
        elif buf is not None:
            buf.append(line)
    return blocks


def find_section(sections: list[Section], keyword: str) -> Section | None:
    """見出し文字列にkeywordを含む最初のセクションを返す。"""
    for s in sections:
        if keyword in s.heading:
            return s
    return None

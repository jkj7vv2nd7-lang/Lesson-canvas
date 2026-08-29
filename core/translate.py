"""
生成済みの成果物を、ALT（外国語指導助手）や日本語指導が必要な家庭向けに
英語版として作り直すためのプロンプト。

単純な機械翻訳ではなく、対象読者（英語を母語とするALT、または
日本語がまだ得意でない保護者・児童）にとって自然で分かりやすい
表現になるよう指示する。
"""

from __future__ import annotations

TRANSLATE_PROMPT_TEMPLATE = """
あなたは日本の学校教育に精通した、英語ネイティブの翻訳者兼教育アシスタントです。
以下の「{label}」を、ALT（外国語指導助手）や日本語がまだ得意でない保護者・児童にも
伝わる、自然で平易な英語に書き直してください。

【指示】
1. 単なる直訳ではなく、対象読者（英語話者）にとって自然な表現にすること
2. Markdownの構造（見出し ##、表 |...|）は維持すること
3. 表の書式は厳密に保つこと（区切り行、セル内改行禁止）
4. 数式・数字・固有名詞（教科書名等）はそのまま活かすこと
5. 出力は英語版の本文のみとし、日本語の解説や前置きは含めないこと

--- 元の内容 ---
{draft_content}
--- ここまで ---
""".strip()


def build_translate_prompt(label: str, draft_content: str) -> str:
    return TRANSLATE_PROMPT_TEMPLATE.format(label=label, draft_content=draft_content)

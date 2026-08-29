"""
授業構想を始める前に、先生にまとめて入力してもらう「事前情報」。

これまでは会話の中でAIが「学年は？」「教科は？」と一つずつ聞き返すことが
多く、テンポの悪さにつながっていた。ここで一度にまとめて入力してもらい、
最初のメッセージとして構造化した形でAIに渡すことで、AIが同じ質問を
繰り返さずに済み、初手からより具体的な提案ができるようにする。
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class UnitIntake:
    grade: str = ""              # 学年
    subject: str = ""            # 教科
    unit_name: str = ""          # 単元名
    total_hours: str = ""        # 総時数
    objectives: str = ""         # 単元のねらい・身につけさせたい力
    student_situation: str = ""  # 児童生徒の実態・気になる点
    textbook: str = ""           # 使用教科書・教材
    extra_requests: str = ""     # その他の要望（ICT活用したい、グループ活動中心 等）

    def is_empty(self) -> bool:
        return not any([
            self.grade, self.subject, self.unit_name, self.total_hours,
            self.objectives, self.student_situation, self.textbook, self.extra_requests,
        ])

    def summary_label(self) -> str:
        """チャット上に表示する短い要約（ユーザー発言の見た目用）。"""
        bits = [b for b in [self.grade, self.subject, self.unit_name] if b]
        return "・".join(bits) if bits else "授業の事前情報を入力しました"


INTAKE_FIELD_LABELS = {
    "grade": "学年",
    "subject": "教科",
    "unit_name": "単元名",
    "total_hours": "総時数",
    "objectives": "単元のねらい・身につけさせたい力",
    "student_situation": "児童生徒の実態・気になる点",
    "textbook": "使用教科書・教材",
    "extra_requests": "その他の要望",
}


def build_intake_prompt(intake: UnitIntake) -> str:
    """構造化された事前情報を、最初のuserメッセージとして送るテキストに整形する。"""
    lines = ["以下の内容で授業を考えたいです。"]
    for field, label in INTAKE_FIELD_LABELS.items():
        value = getattr(intake, field)
        if value:
            lines.append(f"- {label}: {value}")

    lines.append("")
    lines.append(
        "上記はすでに入力済みの情報です。同じ内容を改めて質問せず、"
        "この情報をもとに、単元の構成案やねらいの具体化について、"
        "最初の提案または的を絞った追加質問から始めてください。"
    )
    return "\n".join(lines)

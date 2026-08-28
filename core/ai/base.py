"""
AIプロバイダーの共通インターフェース。

複数社（Gemini / Claude / OpenAI）のAPIを同じ呼び出し方で使えるようにする。
新しいプロバイダーを追加するときは、このクラスを継承して
stream_chat() を実装すればよい。
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Generator, Iterable, Optional


@dataclass
class ChatMessage:
    """会話1ターン分のメッセージ。role は 'user' か 'assistant'。"""
    role: str
    text: str
    # 画像/PDFなどの添付ファイル（bytes, mime_type, name）のリスト
    attachments: list[dict] = field(default_factory=list)


@dataclass
class ProviderInfo:
    """UIに表示するためのプロバイダー情報。"""
    provider_id: str          # "gemini" / "claude" / "openai"
    display_name: str         # "Google Gemini"
    models: list[str]         # 選択可能なモデル名の一覧
    supports_files: bool = True   # 画像/PDFを直接渡せるか
    strengths: str = ""       # UIに出す一言（例: "資料の読み込みに強い"）


class AIProvider(ABC):
    """各社AI APIの薄いラッパー。全プロバイダーはこれを継承する。"""

    info: ProviderInfo

    def __init__(self, api_key: str, model: str):
        self.api_key = api_key
        self.model = model

    @abstractmethod
    def stream_chat(
        self,
        system_prompt: str,
        history: Iterable[ChatMessage],
    ) -> Generator[str, None, None]:
        """
        system_prompt: 常駐のシステム指示
        history: これまでの会話（最後がuserメッセージであること）
        戻り値: テキストチャンクを順次yieldするジェネレータ
        """
        raise NotImplementedError

    def chat(self, system_prompt: str, history: Iterable[ChatMessage]) -> str:
        """ストリーミングせず、全文を一括で返す簡易版。"""
        return "".join(self.stream_chat(system_prompt, history))


class ProviderError(Exception):
    """APIキー不正・レート制限・ネットワークエラーなどを統一的に扱う例外。"""

    def __init__(self, provider_id: str, message: str, original: Optional[Exception] = None):
        self.provider_id = provider_id
        self.original = original
        super().__init__(f"[{provider_id}] {message}")

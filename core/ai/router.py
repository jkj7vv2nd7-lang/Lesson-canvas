"""
複数のAIプロバイダーを一元管理するルーター。

- UIからは「どのプロバイダー・どのモデルを使うか」を指定するだけでよい
- APIキーが未設定のプロバイダーは自動的に選択肢から除外される
- 1つのプロバイダーで失敗した場合、フォールバック先を試すことができる
"""

from __future__ import annotations

from typing import Generator, Iterable, Optional

from .base import AIProvider, ChatMessage, ProviderError, ProviderInfo
from .claude_provider import ClaudeProvider
from .gemini_provider import GeminiProvider
from .openai_provider import OpenAIProvider

_PROVIDER_CLASSES = {
    "gemini": GeminiProvider,
    "claude": ClaudeProvider,
    "openai": OpenAIProvider,
}


class AIRouter:
    def __init__(self, api_keys: dict[str, str]):
        """api_keys: {"gemini": "...", "claude": "...", "openai": "..."}
        値が空文字/Noneのプロバイダーは利用不可として扱う。"""
        self.api_keys = {k: v for k, v in api_keys.items() if v}

    def available_providers(self) -> list[ProviderInfo]:
        """APIキーが設定済みのプロバイダー情報一覧。"""
        return [
            cls.info for pid, cls in _PROVIDER_CLASSES.items() if pid in self.api_keys
        ]

    def all_providers(self) -> list[ProviderInfo]:
        """APIキー有無に関わらず全プロバイダー情報一覧（UI表示用）。"""
        return [cls.info for cls in _PROVIDER_CLASSES.values()]

    def get_provider(self, provider_id: str, model: str) -> AIProvider:
        if provider_id not in self.api_keys:
            raise ProviderError(provider_id, "APIキーが設定されていません")
        cls = _PROVIDER_CLASSES[provider_id]
        return cls(api_key=self.api_keys[provider_id], model=model)

    def stream_chat(
        self,
        provider_id: str,
        model: str,
        system_prompt: str,
        history: Iterable[ChatMessage],
        fallback: Optional[tuple[str, str]] = None,
    ) -> Generator[str, None, None]:
        """fallback=(provider_id, model) を指定すると、主プロバイダー失敗時に自動で切り替える。"""
        history = list(history)
        try:
            provider = self.get_provider(provider_id, model)
            yield from provider.stream_chat(system_prompt, history)
        except ProviderError:
            if fallback is None:
                raise
            fb_provider = self.get_provider(*fallback)
            yield from fb_provider.stream_chat(system_prompt, history)

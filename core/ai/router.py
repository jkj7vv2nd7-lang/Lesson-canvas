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

    def chat_with_retry(
        self,
        provider_id: str,
        model: str,
        system_prompt: str,
        history: Iterable[ChatMessage],
        *,
        attempts: int = 3,
        backoff_seconds: float = 3.0,
        allow_provider_fallback: bool = True,
    ) -> str:
        """一括生成（ブラッシュアップ・別パターン・翻訳等）向けの、失敗時に自動再試行する
        ヘルパー。

        - タイムアウトや混雑など一時的なエラーの場合、少し待ってから同じ
          プロバイダーに再試行する（サービス側の混雑が収まるのを待つ狙い）
        - APIの利用上限（クォータ）エラーの場合は、同じプロバイダーへの
          再試行では解決しないため、他に設定済みのAIプロバイダーがあれば
          自動的にそちらへ切り替えて試す（allow_provider_fallback=True の場合）
        - それ以外（APIキー不正等）は即座に例外を投げる
        """
        import time

        from ..errors import is_quota_error, is_transient_error

        history = list(history)
        last_error: Exception | None = None

        for attempt in range(attempts):
            try:
                provider = self.get_provider(provider_id, model)
                return "".join(provider.stream_chat(system_prompt, history))
            except Exception as e:
                last_error = e
                if attempt < attempts - 1 and is_transient_error(e):
                    time.sleep(backoff_seconds * (attempt + 1))  # 3秒→6秒と徐々に長く待つ
                    continue
                break

        # クォータ切れの場合、他に使えるプロバイダーがあれば自動的に切り替えて試す
        if allow_provider_fallback and last_error is not None and is_quota_error(last_error):
            other_provider_ids = [pid for pid in self.api_keys if pid != provider_id]
            for other_pid in other_provider_ids:
                try:
                    other_model = _PROVIDER_CLASSES[other_pid].info.models[0]
                    other_provider = self.get_provider(other_pid, other_model)
                    return "".join(other_provider.stream_chat(system_prompt, history))
                except Exception as e:
                    last_error = e
                    continue

        raise last_error

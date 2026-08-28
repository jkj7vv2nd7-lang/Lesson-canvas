"""OpenAI プロバイダー。汎用・他社との比較用途。"""

from __future__ import annotations

import base64
from typing import Generator, Iterable

from .base import AIProvider, ChatMessage, ProviderError, ProviderInfo

from openai import OpenAI


class OpenAIProvider(AIProvider):
    info = ProviderInfo(
        provider_id="openai",
        display_name="OpenAI",
        models=["gpt-5.1", "gpt-5.1-mini"],
        supports_files=True,
        strengths="汎用性が高く、他社の出力との比較に便利",
    )

    def _to_content_blocks(self, msg: ChatMessage) -> list:
        blocks = []
        if msg.text:
            blocks.append({"type": "text", "text": msg.text})
        for att in msg.attachments:
            if att["mime_type"].startswith("image/"):
                b64 = base64.b64encode(att["data"]).decode()
                blocks.append({
                    "type": "image_url",
                    "image_url": {"url": f"data:{att['mime_type']};base64,{b64}"},
                })
            # OpenAIのPDF直接読み込みはFiles API経由が必要なため、
            # ここでは事前にテキスト抽出したものをtextとして渡す運用を推奨(sources.py側で処理)
        return blocks or [{"type": "text", "text": ""}]

    def stream_chat(
        self, system_prompt: str, history: Iterable[ChatMessage]
    ) -> Generator[str, None, None]:
        try:
            client = OpenAI(api_key=self.api_key)
            messages = [{"role": "system", "content": system_prompt}]
            for msg in history:
                messages.append({
                    "role": msg.role,
                    "content": self._to_content_blocks(msg),
                })
            with client.chat.completions.stream(
                model=self.model,
                messages=messages,
                temperature=0.4,
            ) as stream:
                for event in stream:
                    if event.type == "content.delta":
                        yield event.delta
        except Exception as e:
            raise ProviderError("openai", str(e), e) from e

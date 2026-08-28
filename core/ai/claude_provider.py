"""Anthropic Claude プロバイダー。対話での壁打ち・論理構成の相談に強い。"""

from __future__ import annotations

import base64
from typing import Generator, Iterable

from .base import AIProvider, ChatMessage, ProviderError, ProviderInfo

import anthropic


class ClaudeProvider(AIProvider):
    info = ProviderInfo(
        provider_id="claude",
        display_name="Anthropic Claude",
        models=["claude-sonnet-4-6", "claude-opus-4-6"],
        supports_files=True,
        strengths="対話しながら授業構想を練る『壁打ち』に強い",
    )

    def _to_content_blocks(self, msg: ChatMessage) -> list:
        blocks = []
        for att in msg.attachments:
            if att["mime_type"].startswith("image/"):
                blocks.append({
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": att["mime_type"],
                        "data": base64.b64encode(att["data"]).decode(),
                    },
                })
            elif att["mime_type"] == "application/pdf":
                blocks.append({
                    "type": "document",
                    "source": {
                        "type": "base64",
                        "media_type": "application/pdf",
                        "data": base64.b64encode(att["data"]).decode(),
                    },
                })
        if msg.text:
            blocks.append({"type": "text", "text": msg.text})
        return blocks or [{"type": "text", "text": ""}]

    def stream_chat(
        self, system_prompt: str, history: Iterable[ChatMessage]
    ) -> Generator[str, None, None]:
        try:
            client = anthropic.Anthropic(api_key=self.api_key)
            messages = [
                {"role": msg.role, "content": self._to_content_blocks(msg)}
                for msg in history
            ]
            with client.messages.stream(
                model=self.model,
                max_tokens=4096,
                system=system_prompt,
                messages=messages,
            ) as stream:
                for text in stream.text_stream:
                    yield text
        except Exception as e:
            raise ProviderError("claude", str(e), e) from e

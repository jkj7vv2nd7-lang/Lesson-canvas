"""Google Gemini プロバイダー。画像・PDFの直接読み込みに強い。"""

from __future__ import annotations

import io
from typing import Generator, Iterable

from .base import AIProvider, ChatMessage, ProviderError, ProviderInfo

try:
    from google import genai
    from google.genai import types as genai_types
    _USE_NEW_SDK = True
except ImportError:
    import google.generativeai as genai  # type: ignore
    _USE_NEW_SDK = False


class GeminiProvider(AIProvider):
    info = ProviderInfo(
        provider_id="gemini",
        display_name="Google Gemini",
        models=["gemini-2.5-flash", "gemini-2.5-pro"],
        supports_files=True,
        strengths="教科書の画像・PDFを直接読み込ませるのに強い",
    )

    def _to_gemini_parts(self, msg: ChatMessage) -> list:
        parts = [msg.text] if msg.text else []
        for att in msg.attachments:
            if att["mime_type"].startswith("image/"):
                from PIL import Image
                parts.append(Image.open(io.BytesIO(att["data"])))
            elif att["mime_type"] == "application/pdf" and _USE_NEW_SDK:
                parts.append(
                    genai_types.Part.from_bytes(
                        data=att["data"], mime_type="application/pdf"
                    )
                )
        return parts

    def stream_chat(
        self, system_prompt: str, history: Iterable[ChatMessage]
    ) -> Generator[str, None, None]:
        history = list(history)
        try:
            if _USE_NEW_SDK:
                client = genai.Client(api_key=self.api_key)
                contents = []
                for msg in history:
                    role = "model" if msg.role == "assistant" else "user"
                    contents.append(
                        genai_types.Content(
                            role=role,
                            parts=[
                                p if isinstance(p, genai_types.Part) else genai_types.Part(text=p)
                                if isinstance(p, str) else p
                                for p in self._to_gemini_parts(msg)
                            ] or [genai_types.Part(text="")],
                        )
                    )
                stream = client.models.generate_content_stream(
                    model=self.model,
                    contents=contents,
                    config=genai_types.GenerateContentConfig(
                        system_instruction=system_prompt,
                        temperature=0.4,
                    ),
                )
                for chunk in stream:
                    if chunk.text:
                        yield chunk.text
            else:
                genai.configure(api_key=self.api_key)
                model = genai.GenerativeModel(
                    model_name=self.model, system_instruction=system_prompt
                )
                # 旧SDKはマルチターンより「直前のuserメッセージ+添付」を渡す簡易実装
                last_user = next((m for m in reversed(history) if m.role == "user"), None)
                payload = self._to_gemini_parts(last_user) if last_user else [""]
                response = model.generate_content(
                    payload,
                    stream=True,
                    generation_config=genai.types.GenerationConfig(temperature=0.4),
                )
                for chunk in response:
                    if chunk.text:
                        yield chunk.text
        except Exception as e:
            raise ProviderError("gemini", str(e), e) from e

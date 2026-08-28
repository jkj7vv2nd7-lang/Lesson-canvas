"""
AI呼び出しで起きがちなエラーを、非エンジニアの先生にも分かる日本語メッセージに変換する。
"""

from __future__ import annotations


def friendly_error_message(e: Exception) -> str:
    text = str(e).lower()

    if "api key" in text or "api_key" in text or "authentication" in text or "unauthorized" in text or "invalid x-api-key" in text:
        return "🔑 APIキーが正しくないか、有効になっていない可能性があります。サイドバーのキーをご確認ください。"

    if "quota" in text or "rate limit" in text or "429" in text or "resource_exhausted" in text:
        return "⏳ APIの利用上限（クォータ）に達した可能性があります。少し時間をおくか、サイドバーで別のAIに切り替えてお試しください。"

    if "timeout" in text or "timed out" in text:
        return "🌐 通信がタイムアウトしました。ネットワーク状況をご確認の上、もう一度お試しください。"

    if "overloaded" in text or "503" in text or "502" in text:
        return "🛠 AIサービスが混み合っているようです。少し時間をおいてからもう一度お試しください。"

    if "safety" in text or "blocked" in text or "content_filter" in text:
        return "⚠️ 内容が安全フィルターに引っかかった可能性があります。表現を変えて再度お試しください。"

    return f"❌ エラーが発生しました: {e}"

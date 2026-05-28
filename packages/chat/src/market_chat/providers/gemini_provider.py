"""Google Gemini provider.

The ``google-generativeai`` SDK is imported lazily so the project doesn't
require it. Missing SDK => ``is_configured()`` returns False and the router
skips this provider.
"""

from __future__ import annotations

import os
import time

from .base import ChatMessage, ChatProvider, ProviderResponse


_PRICING: dict[str, tuple[float, float]] = {
    "gemini-2.0-flash-exp": (0.075, 0.30),
    "gemini-2.0-flash": (0.075, 0.30),
    "gemini-1.5-flash": (0.075, 0.30),
    "gemini-1.5-pro": (1.25, 5.0),
}


class GeminiChatProvider(ChatProvider):
    name = "gemini"
    default_model = "gemini-2.0-flash-exp"

    def __init__(self) -> None:
        self._api_key = os.getenv("CHAT_GEMINI_API_KEY", "").strip()
        self._model = os.getenv("CHAT_GEMINI_MODEL", "").strip() or self.default_model

    def _sdk_available(self) -> bool:
        try:
            import google.generativeai  # noqa: F401
        except Exception:
            return False
        return True

    def is_configured(self) -> bool:
        return bool(self._api_key) and self._sdk_available()

    def estimate_cost(self, tokens_in: int, tokens_out: int, model: str) -> float:
        pricing = _PRICING.get(model)
        if not pricing:
            return 0.0
        in_rate, out_rate = pricing
        return round((tokens_in / 1_000_000) * in_rate + (tokens_out / 1_000_000) * out_rate, 6)

    def chat(
        self,
        messages: list[ChatMessage],
        system: str | None = None,
        model: str | None = None,
    ) -> ProviderResponse:
        import google.generativeai as genai  # type: ignore

        if not self._api_key:
            raise RuntimeError("CHAT_GEMINI_API_KEY is not set.")

        chosen = model or self._model
        genai.configure(api_key=self._api_key)

        # Gemini uses "user" / "model" roles and a separate system instruction.
        history = []
        for m in messages[:-1]:
            if m.role == "system":
                continue
            history.append(
                {
                    "role": "user" if m.role == "user" else "model",
                    "parts": [m.content],
                }
            )
        last = messages[-1] if messages else ChatMessage(role="user", content="")

        client = genai.GenerativeModel(
            model_name=chosen,
            system_instruction=system or None,
        )
        chat_session = client.start_chat(history=history)

        started = time.perf_counter()
        response = chat_session.send_message(last.content)
        latency_ms = int((time.perf_counter() - started) * 1000)

        text = (getattr(response, "text", None) or "").strip()
        usage = getattr(response, "usage_metadata", None)
        tokens_in = int(getattr(usage, "prompt_token_count", 0) or 0)
        tokens_out = int(getattr(usage, "candidates_token_count", 0) or 0)

        return ProviderResponse(
            text=text,
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            cost_usd=self.estimate_cost(tokens_in, tokens_out, chosen),
            latency_ms=latency_ms,
            model=chosen,
            provider=self.name,
        )

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
    "gemini-2.5-flash": (0.30, 2.50),
    "gemini-2.5-pro": (1.25, 10.0),
    "gemini-2.0-flash-exp": (0.075, 0.30),
    "gemini-2.0-flash": (0.075, 0.30),
    "gemini-1.5-flash": (0.075, 0.30),
    "gemini-1.5-pro": (1.25, 5.0),
}


class GeminiChatProvider(ChatProvider):
    name = "gemini"
    default_model = "gemini-2.5-flash"

    def __init__(self) -> None:
        self._api_key = os.getenv("CHAT_GEMINI_API_KEY", "").strip()
        self._model = os.getenv("CHAT_GEMINI_MODEL", "").strip() or self.default_model
        self._temperature = float(os.getenv("CHAT_GEMINI_TEMPERATURE", "0.2") or 0.2)
        # 420 was far too low — gemini-2.5-flash is a "thinking" model that
        # spends part of its output budget reasoning, so a tiny cap returned
        # truncated or empty replies ("recortado"). 2048 gives room for a
        # full answer plus the model's internal thinking.
        self._max_output_tokens = int(os.getenv("CHAT_GEMINI_MAX_OUTPUT_TOKENS", "2048") or 2048)
        self._max_history_messages = max(
            int(os.getenv("CHAT_GEMINI_MAX_HISTORY_MESSAGES", "12") or 12),
            2,
        )
        self._sdk_configured = False

    def _sdk_available(self) -> bool:
        try:
            import google.generativeai  # noqa: F401
        except Exception:
            return False
        return True

    def is_configured(self) -> bool:
        return bool(self._api_key) and self._sdk_available()

    def _ensure_sdk(self):
        import google.generativeai as genai  # type: ignore

        if not self._sdk_configured:
            genai.configure(api_key=self._api_key)
            self._sdk_configured = True
        return genai

    def _trim_messages(self, messages: list[ChatMessage]) -> list[ChatMessage]:
        if len(messages) <= self._max_history_messages:
            return messages
        tail = messages[-self._max_history_messages :]
        return [message for message in tail if message.role in {"user", "assistant"}] or tail

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
        tools=None,
        tool_executor=None,
    ) -> ProviderResponse:
        if not self._api_key:
            raise RuntimeError("CHAT_GEMINI_API_KEY is not set.")

        genai = self._ensure_sdk()
        chosen = model or self._model
        prompt_messages = self._trim_messages(messages)

        # Gemini uses "user" / "model" roles and a separate system instruction.
        history = []
        for m in prompt_messages[:-1]:
            if m.role == "system":
                continue
            history.append(
                {
                    "role": "user" if m.role == "user" else "model",
                    "parts": [m.content],
                }
            )
        last = prompt_messages[-1] if prompt_messages else ChatMessage(role="user", content="")

        client = genai.GenerativeModel(
            model_name=chosen,
            system_instruction=system or None,
            generation_config={
                "temperature": self._temperature,
                "max_output_tokens": self._max_output_tokens,
            },
        )
        chat_session = client.start_chat(history=history)

        started = time.perf_counter()
        response = chat_session.send_message(
            last.content,
            request_options={"timeout": 20},
        )
        latency_ms = int((time.perf_counter() - started) * 1000)

        # Gemini raises when you read `.text` on a blocked/empty/MAX_TOKENS
        # response instead of returning an empty string. Guard it and fall
        # back to digging the candidate parts so the user gets *something*
        # instead of a 500.
        text = ""
        try:
            text = (getattr(response, "text", None) or "").strip()
        except Exception:
            text = ""
        if not text:
            try:
                candidates = getattr(response, "candidates", None) or []
                for candidate in candidates:
                    parts = getattr(getattr(candidate, "content", None), "parts", None) or []
                    joined = "".join(getattr(p, "text", "") or "" for p in parts).strip()
                    if joined:
                        text = joined
                        break
            except Exception:
                text = ""
        if not text:
            text = "_(El modelo no devolvió texto. Probá reformular la pregunta o achicarla.)_"
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

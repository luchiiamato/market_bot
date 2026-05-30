"""OpenAI ChatGPT provider.

The ``openai`` SDK is imported lazily so the project doesn't take a hard
dependency on it. If it can't be imported, ``is_configured()`` returns False.
"""

from __future__ import annotations

import os
import time

from .base import ChatMessage, ChatProvider, ProviderResponse


_PRICING: dict[str, tuple[float, float]] = {
    "gpt-4o-mini": (0.15, 0.60),
    "gpt-4o": (2.50, 10.0),
    "gpt-4.1-mini": (0.40, 1.60),
    "gpt-4.1": (2.00, 8.0),
}


class OpenAIChatProvider(ChatProvider):
    name = "openai"
    default_model = "gpt-4o-mini"

    def __init__(self) -> None:
        self._api_key = os.getenv("CHAT_OPENAI_API_KEY", "").strip()
        self._model = os.getenv("CHAT_OPENAI_MODEL", "").strip() or self.default_model

    def _sdk_available(self) -> bool:
        try:
            import openai  # noqa: F401
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
        tools=None,
        tool_executor=None,
    ) -> ProviderResponse:
        import openai  # type: ignore

        if not self._api_key:
            raise RuntimeError("CHAT_OPENAI_API_KEY is not set.")

        chosen = model or self._model
        client = openai.OpenAI(api_key=self._api_key)

        payload: list[dict] = []
        if system:
            payload.append({"role": "system", "content": system})
        payload.extend({"role": m.role, "content": m.content} for m in messages)

        started = time.perf_counter()
        response = client.chat.completions.create(
            model=chosen,
            messages=payload,
            max_tokens=1024,
        )
        latency_ms = int((time.perf_counter() - started) * 1000)

        choices = getattr(response, "choices", None) or []
        text = ""
        if choices:
            message = getattr(choices[0], "message", None)
            if message is not None:
                text = (getattr(message, "content", None) or "").strip()

        usage = getattr(response, "usage", None)
        tokens_in = int(getattr(usage, "prompt_tokens", 0) or 0)
        tokens_out = int(getattr(usage, "completion_tokens", 0) or 0)

        return ProviderResponse(
            text=text,
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            cost_usd=self.estimate_cost(tokens_in, tokens_out, chosen),
            latency_ms=latency_ms,
            model=chosen,
            provider=self.name,
        )

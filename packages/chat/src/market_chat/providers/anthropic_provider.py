"""Anthropic Claude provider.

The ``anthropic`` SDK is imported lazily inside the methods so that the
project does not gain a hard dependency on it. If the SDK is not installed
``is_configured()`` returns ``False`` and the router will skip this provider.
"""

from __future__ import annotations

import os
import time

from .base import ChatMessage, ChatProvider, ProviderResponse


# Best-effort USD-per-1M-token pricing snapshot. The dict is intentionally
# small — adding a new model only takes one line.
_PRICING: dict[str, tuple[float, float]] = {
    "claude-sonnet-4-5": (3.0, 15.0),
    "claude-3-5-sonnet-latest": (3.0, 15.0),
    "claude-3-5-haiku-latest": (0.80, 4.0),
    "claude-3-opus-latest": (15.0, 75.0),
}


class AnthropicChatProvider(ChatProvider):
    name = "anthropic"
    default_model = "claude-sonnet-4-5"

    def __init__(self) -> None:
        self._api_key = os.getenv("CHAT_ANTHROPIC_API_KEY", "").strip()
        self._model = os.getenv("CHAT_ANTHROPIC_MODEL", "").strip() or self.default_model

    def _sdk_available(self) -> bool:
        try:
            import anthropic  # noqa: F401
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
        # Lazy import — see module docstring.
        import anthropic  # type: ignore

        if not self._api_key:
            raise RuntimeError("CHAT_ANTHROPIC_API_KEY is not set.")

        chosen = model or self._model
        client = anthropic.Anthropic(api_key=self._api_key)

        # Anthropic separates the system prompt from the user/assistant turns,
        # and forbids "system" entries inside ``messages``.
        payload = [
            {"role": m.role, "content": m.content}
            for m in messages
            if m.role in {"user", "assistant"}
        ]

        started = time.perf_counter()
        response = client.messages.create(
            model=chosen,
            system=system or "",
            max_tokens=1024,
            messages=payload,
        )
        latency_ms = int((time.perf_counter() - started) * 1000)

        text_chunks: list[str] = []
        for block in getattr(response, "content", []) or []:
            text = getattr(block, "text", None)
            if text:
                text_chunks.append(text)
        text = "".join(text_chunks).strip()

        usage = getattr(response, "usage", None)
        tokens_in = int(getattr(usage, "input_tokens", 0) or 0)
        tokens_out = int(getattr(usage, "output_tokens", 0) or 0)

        return ProviderResponse(
            text=text,
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            cost_usd=self.estimate_cost(tokens_in, tokens_out, chosen),
            latency_ms=latency_ms,
            model=chosen,
            provider=self.name,
        )

"""Anthropic Claude provider.

The ``anthropic`` SDK is imported lazily inside the methods so that the
project does not gain a hard dependency on it. If the SDK is not installed
``is_configured()`` returns ``False`` and the router will skip this provider.
"""

from __future__ import annotations

import os
import time
from typing import Any, Callable

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
        tools: list[dict[str, Any]] | None = None,
        tool_executor: Callable[[str, dict[str, Any]], str] | None = None,
    ) -> ProviderResponse:
        # Lazy import — see module docstring.
        import anthropic  # type: ignore

        if not self._api_key:
            raise RuntimeError("CHAT_ANTHROPIC_API_KEY is not set.")

        chosen = model or self._model
        client = anthropic.Anthropic(api_key=self._api_key)

        # Anthropic separates the system prompt from the user/assistant turns,
        # and forbids "system" entries inside ``messages``.
        payload: list[dict] = [
            {"role": m.role, "content": m.content}
            for m in messages
            if m.role in {"user", "assistant"}
        ]

        started = time.perf_counter()
        total_in = total_out = 0

        # Tool-use loop: keep calling the model until it stops asking for tools
        # or we hit the safety limit. Without tools, this runs exactly once.
        max_tool_rounds = 5
        for _ in range(max_tool_rounds):
            kwargs: dict[str, Any] = {
                "model": chosen,
                "system": system or "",
                "max_tokens": 1024,
                "messages": payload,
            }
            if tools:
                kwargs["tools"] = tools

            response = client.messages.create(**kwargs)

            usage = getattr(response, "usage", None)
            total_in += int(getattr(usage, "input_tokens", 0) or 0)
            total_out += int(getattr(usage, "output_tokens", 0) or 0)

            stop_reason = getattr(response, "stop_reason", None)
            content_blocks = getattr(response, "content", []) or []

            # If no tool calls, collect text and return.
            tool_use_blocks = [b for b in content_blocks if getattr(b, "type", None) == "tool_use"]
            if not tool_use_blocks or not tool_executor:
                text_chunks = [
                    getattr(b, "text", "")
                    for b in content_blocks
                    if getattr(b, "type", None) == "text"
                ]
                text = "".join(text_chunks).strip()
                break

            # Execute each tool call and collect results.
            # First: append the assistant's tool-use turn to the payload.
            payload.append({"role": "assistant", "content": content_blocks})

            tool_results = []
            for tb in tool_use_blocks:
                tool_name = getattr(tb, "name", "")
                tool_input = getattr(tb, "input", {}) or {}
                tool_id = getattr(tb, "id", "")
                try:
                    result_text = tool_executor(tool_name, tool_input)
                except Exception as exc:
                    result_text = f"Error ejecutando {tool_name}: {exc}"
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": tool_id,
                    "content": str(result_text),
                })

            payload.append({"role": "user", "content": tool_results})

            # If stop_reason is "end_turn" there's nothing more to loop.
            if stop_reason == "end_turn":
                text = ""
                break
        else:
            text = "(límite de rondas de tool-use alcanzado)"

        latency_ms = int((time.perf_counter() - started) * 1000)

        return ProviderResponse(
            text=text,
            tokens_in=total_in,
            tokens_out=total_out,
            cost_usd=self.estimate_cost(total_in, total_out, chosen),
            latency_ms=latency_ms,
            model=chosen,
            provider=self.name,
        )

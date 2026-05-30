"""Abstract chat-provider interface.

Every concrete provider (Anthropic / OpenAI / Gemini) implements this contract
so the router can swap them at runtime. The HTTP layer never imports a
provider directly — it asks the router for the configured one.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Callable


@dataclass
class ChatMessage:
    """A single turn in the conversation, provider-agnostic.

    ``role`` is one of ``"user"``, ``"assistant"`` or ``"system"``. We keep the
    field free-form (no Enum) because the three SDKs each have subtly different
    enums and we coerce on the way in/out instead.
    """

    role: str
    content: str


@dataclass
class ProviderResponse:
    """Homogenised completion result returned by every provider.

    ``cost_usd`` is a best-effort estimate from the provider's published
    pricing — see each provider's ``_PRICING`` dict for the values used.
    """

    text: str
    tokens_in: int
    tokens_out: int
    cost_usd: float
    latency_ms: int
    model: str
    provider: str


class ChatProvider(ABC):
    """Base class for chat providers. Subclasses MUST set ``name`` and ``default_model``."""

    name: str = "base"
    default_model: str = ""

    @abstractmethod
    def is_configured(self) -> bool:
        """True iff both the SDK is importable and an API key is present."""

    @abstractmethod
    def chat(
        self,
        messages: list[ChatMessage],
        system: str | None = None,
        model: str | None = None,
        tools: list[dict[str, Any]] | None = None,
        tool_executor: Callable[[str, dict[str, Any]], str] | None = None,
    ) -> ProviderResponse:
        """Blocking single-shot (or tool-loop) completion.

        When ``tools`` and ``tool_executor`` are provided, the provider may
        execute one or more tool calls before returning the final text.
        Providers that don't support tool use should ignore both parameters
        and fall through to a normal completion.
        """

    def estimate_cost(self, tokens_in: int, tokens_out: int, model: str) -> float:
        """Default 0.0 — providers override with their pricing table."""

        return 0.0

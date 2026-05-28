"""Chat provider router.

Owns the registry of providers, decides which one is the default, and exposes
a public-safe listing for ``GET /chat/providers`` (never returns secrets).
"""

from __future__ import annotations

import os
from typing import Iterable

from .providers.anthropic_provider import AnthropicChatProvider
from .providers.base import ChatProvider
from .providers.gemini_provider import GeminiChatProvider
from .providers.openai_provider import OpenAIChatProvider

PROVIDER_LABELS = {
    "anthropic": "Claude",
    "gemini": "Gemini",
    "openai": "OpenAI",
}


class ChatRouterError(RuntimeError):
    """Raised when no provider can handle a request (unknown name, none configured...)."""


class ChatRouter:
    """Holds the instantiated providers and exposes selection helpers.

    Providers are constructed eagerly in ``__init__`` but they only *read*
    env vars + check SDK availability — no network calls happen at boot.
    """

    def __init__(self, providers: Iterable[ChatProvider] | None = None) -> None:
        if providers is None:
            providers = [
                AnthropicChatProvider(),
                OpenAIChatProvider(),
                GeminiChatProvider(),
            ]
        self._providers: dict[str, ChatProvider] = {p.name: p for p in providers}

    @property
    def providers(self) -> dict[str, ChatProvider]:
        return dict(self._providers)

    def available_providers(self) -> list[dict]:
        """Public-safe listing for ``GET /chat/providers``.

        Returns ``[{id, configured, model}, ...]`` — never the API key.
        """

        return [
            {
                "id": provider.name,
                "label": PROVIDER_LABELS.get(provider.name, provider.name),
                "configured": provider.is_configured(),
                "model": getattr(provider, "_model", provider.default_model),
            }
            for provider in self._providers.values()
        ]

    def get_provider(self, name: str) -> ChatProvider:
        provider = self._providers.get(name)
        if provider is None:
            raise ChatRouterError(f"Provider desconocido: {name!r}.")
        if not provider.is_configured():
            raise ChatRouterError(
                f"El provider {name!r} no está configurado (faltan API key o SDK)."
            )
        return provider

    def default_provider(self) -> ChatProvider:
        """Return the env-default provider, falling back to the first configured one.

        Raises :class:`ChatRouterError` if no provider is configured.
        """

        preferred = os.getenv("CHAT_PROVIDER_DEFAULT", "").strip().lower()
        if preferred:
            provider = self._providers.get(preferred)
            if provider is not None and provider.is_configured():
                return provider
        for provider in self._providers.values():
            if provider.is_configured():
                return provider
        raise ChatRouterError("Ningún provider de chat está configurado.")

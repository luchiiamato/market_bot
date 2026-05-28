"""Market Bot multi-provider chat layer (Sprint 8).

Lazy-loads the optional SDKs (anthropic / openai / google-generativeai) inside
each provider so the project doesn't require any of them to be installed.

Public surface:

* :class:`ChatRouter` — picks a configured provider by name with sensible
  default-fallback semantics.
* :class:`ChatProvider` and :class:`ProviderResponse` — the abstract base +
  the homogenised response shape used by the API layer.
* Store helpers (``create_thread`` etc.) for SQLite persistence sharing the
  identity DB.
* Pydantic schemas used by the FastAPI routes.
"""

from .providers.base import ChatMessage, ChatProvider, ProviderResponse
from .router import ChatRouter, ChatRouterError
from .schemas import (
    ChatMessageRequest,
    ChatMessageResponse,
    ChatProviderInfo,
    ChatThreadCreateRequest,
    ChatThreadResponse,
    ChatUsageResponse,
    ChatUsageRow,
)
from .store import (
    SYSTEM_PROMPT_BASELINE,
    append_message,
    create_thread,
    ensure_chat_schema,
    get_thread,
    list_messages,
    list_threads,
    usage_for_user,
)

__all__ = [
    "ChatMessage",
    "ChatMessageRequest",
    "ChatMessageResponse",
    "ChatProvider",
    "ChatProviderInfo",
    "ChatRouter",
    "ChatRouterError",
    "ChatThreadCreateRequest",
    "ChatThreadResponse",
    "ChatUsageResponse",
    "ChatUsageRow",
    "ProviderResponse",
    "SYSTEM_PROMPT_BASELINE",
    "append_message",
    "create_thread",
    "ensure_chat_schema",
    "get_thread",
    "list_messages",
    "list_threads",
    "usage_for_user",
]

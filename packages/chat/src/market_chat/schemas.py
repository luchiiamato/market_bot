"""Pydantic schemas for the chat HTTP layer.

Kept inside the package (rather than ``services/api/schemas.py``) so that the
chat module is self-contained — if we ever spin it out to a second service it
moves wholesale.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class ChatProviderInfo(BaseModel):
    id: str
    label: str
    configured: bool
    model: str


class ChatThreadCreateRequest(BaseModel):
    title: Optional[str] = Field(default=None, max_length=120)
    provider: Optional[str] = Field(default=None, max_length=32)
    model: Optional[str] = Field(default=None, max_length=80)


class ChatThreadUpdateRequest(BaseModel):
    title: str = Field(min_length=1, max_length=120)


class ChatThreadResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    provider: Optional[str] = None
    model: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class ChatMessageRequest(BaseModel):
    role: str = Field(default="user", pattern="^(user|system)$")
    content: str = Field(min_length=1, max_length=8000)
    provider: Optional[str] = Field(default=None, max_length=32)
    model: Optional[str] = Field(default=None, max_length=80)


class ChatMessageResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    thread_id: int
    role: str
    content: str
    provider: Optional[str] = None
    model: Optional[str] = None
    tokens_in: int = 0
    tokens_out: int = 0
    cost_usd: float = 0.0
    latency_ms: int = 0
    created_at: datetime


class ChatSendResponse(BaseModel):
    """Returned by ``POST /chat/threads/{id}/messages``.

    Contains both the persisted user message and the assistant reply so the
    UI can render the round-trip atomically.
    """

    user_message: ChatMessageResponse
    assistant_message: ChatMessageResponse
    usage: dict


class ChatUsageRow(BaseModel):
    provider: str
    tokens_in: int
    tokens_out: int
    cost_usd: float
    message_count: int


class ChatUsageResponse(BaseModel):
    user_id: int
    total_tokens_in: int
    total_tokens_out: int
    total_cost_usd: float
    total_messages: int
    cost_today_usd: float
    cost_month_usd: float
    by_provider: list[ChatUsageRow]

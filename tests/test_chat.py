"""Tests for the Sprint 8 chat backend.

All tests run offline: every concrete provider's ``chat()`` method is
monkeypatched to return a deterministic :class:`ProviderResponse`, and the
SQLite DB is the per-test temp file installed by ``conftest._reset_db``.
"""

from __future__ import annotations

import pytest


# ---------------------------------------------------------------------------
# Provider base + concrete provider configuration
# ---------------------------------------------------------------------------


def test_provider_not_configured_when_key_missing(monkeypatch):
    """Each concrete provider must report ``is_configured=False`` when the API
    key env var is absent — regardless of whether the SDK is installed."""

    monkeypatch.delenv("CHAT_ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("CHAT_OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("CHAT_GEMINI_API_KEY", raising=False)

    from market_chat.providers import (
        AnthropicChatProvider,
        GeminiChatProvider,
        OpenAIChatProvider,
    )

    assert AnthropicChatProvider().is_configured() is False
    assert OpenAIChatProvider().is_configured() is False
    assert GeminiChatProvider().is_configured() is False


def test_provider_base_subclass_returns_false_when_unconfigured():
    from market_chat.providers.base import ChatProvider, ProviderResponse

    class DummyProvider(ChatProvider):
        name = "dummy"
        default_model = "dummy-1"

        def is_configured(self) -> bool:
            return False

        def chat(self, messages, system=None, model=None, tools=None, tool_executor=None):  # pragma: no cover
            return ProviderResponse("", 0, 0, 0.0, 0, "dummy-1", "dummy")

    assert DummyProvider().is_configured() is False


# ---------------------------------------------------------------------------
# Router
# ---------------------------------------------------------------------------


class _FakeProvider:
    """Minimal fake conforming to the ChatProvider duck-type used by the router."""

    def __init__(self, name: str, *, configured: bool = True, model: str = "model-x") -> None:
        self.name = name
        self.default_model = model
        self._model = model
        self._configured = configured
        self.calls: list[dict] = []

    def is_configured(self) -> bool:
        return self._configured

    def chat(self, messages, system=None, model=None, tools=None, tool_executor=None):
        from market_chat.providers.base import ProviderResponse

        self.calls.append({"messages": list(messages), "system": system, "model": model})
        return ProviderResponse(
            text="hola",
            tokens_in=10,
            tokens_out=5,
            cost_usd=0.01,
            latency_ms=42,
            model=model or self.default_model,
            provider=self.name,
        )


def test_router_routes_to_correct_provider_and_falls_back(monkeypatch):
    from market_chat.router import ChatRouter, ChatRouterError

    a = _FakeProvider("anthropic", configured=False)
    b = _FakeProvider("openai", configured=True)
    c = _FakeProvider("gemini", configured=True)
    router = ChatRouter(providers=[a, b, c])

    listing = router.available_providers()
    assert {entry["id"]: entry["configured"] for entry in listing} == {
        "anthropic": False,
        "openai": True,
        "gemini": True,
    }

    monkeypatch.setenv("CHAT_PROVIDER_DEFAULT", "openai")
    assert router.default_provider() is b

    # Preferred default is unconfigured → falls back to first configured.
    monkeypatch.setenv("CHAT_PROVIDER_DEFAULT", "anthropic")
    assert router.default_provider() is b

    # Direct selection of a configured provider works.
    assert router.get_provider("gemini") is c

    # Direct selection of an unconfigured provider raises.
    with pytest.raises(ChatRouterError):
        router.get_provider("anthropic")

    # Unknown provider raises.
    with pytest.raises(ChatRouterError):
        router.get_provider("does-not-exist")


def test_router_raises_when_no_provider_configured(monkeypatch):
    from market_chat.router import ChatRouter, ChatRouterError

    router = ChatRouter(
        providers=[
            _FakeProvider("anthropic", configured=False),
            _FakeProvider("openai", configured=False),
        ]
    )
    monkeypatch.delenv("CHAT_PROVIDER_DEFAULT", raising=False)
    with pytest.raises(ChatRouterError):
        router.default_provider()


# ---------------------------------------------------------------------------
# Store
# ---------------------------------------------------------------------------


def test_store_create_thread_append_and_list_messages(_reset_db, monkeypatch):
    """Round-trip a thread + messages through the SQLite store."""

    from market_identity.service import IdentityService
    from market_chat import (
        append_message,
        create_thread,
        list_messages,
        list_threads,
        usage_for_user,
    )

    identity = IdentityService()
    session = identity.register_user(
        username="storeuser",
        password="secret123",
        display_name="Store",
    )
    user_id = session.profile.user_id

    thread = create_thread(user_id, "Mi conversación", provider="anthropic", model="claude-sonnet-4-5")
    assert thread.id > 0
    assert thread.title == "Mi conversación"

    append_message(thread.id, role="user", content="Hola")
    append_message(
        thread.id,
        role="assistant",
        content="Buenas",
        provider="anthropic",
        model="claude-sonnet-4-5",
        tokens_in=100,
        tokens_out=50,
        cost_usd=0.0015,
        latency_ms=120,
    )

    messages = list_messages(thread.id, user_id)
    assert [m.role for m in messages] == ["user", "assistant"]
    assert messages[1].cost_usd == pytest.approx(0.0015)

    threads = list_threads(user_id)
    assert len(threads) == 1 and threads[0].id == thread.id

    # Foreign user can't read the thread.
    other = identity.register_user(
        username="other",
        password="secret123",
        display_name="Other",
    )
    assert list_messages(thread.id, other.profile.user_id) == []

    usage = usage_for_user(user_id)
    assert usage["total_cost_usd"] == pytest.approx(0.0015)
    assert usage["by_provider"][0]["provider"] == "anthropic"
    assert usage["by_provider"][0]["message_count"] == 1


def test_store_update_and_delete_thread(_reset_db):
    from market_identity.service import IdentityService
    from market_chat import create_thread, delete_thread, get_thread, update_thread_title

    identity = IdentityService()
    session = identity.register_user(
        username="threadops",
        password="secret123",
        display_name="Thread Ops",
    )
    user_id = session.profile.user_id

    thread = create_thread(user_id, "Hilo original")
    updated = update_thread_title(thread.id, user_id, "Etiqueta nueva")
    assert updated is not None
    assert updated.title == "Etiqueta nueva"

    assert delete_thread(thread.id, user_id) is True
    assert get_thread(thread.id, user_id) is None
    assert delete_thread(thread.id, user_id) is False


# ---------------------------------------------------------------------------
# API integration
# ---------------------------------------------------------------------------


def _install_fake_router(monkeypatch, *, provider_name: str = "anthropic"):
    """Replace the FastAPI app's ``chat_router`` with one backed by ``_FakeProvider``.

    Returns the fake provider so the test can introspect its call log.
    """

    from services.api import app as app_module
    from market_chat.router import ChatRouter

    fake = _FakeProvider(provider_name, configured=True, model="fake-model")
    router = ChatRouter(providers=[fake])
    monkeypatch.setattr(app_module, "chat_router", router)
    return fake


def test_api_chat_providers_endpoint(api_client, auth_headers, monkeypatch):
    _install_fake_router(monkeypatch)
    response = api_client.get("/chat/providers")
    assert response.status_code == 200
    payload = response.json()
    assert payload == [{"id": "anthropic", "label": "Claude", "configured": True, "model": "fake-model"}]


def test_api_chat_thread_message_roundtrip(api_client, auth_headers, monkeypatch):
    """POST thread → POST message → GET messages."""

    fake = _install_fake_router(monkeypatch)

    # Create a thread.
    thread_response = api_client.post(
        "/chat/threads",
        json={"title": "Test thread", "provider": "anthropic"},
        headers=auth_headers,
    )
    assert thread_response.status_code == 201, thread_response.text
    thread_id = thread_response.json()["id"]

    # Send a message — fake provider returns a deterministic reply.
    send_response = api_client.post(
        f"/chat/threads/{thread_id}/messages",
        json={"role": "user", "content": "¿Qué hago con AAPL?"},
        headers=auth_headers,
    )
    assert send_response.status_code == 201, send_response.text
    body = send_response.json()
    assert body["assistant_message"]["content"] == "hola"
    assert body["assistant_message"]["provider"] == "anthropic"
    assert body["usage"]["cost_usd"] == pytest.approx(0.01)

    # Provider should have received our message and the baseline system prompt.
    assert fake.calls, "Provider was never called"
    last_call = fake.calls[-1]
    assert last_call["messages"][-1].content == "¿Qué hago con AAPL?"
    assert last_call["system"] and "Market Bot" in last_call["system"]

    # GET messages returns both turns.
    list_response = api_client.get(
        f"/chat/threads/{thread_id}/messages",
        headers=auth_headers,
    )
    assert list_response.status_code == 200
    roles = [row["role"] for row in list_response.json()]
    assert roles == ["user", "assistant"]


def test_api_chat_unknown_thread_returns_404(api_client, auth_headers, monkeypatch):
    _install_fake_router(monkeypatch)
    response = api_client.get("/chat/threads/9999/messages", headers=auth_headers)
    assert response.status_code == 404


def test_api_chat_thread_rename_and_delete(api_client, auth_headers, monkeypatch):
    _install_fake_router(monkeypatch)

    thread_id = api_client.post(
        "/chat/threads",
        json={"title": "Thread vieja"},
        headers=auth_headers,
    ).json()["id"]

    rename_response = api_client.patch(
        f"/chat/threads/{thread_id}",
        json={"title": "Tecnologia USA"},
        headers=auth_headers,
    )
    assert rename_response.status_code == 200, rename_response.text
    assert rename_response.json()["title"] == "Tecnologia USA"

    list_response = api_client.get("/chat/threads", headers=auth_headers)
    assert list_response.status_code == 200
    assert list_response.json()[0]["title"] == "Tecnologia USA"

    delete_response = api_client.delete(
        f"/chat/threads/{thread_id}",
        headers=auth_headers,
    )
    assert delete_response.status_code == 204, delete_response.text

    list_after_delete = api_client.get("/chat/threads", headers=auth_headers)
    assert list_after_delete.status_code == 200
    assert list_after_delete.json() == []


def test_api_chat_rate_limit_blocks_21st_message(api_client, auth_headers, monkeypatch):
    """The 21st message inside a 1h window should return 429."""

    _install_fake_router(monkeypatch)
    thread_response = api_client.post(
        "/chat/threads",
        json={"title": "Spam"},
        headers=auth_headers,
    )
    thread_id = thread_response.json()["id"]

    for i in range(20):
        ok = api_client.post(
            f"/chat/threads/{thread_id}/messages",
            json={"role": "user", "content": f"ping {i}"},
            headers=auth_headers,
        )
        assert ok.status_code == 201, f"message {i} unexpectedly failed: {ok.text}"

    blocked = api_client.post(
        f"/chat/threads/{thread_id}/messages",
        json={"role": "user", "content": "should fail"},
        headers=auth_headers,
    )
    assert blocked.status_code == 429


def test_api_chat_usage_aggregates_cost(api_client, auth_headers, monkeypatch):
    """``GET /chat/usage`` should sum tokens and cost across all assistant turns."""

    _install_fake_router(monkeypatch)
    thread_id = api_client.post(
        "/chat/threads",
        json={"title": "Usage test"},
        headers=auth_headers,
    ).json()["id"]

    for i in range(3):
        api_client.post(
            f"/chat/threads/{thread_id}/messages",
            json={"role": "user", "content": f"msg {i}"},
            headers=auth_headers,
        )

    usage = api_client.get("/chat/usage", headers=auth_headers).json()
    # Each fake reply: 10/5 tokens, $0.01 cost — three replies => 30/15 tokens, $0.03.
    assert usage["total_tokens_in"] == 30
    assert usage["total_tokens_out"] == 15
    assert usage["total_cost_usd"] == pytest.approx(0.03)
    assert usage["by_provider"][0]["provider"] == "anthropic"
    assert usage["by_provider"][0]["message_count"] == 3


def test_api_chat_portfolio_question_injects_portfolio_context(api_client, auth_headers, monkeypatch):
    from market_portfolio.models import ExposureBucket, PortfolioSummary
    from services.api import app as app_module

    fake = _install_fake_router(monkeypatch)
    monkeypatch.setattr(
        app_module.portfolio_service,
        "portfolio_summary",
        lambda user_id, benchmark_preference, risk_tolerance="medium": PortfolioSummary(
            positions_count=2,
            total_value_ars=18_501_660.0,
            total_value_usd=14_850.0,
            total_cost_ars=16_900_000.0,
            total_cost_usd=13_900.0,
            total_pnl_ars=1_601_660.0,
            total_pnl_usd=950.0,
            total_return_pct_ars=9.48,
            total_return_pct_usd=6.83,
            total_real_return_pct=1.36,
            total_preferred_benchmark_return_pct=13.77,
            preferred_benchmark_label="mep",
            positions=[],
            sector_exposure=[ExposureBucket(label="Tecnologia", total_value_ars=11_000_000.0, pct=0.594)],
            region_exposure=[ExposureBucket(label="USA", total_value_ars=14_000_000.0, pct=0.757)],
        ),
    )

    thread_id = api_client.post(
        "/chat/threads",
        json={"title": "Portfolio context"},
        headers=auth_headers,
    ).json()["id"]

    send_response = api_client.post(
        f"/chat/threads/{thread_id}/messages",
        json={"role": "user", "content": "Resumime mi portfolio en 5 puntos"},
        headers=auth_headers,
    )
    assert send_response.status_code == 201, send_response.text

    last_call = fake.calls[-1]
    assert "PORTFOLIO DEL USUARIO" in last_call["system"]
    assert "Valor total ARS" in last_call["system"]
    assert "Exposicion sectorial principal" in last_call["system"]


def test_api_chat_concept_question_skips_portfolio_summary(api_client, auth_headers, monkeypatch):
    from services.api import app as app_module

    fake = _install_fake_router(monkeypatch)

    def _boom(*_args, **_kwargs):
        raise AssertionError("portfolio_summary no deberia llamarse para una pregunta conceptual")

    monkeypatch.setattr(app_module.portfolio_service, "portfolio_summary", _boom)

    thread_id = api_client.post(
        "/chat/threads",
        json={"title": "Concept chat"},
        headers=auth_headers,
    ).json()["id"]

    send_response = api_client.post(
        f"/chat/threads/{thread_id}/messages",
        json={"role": "user", "content": "Explicame que es ROIC"},
        headers=auth_headers,
    )
    assert send_response.status_code == 201, send_response.text

    last_call = fake.calls[-1]
    assert "PORTFOLIO DEL USUARIO" not in last_call["system"]


def test_format_chat_pct_multiplies_ratio_by_100():
    """Regression: _format_chat_pct must turn a ratio into a percentage.
    A 100x bug made the chat say 'P&L 0.12%' for a real +12.34% portfolio."""
    from services.api.app import _format_chat_pct

    assert _format_chat_pct(0.1234) == "12.34%"
    assert _format_chat_pct(-0.5) == "-50.00%"
    assert _format_chat_pct(0.0) == "0.00%"

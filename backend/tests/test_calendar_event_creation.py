"""
Unit tests for calendar event creation truthfulness + idempotency.

Tests:
  1. success_when_event_id_exists        – 2xx + event_id → success
  2. failure_when_event_id_missing       – 2xx but no event_id → failure
  3. failure_on_http_error               – 4xx/5xx → failure, pending preserved
  4. idempotent_duplicate_returns_same   – second identical request → same event_id
  5. idempotent_no_extra_api_call        – cached result, HTTP not called again
  6. microsoft_calendar_create_endpoint_not_404 – route exists, returns non-404
  7. microsoft_calendar_list_endpoint_not_404   – route exists, returns non-404
  8. microsoft_mail_send_endpoint_not_404       – route exists, returns non-404

Run with:
  cd backend
  python -m pytest tests/test_calendar_event_creation.py -v
"""

import asyncio
import hashlib
import json
import sys
import os
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

# ── Allow importing backend modules without installing as a package ──────────
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# Stub heavy optional deps before import
sys.modules.setdefault("pytz", MagicMock())
sys.modules.setdefault("langdetect", MagicMock())
sys.modules.setdefault("gtts", MagicMock())
sys.modules.setdefault("httpx", MagicMock())

from services.executive_agent_service import (
    ExecutiveAgent,
    ConversationMemory,
    _CALENDAR_IDEMPOTENCY_STORE,
    _compute_calendar_request_id,
)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_action_data(
    title="Sprint Planning",
    date="2026-03-15",
    time="14:00",
    provider="google",
):
    return {
        "title": title,
        "date": date,
        "time": time,
        "provider": provider,
        "user_id": "test_user",
    }


def _mock_http_response(status_code: int, body: dict) -> MagicMock:
    resp = MagicMock()
    resp.status_code = status_code
    resp.is_success = 200 <= status_code < 300
    resp.text = json.dumps(body)
    resp.json = MagicMock(return_value=body)
    return resp


def _make_agent(session_id="test-session") -> ExecutiveAgent:
    """Create agent with mocked chat_service to avoid LLM calls."""
    # Reset or create session
    if session_id in ExecutiveAgent.sessions:
        del ExecutiveAgent.sessions[session_id]
    agent = ExecutiveAgent.__new__(ExecutiveAgent)
    agent.session_id = session_id
    ExecutiveAgent.sessions[session_id] = ConversationMemory(session_id=session_id)
    agent.memory = ExecutiveAgent.sessions[session_id]
    agent.chat_service = MagicMock()
    import datetime
    import pytz
    agent.current_datetime = datetime.datetime.now()
    agent.timezone = MagicMock()
    return agent


# ── Tests ─────────────────────────────────────────────────────────────────────

class TestCalendarEventCreation:
    """Tests for _execute_calendar_event_creation."""

    def setup_method(self):
        """Clear idempotency store before each test."""
        _CALENDAR_IDEMPOTENCY_STORE.clear()

    # ─────────────────────────────────────────────────────────────────────────
    # Test 1: Success when event_id exists
    # ─────────────────────────────────────────────────────────────────────────
    def test_success_when_event_id_exists(self):
        """2xx response WITH event_id → success + calendar_created type."""
        agent = _make_agent("session-success")
        action_data = _make_action_data()

        # Set a pending action so the guard passes
        agent.memory.set_pending_action("create_calendar_event", action_data)

        api_response = _mock_http_response(201, {
            "id": "google-event-abc123",
            "summary": "Sprint Planning",
            "start": "2026-03-15T14:00:00",
            "end": "2026-03-15T15:00:00",
            "htmlLink": "https://calendar.google.com/event/abc123",
        })

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.post = AsyncMock(return_value=api_response)

        with patch("httpx.AsyncClient", return_value=mock_client):
            result = asyncio.get_event_loop().run_until_complete(
                agent._execute_calendar_event_creation(action_data, "test_user")
            )

        assert result["success"] is True, f"Expected success=True, got: {result}"
        assert result["type"] == "calendar_created"
        assert result["data"]["event_id"] == "google-event-abc123"
        # Pending action must be cleared on success
        assert agent.memory.get_pending_action() is None
        # Idempotency store must have the event_id
        assert "google-event-abc123" in _CALENDAR_IDEMPOTENCY_STORE.values()

    # ─────────────────────────────────────────────────────────────────────────
    # Test 2: Failure when event_id missing (truthfulness check)
    # ─────────────────────────────────────────────────────────────────────────
    def test_failure_when_event_id_missing(self):
        """2xx response WITHOUT event_id → failure, pending preserved."""
        agent = _make_agent("session-no-id")
        action_data = _make_action_data()
        agent.memory.set_pending_action("create_calendar_event", action_data)

        # 201 but no 'id' field in body
        api_response = _mock_http_response(201, {
            "summary": "Sprint Planning",
            "start": "2026-03-15T14:00:00",
            "end": "2026-03-15T15:00:00",
            # 'id' intentionally absent
        })

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.post = AsyncMock(return_value=api_response)

        with patch("httpx.AsyncClient", return_value=mock_client):
            result = asyncio.get_event_loop().run_until_complete(
                agent._execute_calendar_event_creation(action_data, "test_user")
            )

        assert result["success"] is False, f"Expected success=False, got: {result}"
        assert result["type"] == "error"
        assert "event_id missing" in result.get("error", "").lower() or \
               "event_id" in result.get("error", "").lower()
        # pending_action_preserved flag must be set
        assert result["data"].get("pending_action_preserved") is True
        # Idempotency store must NOT have been written
        assert len(_CALENDAR_IDEMPOTENCY_STORE) == 0

    # ─────────────────────────────────────────────────────────────────────────
    # Test 3: Failure on HTTP error – pending action preserved
    # ─────────────────────────────────────────────────────────────────────────
    def test_failure_on_http_error_preserves_pending(self):
        """4xx/5xx response → failure, pending_action NOT cleared (user can retry)."""
        agent = _make_agent("session-http-err")
        action_data = _make_action_data()
        agent.memory.set_pending_action("create_calendar_event", action_data)

        api_response = _mock_http_response(403, {"detail": "OAuth token expired"})

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.post = AsyncMock(return_value=api_response)

        with patch("httpx.AsyncClient", return_value=mock_client):
            result = asyncio.get_event_loop().run_until_complete(
                agent._execute_calendar_event_creation(action_data, "test_user")
            )

        assert result["success"] is False
        assert result["type"] == "error"
        assert result["data"].get("pending_action_preserved") is True
        # pending_action must still be present so user can retry
        assert agent.memory.get_pending_action() is not None

    # ─────────────────────────────────────────────────────────────────────────
    # Test 4: Idempotent duplicate returns same event_id
    # ─────────────────────────────────────────────────────────────────────────
    def test_idempotent_duplicate_returns_same_event_id(self):
        """Second identical request returns cached event_id without calling API."""
        agent1 = _make_agent("session-idempotent-1")
        action_data = _make_action_data()
        agent1.memory.set_pending_action("create_calendar_event", action_data)

        api_response = _mock_http_response(201, {
            "id": "google-event-xyz789",
            "summary": "Sprint Planning",
            "start": "2026-03-15T14:00:00",
            "end": "2026-03-15T15:00:00",
        })

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.post = AsyncMock(return_value=api_response)

        # First request
        with patch("httpx.AsyncClient", return_value=mock_client):
            result1 = asyncio.get_event_loop().run_until_complete(
                agent1._execute_calendar_event_creation(action_data, "test_user")
            )

        assert result1["success"] is True
        assert result1["data"]["event_id"] == "google-event-xyz789"

        # Second request (duplicate) – new agent, same action_data, same user_id
        agent2 = _make_agent("session-idempotent-2")
        agent2.memory.set_pending_action("create_calendar_event", action_data)

        mock_client2 = AsyncMock()
        mock_client2.__aenter__ = AsyncMock(return_value=mock_client2)
        mock_client2.__aexit__ = AsyncMock(return_value=None)
        mock_client2.post = AsyncMock(return_value=api_response)

        with patch("httpx.AsyncClient", return_value=mock_client2):
            result2 = asyncio.get_event_loop().run_until_complete(
                agent2._execute_calendar_event_creation(action_data, "test_user")
            )

        assert result2["success"] is True
        assert result2["data"]["event_id"] == "google-event-xyz789"
        assert result2["data"].get("idempotent") is True
        # Crucially: the HTTP post must NOT have been called a second time
        mock_client2.post.assert_not_called()

    # ─────────────────────────────────────────────────────────────────────────
    # Test 5: No pending action guard
    # ─────────────────────────────────────────────────────────────────────────
    def test_no_pending_action_guard_prevents_phantom_success(self):
        """Without pending_action, execution refuses and returns error."""
        agent = _make_agent("session-no-pending")
        action_data = _make_action_data()
        # Do NOT set pending action

        result = asyncio.get_event_loop().run_until_complete(
            agent._execute_calendar_event_creation(action_data, "test_user")
        )

        assert result["success"] is False
        assert result["type"] == "error"
        assert "No pending action" in result["error"]


class TestComputeCalendarRequestId:
    """Tests for _compute_calendar_request_id determinism."""

    def test_same_inputs_produce_same_hash(self):
        id1 = _compute_calendar_request_id("u1", "Meeting", "2026-03-15T10:00:00", "2026-03-15T11:00:00", "UTC")
        id2 = _compute_calendar_request_id("u1", "Meeting", "2026-03-15T10:00:00", "2026-03-15T11:00:00", "UTC")
        assert id1 == id2

    def test_different_users_produce_different_hash(self):
        id1 = _compute_calendar_request_id("user_a", "Meeting", "2026-03-15T10:00:00", "2026-03-15T11:00:00", "UTC")
        id2 = _compute_calendar_request_id("user_b", "Meeting", "2026-03-15T10:00:00", "2026-03-15T11:00:00", "UTC")
        assert id1 != id2

    def test_different_titles_produce_different_hash(self):
        id1 = _compute_calendar_request_id("u1", "Sprint Planning", "2026-03-15T10:00:00", "2026-03-15T11:00:00", "UTC")
        id2 = _compute_calendar_request_id("u1", "Standup", "2026-03-15T10:00:00", "2026-03-15T11:00:00", "UTC")
        assert id1 != id2

    def test_hash_is_valid_sha256(self):
        h = _compute_calendar_request_id("u1", "M", "s", "e", "UTC")
        assert len(h) == 64
        assert all(c in "0123456789abcdef" for c in h)


class TestMicrosoftRouteExists:
    """
    Assert that the canonical Microsoft integration routes are registered
    on the integrations router.  Inspects router.routes directly so there
    is no dependency on TestClient or a running server.
    """

    @classmethod
    def _get_routes(cls):
        """Import the integrations router and return its (METHOD, path) pairs."""
        import importlib

        # Stub deps that api/integrations.py imports at module level
        for mod in (
            "google_auth_oauthlib", "google_auth_oauthlib.flow",
            "google.oauth2.credentials", "googleapiclient",
            "googleapiclient.discovery", "googleapiclient.errors",
            "msal",
        ):
            sys.modules.setdefault(mod, MagicMock())

        # Force reimport so stubs are active
        for key in list(sys.modules.keys()):
            if "api.integrations" in key or key == "api.integrations":
                del sys.modules[key]

        integrations_mod = importlib.import_module("api.integrations")
        router = integrations_mod.router

        routes = []
        for route in router.routes:
            methods = getattr(route, "methods", None) or set()
            path = getattr(route, "path", "")
            for method in methods:
                routes.append((method.upper(), path))
        return routes

    def test_microsoft_calendar_create_route_registered(self):
        """POST /integrations/microsoft/calendar/events must be registered."""
        routes = self._get_routes()
        assert ("POST", "/integrations/microsoft/calendar/events") in routes, (
            f"POST /integrations/microsoft/calendar/events not found in integrations router. "
            f"Registered routes: {routes}"
        )

    def test_microsoft_calendar_list_route_registered(self):
        """GET /integrations/microsoft/calendar/events must be registered."""
        routes = self._get_routes()
        assert ("GET", "/integrations/microsoft/calendar/events") in routes, (
            f"GET /integrations/microsoft/calendar/events not found in integrations router. "
            f"Registered routes: {routes}"
        )

    def test_microsoft_mail_send_route_registered(self):
        """POST /integrations/microsoft/mail/send must be registered."""
        routes = self._get_routes()
        assert ("POST", "/integrations/microsoft/mail/send") in routes, (
            f"POST /integrations/microsoft/mail/send not found in integrations router. "
            f"Registered routes: {routes}"
        )


class TestNormalizeProvider:
    """Unit tests for _normalize_provider ensuring 'microsoft' slug is returned."""

    def test_outlook_maps_to_microsoft(self):
        from services.executive_agent_service import _normalize_provider
        assert _normalize_provider("outlook") == "microsoft"

    def test_microsoft_maps_to_microsoft(self):
        from services.executive_agent_service import _normalize_provider
        assert _normalize_provider("microsoft") == "microsoft"

    def test_ms_maps_to_microsoft(self):
        from services.executive_agent_service import _normalize_provider
        assert _normalize_provider("ms") == "microsoft"

    def test_office365_maps_to_microsoft(self):
        from services.executive_agent_service import _normalize_provider
        assert _normalize_provider("office365") == "microsoft"

    def test_google_maps_to_google(self):
        from services.executive_agent_service import _normalize_provider
        assert _normalize_provider("google") == "google"

    def test_gmail_maps_to_google(self):
        from services.executive_agent_service import _normalize_provider
        assert _normalize_provider("gmail") == "google"


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import subprocess
    subprocess.run(["python", "-m", "pytest", __file__, "-v"], check=True)

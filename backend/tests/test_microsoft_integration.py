"""
Microsoft Integration Tests
============================
Verifies the critical paths for Microsoft OAuth token handling,
Graph API error mapping, and Executive AI intent routing.

Run from backend/ directory:
    pytest tests/test_microsoft_integration.py -v

These tests do NOT make real network calls — all HTTP is mocked.
"""

import json
import base64
from datetime import datetime, timedelta
from typing import Dict, Any
from unittest.mock import MagicMock, patch, PropertyMock

import pytest


# ============================================================================
# Helpers
# ============================================================================

def _make_jwt(payload: Dict[str, Any]) -> str:
    """Create a fake JWT with the given payload (no signature validation)."""
    header = base64.urlsafe_b64encode(b'{"alg":"HS256","typ":"JWT"}').rstrip(b"=").decode()
    body_bytes = json.dumps(payload).encode()
    body = base64.urlsafe_b64encode(body_bytes).rstrip(b"=").decode()
    return f"{header}.{body}.fakesig"


def _graph_token(
    aud: str = "https://graph.microsoft.com",
    scp: str = "Calendars.ReadWrite Mail.Read Mail.Send User.Read",
    exp_offset: int = 3600,
) -> str:
    """Return a fake Graph access token JWT."""
    exp = int((datetime.utcnow() + timedelta(seconds=exp_offset)).timestamp())
    return _make_jwt({"aud": aud, "scp": scp, "exp": exp})


def _stored_tokens(
    access_token: str = None,
    refresh_token: str = "refresh-tok-abc",
    expires_at_offset: int = 3600,
) -> Dict[str, Any]:
    """Return a dict that mimics valid stored token data."""
    if access_token is None:
        access_token = _graph_token()
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "Bearer",
        "expires_at": (datetime.utcnow() + timedelta(seconds=expires_at_offset)).isoformat(),
        "scopes": [
            "https://graph.microsoft.com/Mail.Send",
            "https://graph.microsoft.com/Mail.Read",
            "https://graph.microsoft.com/Calendars.ReadWrite",
            "https://graph.microsoft.com/User.Read",
        ],
    }


# ============================================================================
# A. Token storage — unit tests
# ============================================================================

class TestGetValidMsToken:
    """Tests for utils.ms_token.get_valid_ms_token"""

    def test_returns_token_when_valid(self):
        """Valid non-expired token → returns immediately without refresh."""
        tokens = _stored_tokens(expires_at_offset=600)  # 10 min from now

        with patch("utils.ms_token.get_token_storage") as mock_storage:
            mock_storage.return_value.load_tokens.return_value = tokens
            from utils.ms_token import get_valid_ms_token
            token = get_valid_ms_token("default_user")

        assert token == tokens["access_token"]

    def test_refreshes_when_expired(self):
        """Expired token → calls refresh and returns new token."""
        expired_tokens = _stored_tokens(expires_at_offset=-60)  # expired 1 min ago
        new_access_token = _graph_token()

        msal_result = {
            "access_token": new_access_token,
            "refresh_token": "new-refresh-tok",
            "expires_in": 3600,
        }

        with patch("utils.ms_token.get_token_storage") as mock_storage, \
             patch("utils.ms_token.ConfidentialClientApplication") as mock_msal, \
             patch.dict("os.environ", {
                 "MICROSOFT_CLIENT_ID": "client-id",
                 "MICROSOFT_CLIENT_SECRET": "client-secret",
                 "MICROSOFT_TENANT_ID": "consumers",
             }):
            mock_storage.return_value.load_tokens.return_value = expired_tokens
            mock_storage.return_value.save_tokens.return_value = None
            mock_msal.return_value.acquire_token_by_refresh_token.return_value = msal_result

            from utils.ms_token import get_valid_ms_token
            token = get_valid_ms_token("default_user")

        assert token == new_access_token
        # Verify MSAL was called with refresh token
        mock_msal.return_value.acquire_token_by_refresh_token.assert_called_once()

    def test_raises_401_when_no_tokens(self):
        """No stored tokens → HTTPException(401, MICROSOFT_UNAUTHORIZED)."""
        from fastapi import HTTPException

        with patch("utils.ms_token.get_token_storage") as mock_storage:
            mock_storage.return_value.load_tokens.return_value = None
            from utils.ms_token import get_valid_ms_token

            with pytest.raises(HTTPException) as exc_info:
                get_valid_ms_token("default_user")

        assert exc_info.value.status_code == 401
        assert exc_info.value.detail["code"] == "MICROSOFT_UNAUTHORIZED"

    def test_raises_401_when_refresh_fails(self):
        """Expired token + failed refresh → HTTPException(401)."""
        from fastapi import HTTPException

        expired_tokens = _stored_tokens(expires_at_offset=-3600)
        msal_error_result = {
            "error": "invalid_grant",
            "error_description": "Refresh token expired",
        }

        with patch("utils.ms_token.get_token_storage") as mock_storage, \
             patch("utils.ms_token.ConfidentialClientApplication") as mock_msal, \
             patch.dict("os.environ", {
                 "MICROSOFT_CLIENT_ID": "client-id",
                 "MICROSOFT_CLIENT_SECRET": "client-secret",
             }):
            mock_storage.return_value.load_tokens.return_value = expired_tokens
            mock_msal.return_value.acquire_token_by_refresh_token.return_value = msal_error_result

            from utils.ms_token import get_valid_ms_token

            with pytest.raises(HTTPException) as exc_info:
                get_valid_ms_token("default_user")

        assert exc_info.value.status_code == 401
        assert "MICROSOFT_UNAUTHORIZED" in exc_info.value.detail["code"]

    def test_access_token_stored_not_id_token(self):
        """
        Verifies that the stored access_token has Graph aud, not account aud.
        The JWT payload aud should contain 'graph.microsoft.com' (or its GUID).
        """
        # Simulate wrong token (id_token has aud = client_id)
        id_like_token = _graph_token(aud="00000000-0000-0000-0000-000000000001")  # fake client_id as aud
        tokens = _stored_tokens(access_token=id_like_token, expires_at_offset=600)

        import logging
        with patch("utils.ms_token.get_token_storage") as mock_storage:
            mock_storage.return_value.load_tokens.return_value = tokens
            from utils.ms_token import _log_token_diagnostics
            with patch.object(logging.getLogger("utils.ms_token"), "warning") as mock_warn:
                _log_token_diagnostics("default_user", tokens)
                # Should have warned about wrong audience
                warn_calls = [str(c) for c in mock_warn.call_args_list]
                assert any("WRONG TOKEN AUDIENCE" in c for c in warn_calls), \
                    f"Expected WRONG TOKEN AUDIENCE warning, got: {warn_calls}"

    def test_correct_graph_token_no_audience_warning(self):
        """Correct Graph token → no WRONG TOKEN AUDIENCE warning."""
        good_token = _graph_token(aud="https://graph.microsoft.com")
        tokens = _stored_tokens(access_token=good_token, expires_at_offset=600)

        import logging
        with patch("utils.ms_token.get_token_storage") as mock_storage:
            mock_storage.return_value.load_tokens.return_value = tokens
            from utils.ms_token import _log_token_diagnostics
            with patch.object(logging.getLogger("utils.ms_token"), "warning") as mock_warn:
                _log_token_diagnostics("default_user", tokens)
                warn_calls = [str(c) for c in mock_warn.call_args_list]
                assert not any("WRONG TOKEN AUDIENCE" in c for c in warn_calls), \
                    f"Unexpected WRONG TOKEN AUDIENCE warning for valid Graph token"


# ============================================================================
# B. HTTP error mapping — _ms_request
# ============================================================================

class TestMsRequest:
    """Tests for api.integrations._ms_request error handling."""

    def _get_ms_request(self):
        # Import fresh to get the patched version
        import importlib
        import backend.api.integrations as mod
        importlib.reload(mod)
        return mod._ms_request

    def _make_mock_response(self, status_code: int, json_body: dict = None, text: str = ""):
        mock_resp = MagicMock()
        mock_resp.status_code = status_code
        mock_resp.ok = status_code < 400
        mock_resp.text = text or json.dumps(json_body or {})
        mock_resp.content = b"some content" if status_code not in (204,) else b""
        if json_body is not None:
            mock_resp.json.return_value = json_body
        return mock_resp

    def test_401_raises_microsoft_unauthorized(self):
        """Graph 401 → HTTPException(401, MICROSOFT_UNAUTHORIZED) not 500."""
        from fastapi import HTTPException
        from api.integrations import _ms_request

        mock_resp = self._make_mock_response(401, text='{"error":{"code":"InvalidAuthenticationToken"}}')

        with patch("api.integrations.http_requests.request", return_value=mock_resp), \
             patch("api.integrations.get_token_storage") as mock_storage:
            mock_storage.return_value.load_tokens.return_value = None  # no retry

            with pytest.raises(HTTPException) as exc_info:
                _ms_request("GET", "/me/calendar/events", "some-token")

        assert exc_info.value.status_code == 401
        assert exc_info.value.detail["code"] == "MICROSOFT_UNAUTHORIZED"
        # Critically: NOT wrapped as 500
        assert exc_info.value.status_code != 500

    def test_403_raises_microsoft_forbidden(self):
        """Graph 403 → HTTPException(403, MICROSOFT_FORBIDDEN) not 500."""
        from fastapi import HTTPException
        from api.integrations import _ms_request

        mock_resp = self._make_mock_response(403, text='{"error":{"code":"Forbidden","message":"Insufficient scope"}}')

        with patch("api.integrations.http_requests.request", return_value=mock_resp):
            with pytest.raises(HTTPException) as exc_info:
                _ms_request("GET", "/me/calendar/events", "some-token")

        assert exc_info.value.status_code == 403
        assert exc_info.value.detail["code"] == "MICROSOFT_FORBIDDEN"
        assert exc_info.value.status_code != 500

    def test_200_returns_json(self):
        """Successful Graph response → returns parsed JSON dict."""
        from api.integrations import _ms_request

        event_data = {"id": "abc123", "subject": "Test Event"}
        mock_resp = self._make_mock_response(200, json_body=event_data)
        mock_resp.ok = True

        with patch("api.integrations.http_requests.request", return_value=mock_resp):
            result = _ms_request("GET", "/me/calendar/events/abc123", "some-token")

        assert result == event_data

    def test_204_returns_empty_dict(self):
        """204 No Content → returns empty dict (e.g., DELETE)."""
        from api.integrations import _ms_request

        mock_resp = self._make_mock_response(204)
        mock_resp.ok = True
        mock_resp.content = b""

        with patch("api.integrations.http_requests.request", return_value=mock_resp):
            result = _ms_request("DELETE", "/me/calendar/events/abc123", "some-token")

        assert result == {}

    def test_401_with_user_id_attempts_refresh_and_retry(self):
        """
        Graph 401 with user_id → should attempt exactly one refresh + retry.
        If retry succeeds (200), returns data.
        """
        from api.integrations import _ms_request

        event_data = {"id": "evt-after-refresh", "subject": "Refreshed Event"}
        resp_401 = self._make_mock_response(401, text="Unauthorized")
        resp_200 = self._make_mock_response(200, json_body=event_data)
        resp_200.ok = True

        tokens = _stored_tokens(_graph_token())
        new_access_token = _graph_token()
        msal_result = {
            "access_token": new_access_token,
            "refresh_token": "new-refresh",
            "expires_in": 3600,
        }

        with patch("api.integrations.http_requests.request", side_effect=[resp_401, resp_200]), \
             patch("api.integrations.get_token_storage") as mock_storage, \
             patch("api.integrations._refresh_ms_token", return_value=new_access_token):
            mock_storage.return_value.load_tokens.return_value = tokens

            result = _ms_request("GET", "/me/calendar/events", "old-token", user_id="default_user")

        assert result == event_data


# ============================================================================
# C. Intent routing — Executive AI
# ============================================================================

class TestIntentRouting:
    """Tests for utils.intent_router.IntentRouter — Microsoft-relevant routing."""

    def _route(self, message: str, active_task=None, pending_action=None):
        from utils.intent_router import IntentRouter
        return IntentRouter.route_message(
            message=message,
            active_task=active_task,
            pending_action=pending_action,
            last_question_type=None,
        )

    def test_last_3_emails_routes_email_read(self):
        """'What are my last 3 emails?' → EMAIL_READ"""
        from utils.intent_router import IntentType
        result = self._route("what are my last 3 emails?")
        assert result["intent_type"] == IntentType.EMAIL_READ, \
            f"Expected EMAIL_READ, got {result['intent_type']}"

    def test_show_calendar_today_routes_calendar_list(self):
        """'Show me my calendar today' → CALENDAR_LIST"""
        from utils.intent_router import IntentType
        result = self._route("show me my calendar today")
        assert result["intent_type"] in (IntentType.CALENDAR_LIST, IntentType.CALENDAR_READ), \
            f"Expected CALENDAR_LIST or CALENDAR_READ, got {result['intent_type']}"

    def test_create_meeting_routes_calendar_create(self):
        """'Create meeting tomorrow 9-10 in Fulda' → CALENDAR_CREATE"""
        from utils.intent_router import IntentType
        result = self._route("create meeting tomorrow 9-10 in Fulda")
        assert result["intent_type"] == IntentType.CALENDAR_CREATE, \
            f"Expected CALENDAR_CREATE, got {result['intent_type']}"

    def test_send_email_routes_general_with_email_intent(self):
        """'Send an email to john@example.com about the project' → not EMAIL_READ"""
        from utils.intent_router import IntentType
        result = self._route("send an email to john@example.com about the project update")
        # Must NOT be EMAIL_READ (send ≠ read)
        assert result["intent_type"] != IntentType.EMAIL_READ, \
            "Sending email should NOT route to EMAIL_READ"

    def test_last_n_emails_pattern(self):
        """'Show me my last 5 emails' → EMAIL_READ via regex pattern."""
        from utils.intent_router import IntentType
        result = self._route("show me my last 5 emails")
        assert result["intent_type"] == IntentType.EMAIL_READ, \
            f"Expected EMAIL_READ, got {result['intent_type']}"

    def test_check_inbox_routes_email_read(self):
        """'Check my inbox' → EMAIL_READ"""
        from utils.intent_router import IntentType
        result = self._route("check my inbox")
        assert result["intent_type"] == IntentType.EMAIL_READ

    def test_my_schedule_routes_calendar_read(self):
        """'What's my schedule for tomorrow?' → CALENDAR_READ or CALENDAR_LIST"""
        from utils.intent_router import IntentType
        result = self._route("what's my schedule for tomorrow?")
        assert result["intent_type"] in (IntentType.CALENDAR_READ, IntentType.CALENDAR_LIST), \
            f"Expected CALENDAR_READ/LIST, got {result['intent_type']}"

    def test_draft_routes_not_email_read(self):
        """'Draft an email to boss' → NOT EMAIL_READ (write intent)."""
        from utils.intent_router import IntentType
        result = self._route("draft an email to my boss about the project delay")
        assert result["intent_type"] != IntentType.EMAIL_READ, \
            "Draft email should NOT route to EMAIL_READ"

    def test_edit_event_routes_slot_fill_with_active_task(self):
        """'Move it to 11' while active calendar task → PROVIDE_SLOT_VALUE."""
        from utils.intent_router import IntentType
        active_task = {
            "type": "calendar_event",
            "data": {"title": "Meeting", "date": "2026-03-03", "time": "09:00"},
            "status": "awaiting_confirmation",
        }
        result = self._route("move it to 11", active_task=active_task)
        # Should fill slot or modify draft, NOT start new flow
        assert result["intent_type"] in (
            IntentType.PROVIDE_SLOT_VALUE, IntentType.MODIFY_DRAFT
        ), f"Expected slot fill or modify draft, got {result['intent_type']}"


# ============================================================================
# D. OAuth callback — stores access_token (not id_token)
# ============================================================================

class TestOAuthCallback:
    """Verifies that the OAuth callback stores access_token, not id_token."""

    def test_callback_stores_access_token(self):
        """_ms_handle_callback must store result['access_token'], not id_token."""
        graph_access_token = _graph_token()
        id_token = _make_jwt({"aud": "client-id-xyz", "sub": "user123"})  # client-targeted, NOT for Graph

        msal_result = {
            "access_token": graph_access_token,   # ← correct Graph token
            "id_token": id_token,                  # ← should NOT be stored as access_token
            "refresh_token": "refresh-xyz",
            "token_type": "Bearer",
            "scope": "Calendars.ReadWrite Mail.Read Mail.Send User.Read",
            "expires_in": 3600,
        }

        saved_data = {}

        with patch("api.integrations.ConfidentialClientApplication") as mock_msal, \
             patch("api.integrations.get_token_storage") as mock_storage, \
             patch.dict("os.environ", {
                 "MICROSOFT_CLIENT_ID": "client-id",
                 "MICROSOFT_CLIENT_SECRET": "client-secret",
                 "MICROSOFT_REDIRECT_URI": "http://localhost:8000/api/integrations/microsoft/auth/callback",
                 "MICROSOFT_TENANT_ID": "consumers",
             }):
            mock_msal.return_value.acquire_token_by_authorization_code.return_value = msal_result

            def capture_save(user_id, provider, data):
                saved_data.update(data)

            mock_storage.return_value.save_tokens.side_effect = capture_save

            import asyncio
            from api.integrations import _ms_handle_callback
            asyncio.get_event_loop().run_until_complete(
                _ms_handle_callback(code="auth-code-xyz", state="default_user")
            )

        # Verify access_token is the Graph token, not the id_token
        stored_access = saved_data.get("access_token")
        assert stored_access == graph_access_token, (
            f"access_token stored is NOT the Graph token!\n"
            f"stored: {stored_access[:30] if stored_access else None}\n"
            f"expected: {graph_access_token[:30]}"
        )
        assert stored_access != id_token, \
            "CRITICAL: id_token was stored as access_token — this causes 401 from Graph!"

        # Verify refresh_token is stored
        assert saved_data.get("refresh_token") == "refresh-xyz"

        # Verify expires_at is stored
        assert "expires_at" in saved_data
        expires_at = saved_data["expires_at"]
        assert expires_at, "expires_at must be stored for auto-refresh to work"


# ============================================================================
# E. Calendar endpoint — proper HTTP status codes
# ============================================================================

class TestCalendarEndpointHttpCodes:
    """Tests verify Microsoft calendar API routes return correct HTTP codes."""

    @pytest.mark.anyio
    async def test_calendar_list_401_graph_returns_401_not_500(self):
        """
        When Graph returns 401, GET /microsoft/calendar/events must return 401, not 500.
        This was the core reported bug.
        """
        from fastapi import HTTPException
        from api.integrations import microsoft_calendar_list_events

        with patch("api.integrations._ms_get_token", return_value="some-token"), \
             patch("api.integrations._ms_request", side_effect=HTTPException(
                 status_code=401,
                 detail={"code": "MICROSOFT_UNAUTHORIZED", "message": "Not authorized"},
             )):
            with pytest.raises(HTTPException) as exc_info:
                await microsoft_calendar_list_events(user_id="default_user", max_results=10)

        # Must be 401, not 500
        assert exc_info.value.status_code == 401
        assert exc_info.value.detail["code"] == "MICROSOFT_UNAUTHORIZED"

    @pytest.mark.anyio
    async def test_calendar_create_401_graph_returns_401(self):
        """
        POST /microsoft/calendar/events with 401 from Graph → 401 response.
        """
        from fastapi import HTTPException
        from api.integrations import microsoft_calendar_create_event
        from models.integrations import CalendarEventCreateRequest

        request = CalendarEventCreateRequest(
            summary="Test Meeting",
            start="2026-03-03T09:00:00",
            end="2026-03-03T10:00:00",
        )

        with patch("api.integrations._ms_get_token", return_value="some-token"), \
             patch("api.integrations._ms_request", side_effect=HTTPException(
                 status_code=401,
                 detail={"code": "MICROSOFT_UNAUTHORIZED", "message": "Not authorized"},
             )):
            with pytest.raises(HTTPException) as exc_info:
                await microsoft_calendar_create_event(request=request, user_id="default_user")

        assert exc_info.value.status_code == 401
        assert exc_info.value.detail["code"] == "MICROSOFT_UNAUTHORIZED"

    @pytest.mark.anyio
    async def test_calendar_create_403_graph_returns_403(self):
        """
        POST /microsoft/calendar/events with 403 from Graph → 403 response.
        """
        from fastapi import HTTPException
        from api.integrations import microsoft_calendar_create_event
        from models.integrations import CalendarEventCreateRequest

        request = CalendarEventCreateRequest(
            summary="Test Meeting",
            start="2026-03-03T09:00:00",
            end="2026-03-03T10:00:00",
        )

        with patch("api.integrations._ms_get_token", return_value="some-token"), \
             patch("api.integrations._ms_request", side_effect=HTTPException(
                 status_code=403,
                 detail={"code": "MICROSOFT_FORBIDDEN", "message": "Missing scope"},
             )):
            with pytest.raises(HTTPException) as exc_info:
                await microsoft_calendar_create_event(request=request, user_id="default_user")

        assert exc_info.value.status_code == 403
        assert exc_info.value.detail["code"] == "MICROSOFT_FORBIDDEN"

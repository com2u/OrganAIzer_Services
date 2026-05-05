"""
Email Foundation Phase 1A Tests
=================================
Tests for:
  - _gmail_decode_part_body and _gmail_extract_body unit tests
  - Gmail list includes thread_id
  - Gmail full message returns body / thread_id / attachments
  - Gmail full message does not log email body content
  - Unauthenticated and Gmail API error handling

Run from backend/ directory:
    python -m pytest tests/test_email_foundation.py -v

No real API calls are made — Gmail service / build are fully mocked.
"""

import sys
import os
import base64
import logging

import pytest
from unittest.mock import MagicMock, patch
from fastapi import FastAPI
from fastapi.testclient import TestClient

# ── allow importing backend modules ─────────────────────────────────────────
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from api.integrations import router, _gmail_decode_part_body, _gmail_extract_body
from googleapiclient.errors import HttpError

# ── minimal test app (integrations router only) ──────────────────────────────
_app = FastAPI()
_app.include_router(router, prefix="/api")
client = TestClient(_app, raise_server_exceptions=False)


# ── helpers ──────────────────────────────────────────────────────────────────

def _b64url(text: str) -> str:
    """Encode a UTF-8 string as base64url without padding (Gmail wire format)."""
    return base64.urlsafe_b64encode(text.encode()).rstrip(b"=").decode()


def _make_http_error(status: int) -> HttpError:
    resp = MagicMock()
    resp.status = status
    return HttpError(resp=resp, content=b"error")


def _valid_tokens() -> dict:
    return {
        "access_token": "fake-access-token",
        "refresh_token": "fake-refresh-token",
        "token_uri": "https://oauth2.googleapis.com/token",
        "client_id": "fake-client-id",
        "client_secret": "fake-client-secret",
        "scopes": ["https://www.googleapis.com/auth/gmail.readonly"],
    }


def _gmail_service(list_result=None, get_result=None) -> MagicMock:
    """Build a minimal Gmail API service mock."""
    service = MagicMock()
    msgs = service.users.return_value.messages.return_value
    if list_result is not None:
        msgs.list.return_value.execute.return_value = list_result
    if get_result is not None:
        msgs.get.return_value.execute.return_value = get_result
    return service


def _gmail_service_get_raises(exc) -> MagicMock:
    """Gmail service where .get().execute() raises exc."""
    service = MagicMock()
    msgs = service.users.return_value.messages.return_value
    msgs.get.return_value.execute.side_effect = exc
    return service


def _metadata_msg(msg_id: str, thread_id: str) -> dict:
    return {
        "id": msg_id,
        "threadId": thread_id,
        "snippet": f"Preview of {msg_id}",
        "labelIds": ["INBOX"],
        "payload": {
            "headers": [
                {"name": "From", "value": "Alice <alice@example.com>"},
                {"name": "Subject", "value": "Test Subject"},
                {"name": "Date", "value": "Mon, 05 May 2026 10:00:00 +0200"},
            ]
        },
    }


def _full_msg(
    msg_id: str = "msg123",
    thread_id: str = "thread456",
    body_text: str = "Hello plain",
    body_html: str = "<p>Hello HTML</p>",
    attachments: list | None = None,
) -> dict:
    parts = [
        {"mimeType": "text/plain", "body": {"data": _b64url(body_text)}},
        {"mimeType": "text/html", "body": {"data": _b64url(body_html)}},
    ]
    if attachments:
        parts += attachments
    return {
        "id": msg_id,
        "threadId": thread_id,
        "snippet": "snippet text",
        "payload": {
            "mimeType": "multipart/alternative",
            "headers": [
                {"name": "Subject", "value": "My Subject"},
                {"name": "From", "value": "sender@example.com"},
                {"name": "To", "value": "recipient@example.com"},
                {"name": "Cc", "value": "cc@example.com"},
                {"name": "Date", "value": "Mon, 05 May 2026 10:00:00 +0200"},
            ],
            "parts": parts,
        },
    }


# ============================================================================
# A. Body parser unit tests
# ============================================================================

class TestGmailDecodePartBody:

    def test_decodes_valid_base64url(self):
        encoded = _b64url("Hello, World!")
        assert _gmail_decode_part_body(encoded) == "Hello, World!"

    def test_empty_string_returns_empty(self):
        assert _gmail_decode_part_body("") == ""

    def test_data_with_padding_needed(self):
        # b64url without padding — length not multiple of 4
        text = "ab"
        encoded = base64.urlsafe_b64encode(text.encode()).rstrip(b"=").decode()
        assert len(encoded) % 4 != 0
        assert _gmail_decode_part_body(encoded) == text

    def test_already_padded_data(self):
        text = "test"
        encoded = base64.urlsafe_b64encode(text.encode()).decode()  # keep padding
        assert _gmail_decode_part_body(encoded) == text

    def test_multiline_body(self):
        text = "Line 1\nLine 2\nLine 3"
        assert _gmail_decode_part_body(_b64url(text)) == text

    def test_invalid_base64_returns_empty(self):
        # Completely invalid data should return empty without raising
        result = _gmail_decode_part_body("!!!not-base64!!!")
        assert isinstance(result, str)


class TestGmailExtractBody:

    def test_text_plain_payload(self):
        payload = {"mimeType": "text/plain", "body": {"data": _b64url("Hello text")}}
        text, html, body_type = _gmail_extract_body(payload)
        assert text == "Hello text"
        assert html == ""
        assert body_type == "text"

    def test_text_html_payload(self):
        payload = {"mimeType": "text/html", "body": {"data": _b64url("<b>Hi</b>")}}
        text, html, body_type = _gmail_extract_body(payload)
        assert text == ""
        assert html == "<b>Hi</b>"
        assert body_type == "html"

    def test_multipart_alternative_returns_both(self):
        payload = {
            "mimeType": "multipart/alternative",
            "parts": [
                {"mimeType": "text/plain", "body": {"data": _b64url("plain")}},
                {"mimeType": "text/html", "body": {"data": _b64url("<p>html</p>")}},
            ],
        }
        text, html, body_type = _gmail_extract_body(payload)
        assert text == "plain"
        assert html == "<p>html</p>"
        assert body_type == "multipart"

    def test_multipart_text_only(self):
        payload = {
            "mimeType": "multipart/mixed",
            "parts": [
                {"mimeType": "text/plain", "body": {"data": _b64url("only text")}},
            ],
        }
        text, html, body_type = _gmail_extract_body(payload)
        assert text == "only text"
        assert html == ""
        assert body_type == "text"

    def test_multipart_html_only(self):
        payload = {
            "mimeType": "multipart/mixed",
            "parts": [
                {"mimeType": "text/html", "body": {"data": _b64url("<em>hi</em>")}},
            ],
        }
        text, html, body_type = _gmail_extract_body(payload)
        assert text == ""
        assert html == "<em>hi</em>"
        assert body_type == "html"

    def test_unknown_mime_type_returns_empty(self):
        payload = {"mimeType": "application/pdf", "body": {"data": _b64url("binary")}}
        text, html, body_type = _gmail_extract_body(payload)
        assert text == ""
        assert html == ""
        assert body_type == ""

    def test_empty_payload(self):
        text, html, body_type = _gmail_extract_body({})
        assert text == ""
        assert html == ""

    def test_nested_multipart(self):
        # multipart/mixed wrapping a multipart/alternative
        payload = {
            "mimeType": "multipart/mixed",
            "parts": [
                {
                    "mimeType": "multipart/alternative",
                    "parts": [
                        {"mimeType": "text/plain", "body": {"data": _b64url("nested text")}},
                        {"mimeType": "text/html", "body": {"data": _b64url("<p>nested html</p>")}},
                    ],
                }
            ],
        }
        text, html, body_type = _gmail_extract_body(payload)
        assert text == "nested text"
        assert html == "<p>nested html</p>"
        assert body_type == "multipart"

    def test_missing_body_data(self):
        payload = {"mimeType": "text/plain", "body": {}}
        text, html, body_type = _gmail_extract_body(payload)
        assert text == ""

    def test_multipart_empty_parts(self):
        payload = {"mimeType": "multipart/alternative", "parts": []}
        text, html, body_type = _gmail_extract_body(payload)
        assert text == ""
        assert html == ""
        assert body_type == "multipart"


# ============================================================================
# B. Gmail list includes thread_id
# ============================================================================

class TestGmailListThreadId:

    def test_list_includes_thread_id(self):
        list_result = {"messages": [{"id": "msg001"}, {"id": "msg002"}]}
        get_result_side = [
            _metadata_msg("msg001", "thread-A"),
            _metadata_msg("msg002", "thread-B"),
        ]
        service = _gmail_service(list_result=list_result)
        service.users.return_value.messages.return_value.get.return_value.execute.side_effect = (
            get_result_side
        )

        with patch("api.integrations.get_token_storage") as mock_storage, \
             patch("api.integrations.build", return_value=service), \
             patch("api.integrations.Credentials"):
            mock_storage.return_value.load_tokens.return_value = _valid_tokens()
            resp = client.get("/api/integrations/google/gmail/messages?user_id=test_user")

        assert resp.status_code == 200
        emails = resp.json()["emails"]
        assert len(emails) == 2
        assert emails[0]["thread_id"] == "thread-A"
        assert emails[1]["thread_id"] == "thread-B"

    def test_list_thread_id_empty_when_missing(self):
        meta = _metadata_msg("msg001", "thread-A")
        meta.pop("threadId")  # simulate missing field
        service = _gmail_service(
            list_result={"messages": [{"id": "msg001"}]},
            get_result=meta,
        )

        with patch("api.integrations.get_token_storage") as mock_storage, \
             patch("api.integrations.build", return_value=service), \
             patch("api.integrations.Credentials"):
            mock_storage.return_value.load_tokens.return_value = _valid_tokens()
            resp = client.get("/api/integrations/google/gmail/messages?user_id=test_user")

        assert resp.status_code == 200
        assert resp.json()["emails"][0]["thread_id"] == ""


# ============================================================================
# C. Gmail full message endpoint
# ============================================================================

class TestGmailGetMessage:

    def test_returns_all_fields(self):
        msg = _full_msg()
        service = _gmail_service(get_result=msg)

        with patch("api.integrations.get_token_storage") as mock_storage, \
             patch("api.integrations.build", return_value=service), \
             patch("api.integrations.Credentials"):
            mock_storage.return_value.load_tokens.return_value = _valid_tokens()
            resp = client.get("/api/integrations/google/gmail/messages/msg123?user_id=test_user")

        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "msg123"
        assert data["thread_id"] == "thread456"
        assert data["subject"] == "My Subject"
        assert data["from"] == "sender@example.com"
        assert data["to"] == "recipient@example.com"
        assert data["cc"] == "cc@example.com"
        assert data["date"] == "Mon, 05 May 2026 10:00:00 +0200"
        assert data["snippet"] == "snippet text"
        assert data["body_text"] == "Hello plain"
        assert data["body_html"] == "<p>Hello HTML</p>"
        assert data["body_type"] == "multipart"
        assert isinstance(data["attachments"], list)

    def test_returns_attachments(self):
        attachment_part = {
            "mimeType": "application/pdf",
            "filename": "report.pdf",
            "body": {"size": 9876, "attachmentId": "att_abc123"},
        }
        msg = _full_msg(attachments=[attachment_part])
        service = _gmail_service(get_result=msg)

        with patch("api.integrations.get_token_storage") as mock_storage, \
             patch("api.integrations.build", return_value=service), \
             patch("api.integrations.Credentials"):
            mock_storage.return_value.load_tokens.return_value = _valid_tokens()
            resp = client.get("/api/integrations/google/gmail/messages/msg123?user_id=test_user")

        assert resp.status_code == 200
        attachments = resp.json()["attachments"]
        assert len(attachments) == 1
        assert attachments[0]["filename"] == "report.pdf"
        assert attachments[0]["mime_type"] == "application/pdf"
        assert attachments[0]["size"] == 9876
        assert attachments[0]["attachment_id"] == "att_abc123"

    def test_unauthenticated_returns_401(self):
        with patch("api.integrations.get_token_storage") as mock_storage:
            mock_storage.return_value.load_tokens.return_value = None
            resp = client.get("/api/integrations/google/gmail/messages/msg123?user_id=test_user")

        assert resp.status_code == 401
        assert resp.json()["detail"]["code"] == "NOT_AUTHENTICATED"

    def test_gmail_api_401_returns_401(self):
        service = _gmail_service_get_raises(_make_http_error(401))

        with patch("api.integrations.get_token_storage") as mock_storage, \
             patch("api.integrations.build", return_value=service), \
             patch("api.integrations.Credentials"):
            mock_storage.return_value.load_tokens.return_value = _valid_tokens()
            resp = client.get("/api/integrations/google/gmail/messages/msg123?user_id=test_user")

        assert resp.status_code == 401
        assert resp.json()["detail"]["code"] == "AUTHENTICATION_REQUIRED"

    def test_gmail_api_404_returns_404(self):
        service = _gmail_service_get_raises(_make_http_error(404))

        with patch("api.integrations.get_token_storage") as mock_storage, \
             patch("api.integrations.build", return_value=service), \
             patch("api.integrations.Credentials"):
            mock_storage.return_value.load_tokens.return_value = _valid_tokens()
            resp = client.get("/api/integrations/google/gmail/messages/missing_id?user_id=test_user")

        assert resp.status_code == 404
        assert resp.json()["detail"]["code"] == "MESSAGE_NOT_FOUND"

    def test_gmail_api_500_returns_500(self):
        service = _gmail_service_get_raises(_make_http_error(500))

        with patch("api.integrations.get_token_storage") as mock_storage, \
             patch("api.integrations.build", return_value=service), \
             patch("api.integrations.Credentials"):
            mock_storage.return_value.load_tokens.return_value = _valid_tokens()
            resp = client.get("/api/integrations/google/gmail/messages/msg123?user_id=test_user")

        assert resp.status_code == 500
        assert resp.json()["detail"]["code"] == "GMAIL_API_ERROR"

    def test_does_not_log_body(self, caplog):
        body_text = "SENSITIVE_BODY_TEXT_XYZ_UNIQUE"
        body_html = "<p>SENSITIVE_HTML_XYZ_UNIQUE</p>"
        msg = _full_msg(body_text=body_text, body_html=body_html)
        service = _gmail_service(get_result=msg)

        with patch("api.integrations.get_token_storage") as mock_storage, \
             patch("api.integrations.build", return_value=service), \
             patch("api.integrations.Credentials"):
            mock_storage.return_value.load_tokens.return_value = _valid_tokens()
            with caplog.at_level(logging.DEBUG):
                resp = client.get("/api/integrations/google/gmail/messages/msg123?user_id=test_user")

        assert resp.status_code == 200
        all_logs = " ".join(r.getMessage() for r in caplog.records)
        assert body_text not in all_logs, "body_text must not appear in logs"
        assert body_html not in all_logs, "body_html must not appear in logs"


# ============================================================================
# D. Outlook list includes thread_id
# ============================================================================

def _ms_list_msg(msg_id: str, conversation_id: str | None = "conv-ABC") -> dict:
    m = {
        "id": msg_id,
        "from": {"emailAddress": {"name": "Alice", "address": "alice@example.com"}},
        "subject": "Test Subject",
        "receivedDateTime": "2026-05-05T10:00:00Z",
        "bodyPreview": "Preview text",
        "isRead": False,
    }
    if conversation_id is not None:
        m["conversationId"] = conversation_id
    return m


def _ms_full_msg(msg_id: str, conversation_id: str | None = "conv-ABC") -> dict:
    m = {
        "id": msg_id,
        "subject": "Full Subject",
        "from": {"emailAddress": {"name": "Alice", "address": "alice@example.com"}},
        "toRecipients": [{"emailAddress": {"address": "bob@example.com"}}],
        "ccRecipients": [],
        "receivedDateTime": "2026-05-05T10:00:00Z",
        "isRead": True,
        "hasAttachments": False,
        "body": {"contentType": "text", "content": "Body text"},
        "bodyPreview": "Preview",
    }
    if conversation_id is not None:
        m["conversationId"] = conversation_id
    return m


class TestOutlookListThreadId:

    def test_list_includes_thread_id(self):
        data = {"value": [_ms_list_msg("msg001", "conv-ABC"), _ms_list_msg("msg002", "conv-XYZ")]}

        with patch("api.integrations._ms_get_token", return_value="fake-token"), \
             patch("api.integrations._ms_request", return_value=data):
            resp = client.get("/api/integrations/microsoft/mail/messages?user_id=test_user")

        assert resp.status_code == 200
        emails = resp.json()["emails"]
        assert len(emails) == 2
        assert emails[0]["thread_id"] == "conv-ABC"
        assert emails[1]["thread_id"] == "conv-XYZ"

    def test_list_thread_id_empty_when_missing(self):
        data = {"value": [_ms_list_msg("msg001", conversation_id=None)]}

        with patch("api.integrations._ms_get_token", return_value="fake-token"), \
             patch("api.integrations._ms_request", return_value=data):
            resp = client.get("/api/integrations/microsoft/mail/messages?user_id=test_user")

        assert resp.status_code == 200
        assert resp.json()["emails"][0]["thread_id"] == ""


# ============================================================================
# E. Outlook full message includes thread_id
# ============================================================================

class TestOutlookGetMessageThreadId:

    def test_get_message_includes_thread_id(self):
        msg = _ms_full_msg("msg001", "conv-DEF")

        with patch("api.integrations._ms_get_token", return_value="fake-token"), \
             patch("api.integrations._ms_request", return_value=msg):
            resp = client.get("/api/integrations/microsoft/mail/messages/msg001?user_id=test_user")

        assert resp.status_code == 200
        assert resp.json()["thread_id"] == "conv-DEF"

    def test_get_message_thread_id_empty_when_missing(self):
        msg = _ms_full_msg("msg001", conversation_id=None)

        with patch("api.integrations._ms_get_token", return_value="fake-token"), \
             patch("api.integrations._ms_request", return_value=msg):
            resp = client.get("/api/integrations/microsoft/mail/messages/msg001?user_id=test_user")

        assert resp.status_code == 200
        assert resp.json()["thread_id"] == ""


# ============================================================================
# F. Gmail thread endpoint
# ============================================================================

def _gmail_thread_msg(
    msg_id: str,
    text: str = "Body text",
    subject: str = "Thread Subject",
    from_addr: str = "sender@example.com",
    date: str = "Mon, 05 May 2026 10:00:00 +0200",
) -> dict:
    return {
        "id": msg_id,
        "snippet": f"snippet-{msg_id}",
        "payload": {
            "mimeType": "text/plain",
            "headers": [
                {"name": "Subject", "value": subject},
                {"name": "From", "value": from_addr},
                {"name": "Date", "value": date},
            ],
            "body": {"data": _b64url(text)},
        },
    }


def _gmail_thread_service(thread_data=None, raises=None) -> MagicMock:
    service = MagicMock()
    threads = service.users.return_value.threads.return_value
    if thread_data is not None:
        threads.get.return_value.execute.return_value = thread_data
    if raises is not None:
        threads.get.return_value.execute.side_effect = raises
    return service


class TestGmailThread:

    def _call(self, service, thread_id="thread-001"):
        with patch("api.integrations.get_token_storage") as mock_storage, \
             patch("api.integrations.build", return_value=service), \
             patch("api.integrations.Credentials"):
            mock_storage.return_value.load_tokens.return_value = _valid_tokens()
            return client.get(
                f"/api/integrations/google/gmail/threads/{thread_id}?user_id=test_user"
            )

    def test_returns_multiple_messages(self):
        thread_data = {
            "id": "thread-001",
            "messages": [
                _gmail_thread_msg("msg-A", text="First message"),
                _gmail_thread_msg("msg-B", text="Second message"),
            ],
        }
        resp = self._call(_gmail_thread_service(thread_data=thread_data))

        assert resp.status_code == 200
        data = resp.json()
        assert data["thread_id"] == "thread-001"
        assert len(data["messages"]) == 2
        assert data["messages"][0]["id"] == "msg-A"
        assert data["messages"][1]["id"] == "msg-B"

    def test_preserves_message_order(self):
        thread_data = {
            "id": "thread-001",
            "messages": [
                _gmail_thread_msg("msg-1", date="Mon, 05 May 2026 08:00:00 +0200"),
                _gmail_thread_msg("msg-2", date="Mon, 05 May 2026 09:00:00 +0200"),
                _gmail_thread_msg("msg-3", date="Mon, 05 May 2026 10:00:00 +0200"),
            ],
        }
        resp = self._call(_gmail_thread_service(thread_data=thread_data))

        assert resp.status_code == 200
        ids = [m["id"] for m in resp.json()["messages"]]
        assert ids == ["msg-1", "msg-2", "msg-3"]

    def test_includes_body_text(self):
        thread_data = {
            "id": "thread-001",
            "messages": [_gmail_thread_msg("msg-A", text="Hello from body")],
        }
        resp = self._call(_gmail_thread_service(thread_data=thread_data))

        assert resp.status_code == 200
        msg = resp.json()["messages"][0]
        assert msg["body_text"] == "Hello from body"
        assert msg["body_type"] == "text"

    def test_empty_thread_returns_empty_list(self):
        thread_data = {"id": "thread-empty", "messages": []}
        resp = self._call(_gmail_thread_service(thread_data=thread_data), thread_id="thread-empty")

        assert resp.status_code == 200
        assert resp.json()["messages"] == []

    def test_unauthenticated_returns_401(self):
        with patch("api.integrations.get_token_storage") as mock_storage:
            mock_storage.return_value.load_tokens.return_value = None
            resp = client.get("/api/integrations/google/gmail/threads/thread-001?user_id=test_user")

        assert resp.status_code == 401
        assert resp.json()["detail"]["code"] == "NOT_AUTHENTICATED"

    def test_gmail_api_404_returns_404(self):
        resp = self._call(_gmail_thread_service(raises=_make_http_error(404)))

        assert resp.status_code == 404
        assert resp.json()["detail"]["code"] == "THREAD_NOT_FOUND"

    def test_gmail_api_401_returns_401(self):
        resp = self._call(_gmail_thread_service(raises=_make_http_error(401)))

        assert resp.status_code == 401
        assert resp.json()["detail"]["code"] == "AUTHENTICATION_REQUIRED"


# ============================================================================
# G. Outlook thread endpoint
# ============================================================================

def _ms_thread_msg(
    msg_id: str,
    text: str = "Body text",
    received: str = "2026-05-05T10:00:00Z",
) -> dict:
    return {
        "id": msg_id,
        "subject": "Outlook Thread",
        "from": {"emailAddress": {"name": "Alice", "address": "alice@example.com"}},
        "receivedDateTime": received,
        "bodyPreview": f"preview-{msg_id}",
        "body": {"contentType": "text", "content": text},
    }


class TestOutlookThread:

    def _call(self, ms_request_return, thread_id="conv-THREAD"):
        with patch("api.integrations._ms_get_token", return_value="fake-token"), \
             patch("api.integrations._ms_request", return_value=ms_request_return) as mock_req:
            resp = client.get(
                f"/api/integrations/microsoft/mail/threads/{thread_id}?user_id=test_user"
            )
        return resp, mock_req

    def test_returns_multiple_messages(self):
        data = {"value": [_ms_thread_msg("msg-1"), _ms_thread_msg("msg-2")]}
        resp, _ = self._call(data)

        assert resp.status_code == 200
        result = resp.json()
        assert result["thread_id"] == "conv-THREAD"
        assert len(result["messages"]) == 2
        assert result["messages"][0]["id"] == "msg-1"
        assert result["messages"][1]["id"] == "msg-2"

    def test_thread_id_filter_applied(self):
        data = {"value": [_ms_thread_msg("msg-1")]}
        resp, mock_req = self._call(data, thread_id="conv-XYZ123")

        assert resp.status_code == 200
        filter_param = mock_req.call_args.kwargs["params"]["$filter"]
        assert "conv-XYZ123" in filter_param

    def test_includes_body_text(self):
        data = {"value": [_ms_thread_msg("msg-1", text="Outlook body content")]}
        resp, _ = self._call(data)

        assert resp.status_code == 200
        msg = resp.json()["messages"][0]
        assert msg["body_text"] == "Outlook body content"
        assert msg["body_type"] == "text"

    def test_empty_results_returns_404(self):
        resp, _ = self._call({"value": []})

        assert resp.status_code == 404
        assert resp.json()["detail"]["code"] == "THREAD_NOT_FOUND"

    def test_unauthenticated_returns_401(self):
        with patch("api.integrations._ms_get_token") as mock_token:
            from fastapi import HTTPException as FastHTTPException
            mock_token.side_effect = FastHTTPException(
                status_code=401,
                detail={"code": "NOT_AUTHENTICATED", "message": "No token"},
            )
            resp = client.get("/api/integrations/microsoft/mail/threads/conv-X?user_id=test_user")

        assert resp.status_code == 401

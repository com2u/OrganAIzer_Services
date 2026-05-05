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

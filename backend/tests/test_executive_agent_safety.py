"""
Executive Agent safety tests for services/executive_agent_service.py.

Covers:
  - Every propose_* tool returns type="confirmation_required" and does NOT
    make any HTTP call (no email sent, no calendar mutated)
  - cancel clears pending_action and makes no HTTP call
  - CONFIRMATION_REQUIRED_TOOLS is complete and correct

No real LLM calls, no real HTTP calls, no real Google/Microsoft API.
chat_with_tools is mocked for every test that reaches the LLM loop.
httpx.AsyncClient is patched to assert it is never called on propose_ paths.
"""

import asyncio
import json
import sys
import os
from unittest.mock import patch, MagicMock, AsyncMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from services.tool_definitions import TOOLS, CONFIRMATION_REQUIRED_TOOLS
from services.executive_agent_service import ExecutiveAgent


def _run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


def _llm_response(tool_name: str, args: dict) -> dict:
    """Fake chat_with_tools return value containing one tool call."""
    return {
        "tool_calls": [
            {
                "function": {
                    "name": tool_name,
                    "arguments": json.dumps(args),
                },
                "id": f"call_{tool_name}",
            }
        ],
        "content": None,
    }


def _mock_chat_service(response: dict) -> MagicMock:
    """Mock ChatService whose chat_with_tools always returns response."""
    svc = MagicMock()
    svc.chat_with_tools = AsyncMock(return_value=response)
    return svc


def _clear_sessions():
    ExecutiveAgent.sessions.clear()


# =============================================================================
# CONFIRMATION_REQUIRED_TOOLS completeness — no mocks needed
# =============================================================================

class TestConfirmationRequiredToolsCompleteness:
    """Pure data tests: the safety gate set must be exactly right."""

    def test_all_propose_tools_in_confirmation_set(self):
        propose_names = {
            t["function"]["name"]
            for t in TOOLS
            if t["function"]["name"].startswith("propose_")
        }
        for name in propose_names:
            assert name in CONFIRMATION_REQUIRED_TOOLS, (
                f"{name} is a propose_ tool but missing from CONFIRMATION_REQUIRED_TOOLS"
            )

    def test_read_tools_not_in_confirmation_set(self):
        for name in ("list_calendar_events", "read_emails", "lookup_contact"):
            assert name not in CONFIRMATION_REQUIRED_TOOLS

    def test_confirmation_set_has_exactly_six_tools(self):
        assert len(CONFIRMATION_REQUIRED_TOOLS) == 6

    def test_all_confirmation_tools_are_propose_tools(self):
        for name in CONFIRMATION_REQUIRED_TOOLS:
            assert name.startswith("propose_"), (
                f"{name!r} in CONFIRMATION_REQUIRED_TOOLS does not start with 'propose_'"
            )

    def test_confirmation_set_contains_expected_tools(self):
        expected = {
            "propose_create_calendar_event",
            "propose_update_calendar_event",
            "propose_delete_calendar_event",
            "propose_send_email",
            "propose_reply_email",
            "propose_create_recurring_event",
        }
        assert CONFIRMATION_REQUIRED_TOOLS == expected


# =============================================================================
# propose_send_email and propose_reply_email — no email sent
# =============================================================================

class TestProposeEmailDoesNotSend:

    def setup_method(self):
        _clear_sessions()

    def teardown_method(self):
        _clear_sessions()

    def test_propose_send_email_returns_confirmation_required(self):
        sid = "test_exec_send_email_cr"
        args = {"to": ["alice@example.com"], "subject": "Hello", "body": "Test body"}
        svc = _mock_chat_service(_llm_response("propose_send_email", args))

        with patch("services.executive_agent_service.get_chat_service", return_value=svc):
            agent = ExecutiveAgent(session_id=sid)
            result = _run(agent.process_message("send an email to alice", user_id="test_user"))

        assert result["type"] == "confirmation_required"
        assert result["success"] is True

    def test_propose_send_email_does_not_call_http(self):
        sid = "test_exec_send_email_http"
        args = {"to": ["alice@example.com"], "subject": "Hello", "body": "Test body"}
        svc = _mock_chat_service(_llm_response("propose_send_email", args))

        with patch("services.executive_agent_service.get_chat_service", return_value=svc):
            with patch("services.executive_agent_service.httpx.AsyncClient") as mock_client:
                agent = ExecutiveAgent(session_id=sid)
                _run(agent.process_message("send an email to alice", user_id="test_user"))

        mock_client.assert_not_called()

    def test_propose_send_email_sets_pending_action(self):
        sid = "test_exec_send_email_pend"
        args = {"to": ["alice@example.com"], "subject": "Hello", "body": "Test body"}
        svc = _mock_chat_service(_llm_response("propose_send_email", args))

        with patch("services.executive_agent_service.get_chat_service", return_value=svc):
            agent = ExecutiveAgent(session_id=sid)
            _run(agent.process_message("send an email to alice", user_id="test_user"))

        pending = agent.memory.get_pending_action()
        assert pending is not None
        assert pending["type"] == "propose_send_email"

    def test_propose_reply_email_returns_confirmation_required(self):
        sid = "test_exec_reply_email_cr"
        args = {
            "thread_id": "thread-123",
            "original_subject": "Meeting update",
            "body": "Sounds good, see you then.",
        }
        svc = _mock_chat_service(_llm_response("propose_reply_email", args))

        with patch("services.executive_agent_service.get_chat_service", return_value=svc):
            agent = ExecutiveAgent(session_id=sid)
            result = _run(agent.process_message("reply to the meeting email", user_id="test_user"))

        assert result["type"] == "confirmation_required"

    def test_propose_reply_email_does_not_call_http(self):
        sid = "test_exec_reply_email_http"
        args = {
            "thread_id": "thread-123",
            "original_subject": "Meeting update",
            "body": "Sounds good, see you then.",
        }
        svc = _mock_chat_service(_llm_response("propose_reply_email", args))

        with patch("services.executive_agent_service.get_chat_service", return_value=svc):
            with patch("services.executive_agent_service.httpx.AsyncClient") as mock_client:
                agent = ExecutiveAgent(session_id=sid)
                _run(agent.process_message("reply to the meeting email", user_id="test_user"))

        mock_client.assert_not_called()


# =============================================================================
# Calendar propose_ tools — no calendar mutated
# =============================================================================

class TestProposeCalendarDoesNotMutate:

    def setup_method(self):
        _clear_sessions()

    def teardown_method(self):
        _clear_sessions()

    def test_propose_create_event_returns_confirmation_required(self):
        sid = "test_exec_create_cal_cr"
        args = {
            "title": "Team Meeting",
            "start": "2026-06-01T10:00:00",
            "end": "2026-06-01T11:00:00",
        }
        svc = _mock_chat_service(_llm_response("propose_create_calendar_event", args))

        with patch("services.executive_agent_service.get_chat_service", return_value=svc):
            agent = ExecutiveAgent(session_id=sid)
            result = _run(agent.process_message("create a meeting", user_id="test_user"))

        assert result["type"] == "confirmation_required"

    def test_propose_create_event_does_not_call_http(self):
        sid = "test_exec_create_cal_http"
        args = {
            "title": "Team Meeting",
            "start": "2026-06-01T10:00:00",
            "end": "2026-06-01T11:00:00",
        }
        svc = _mock_chat_service(_llm_response("propose_create_calendar_event", args))

        with patch("services.executive_agent_service.get_chat_service", return_value=svc):
            with patch("services.executive_agent_service.httpx.AsyncClient") as mock_client:
                agent = ExecutiveAgent(session_id=sid)
                _run(agent.process_message("create a meeting", user_id="test_user"))

        mock_client.assert_not_called()

    def test_propose_update_event_returns_confirmation_required(self):
        sid = "test_exec_update_cal_cr"
        args = {
            "event_id": "abc123",
            "event_title": "Team Meeting",
            "new_title": "Project Sync",
        }
        svc = _mock_chat_service(_llm_response("propose_update_calendar_event", args))

        with patch("services.executive_agent_service.get_chat_service", return_value=svc):
            agent = ExecutiveAgent(session_id=sid)
            result = _run(agent.process_message("rename my meeting", user_id="test_user"))

        assert result["type"] == "confirmation_required"

    def test_propose_update_event_does_not_call_http(self):
        sid = "test_exec_update_cal_http"
        args = {
            "event_id": "abc123",
            "event_title": "Team Meeting",
            "new_title": "Project Sync",
        }
        svc = _mock_chat_service(_llm_response("propose_update_calendar_event", args))

        with patch("services.executive_agent_service.get_chat_service", return_value=svc):
            with patch("services.executive_agent_service.httpx.AsyncClient") as mock_client:
                agent = ExecutiveAgent(session_id=sid)
                _run(agent.process_message("rename my meeting", user_id="test_user"))

        mock_client.assert_not_called()

    def test_propose_delete_event_returns_confirmation_required(self):
        sid = "test_exec_delete_cal_cr"
        args = {"event_id": "abc123", "event_title": "Team Meeting"}
        svc = _mock_chat_service(_llm_response("propose_delete_calendar_event", args))

        with patch("services.executive_agent_service.get_chat_service", return_value=svc):
            agent = ExecutiveAgent(session_id=sid)
            result = _run(agent.process_message("delete my meeting", user_id="test_user"))

        assert result["type"] == "confirmation_required"

    def test_propose_delete_event_does_not_call_http(self):
        sid = "test_exec_delete_cal_http"
        args = {"event_id": "abc123", "event_title": "Team Meeting"}
        svc = _mock_chat_service(_llm_response("propose_delete_calendar_event", args))

        with patch("services.executive_agent_service.get_chat_service", return_value=svc):
            with patch("services.executive_agent_service.httpx.AsyncClient") as mock_client:
                agent = ExecutiveAgent(session_id=sid)
                _run(agent.process_message("delete my meeting", user_id="test_user"))

        mock_client.assert_not_called()

    def test_propose_create_recurring_event_returns_confirmation_required(self):
        sid = "test_exec_recurring_cr"
        args = {
            "title": "Weekly Standup",
            "start": "2026-06-02T09:00:00",
            "end": "2026-06-02T09:30:00",
            "recurrence": "weekly",
        }
        svc = _mock_chat_service(_llm_response("propose_create_recurring_event", args))

        with patch("services.executive_agent_service.get_chat_service", return_value=svc):
            agent = ExecutiveAgent(session_id=sid)
            result = _run(agent.process_message("create weekly standup", user_id="test_user"))

        assert result["type"] == "confirmation_required"

    def test_propose_create_recurring_event_does_not_call_http(self):
        sid = "test_exec_recurring_http"
        args = {
            "title": "Weekly Standup",
            "start": "2026-06-02T09:00:00",
            "end": "2026-06-02T09:30:00",
            "recurrence": "weekly",
        }
        svc = _mock_chat_service(_llm_response("propose_create_recurring_event", args))

        with patch("services.executive_agent_service.get_chat_service", return_value=svc):
            with patch("services.executive_agent_service.httpx.AsyncClient") as mock_client:
                agent = ExecutiveAgent(session_id=sid)
                _run(agent.process_message("create weekly standup", user_id="test_user"))

        mock_client.assert_not_called()


# =============================================================================
# cancel clears pending_action — no HTTP call
# =============================================================================

class TestCancelClearsPendingAction:

    def setup_method(self):
        _clear_sessions()

    def teardown_method(self):
        _clear_sessions()

    def test_cancel_after_propose_email_clears_pending(self):
        sid = "test_exec_cancel_email"
        args = {"to": ["bob@example.com"], "subject": "Test", "body": "Hi"}
        svc = _mock_chat_service(_llm_response("propose_send_email", args))

        with patch("services.executive_agent_service.get_chat_service", return_value=svc):
            agent = ExecutiveAgent(session_id=sid)
            _run(agent.process_message("send email to bob", user_id="test_user"))

        assert agent.memory.get_pending_action() is not None

        cancel_result = _run(agent.process_message("cancel", user_id="test_user"))

        assert cancel_result["type"] == "cancelled"
        assert cancel_result["success"] is True
        assert agent.memory.get_pending_action() is None

    def test_no_after_propose_cancels(self):
        sid = "test_exec_cancel_no"
        args = {"to": ["carol@example.com"], "subject": "Hello", "body": "Hi"}
        svc = _mock_chat_service(_llm_response("propose_send_email", args))

        with patch("services.executive_agent_service.get_chat_service", return_value=svc):
            agent = ExecutiveAgent(session_id=sid)
            _run(agent.process_message("send email to carol", user_id="test_user"))

        cancel_result = _run(agent.process_message("no", user_id="test_user"))

        assert cancel_result["type"] == "cancelled"
        assert agent.memory.get_pending_action() is None

    def test_stop_after_propose_calendar_cancels(self):
        sid = "test_exec_cancel_stop"
        args = {"event_id": "ev-456", "event_title": "Old Meeting"}
        svc = _mock_chat_service(_llm_response("propose_delete_calendar_event", args))

        with patch("services.executive_agent_service.get_chat_service", return_value=svc):
            agent = ExecutiveAgent(session_id=sid)
            _run(agent.process_message("delete the meeting", user_id="test_user"))

        cancel_result = _run(agent.process_message("stop", user_id="test_user"))

        assert cancel_result["type"] == "cancelled"
        assert agent.memory.get_pending_action() is None

    def test_cancel_makes_no_http_call(self):
        sid = "test_exec_cancel_http"
        args = {"to": ["bob@example.com"], "subject": "Test", "body": "Hi"}
        svc = _mock_chat_service(_llm_response("propose_send_email", args))

        with patch("services.executive_agent_service.get_chat_service", return_value=svc):
            with patch("services.executive_agent_service.httpx.AsyncClient") as mock_client:
                agent = ExecutiveAgent(session_id=sid)
                _run(agent.process_message("send email to bob", user_id="test_user"))
                _run(agent.process_message("cancel", user_id="test_user"))

        mock_client.assert_not_called()


# =============================================================================
# No HTTP on first turn — all 6 propose_ tools
# =============================================================================

class TestNoHttpOnAnyProposeTool:
    """httpx.AsyncClient must never be entered on any propose_ first turn."""

    def setup_method(self):
        _clear_sessions()

    def teardown_method(self):
        _clear_sessions()

    def _assert_no_http_and_confirm(self, sid: str, tool_name: str, args: dict):
        svc = _mock_chat_service(_llm_response(tool_name, args))

        with patch("services.executive_agent_service.get_chat_service", return_value=svc):
            with patch("services.executive_agent_service.httpx.AsyncClient") as mock_client:
                agent = ExecutiveAgent(session_id=sid)
                result = _run(agent.process_message("do it", user_id="test_user"))

        assert result["type"] == "confirmation_required", (
            f"{tool_name}: expected type='confirmation_required', got {result['type']!r}"
        )
        mock_client.assert_not_called()

    def test_no_http_on_propose_send_email(self):
        self._assert_no_http_and_confirm(
            "test_exec_nhttp_send",
            "propose_send_email",
            {"to": ["x@y.com"], "subject": "S", "body": "B"},
        )

    def test_no_http_on_propose_reply_email(self):
        self._assert_no_http_and_confirm(
            "test_exec_nhttp_reply",
            "propose_reply_email",
            {"thread_id": "t1", "original_subject": "Test", "body": "OK"},
        )

    def test_no_http_on_propose_create_calendar_event(self):
        self._assert_no_http_and_confirm(
            "test_exec_nhttp_create",
            "propose_create_calendar_event",
            {"title": "Meeting", "start": "2026-07-01T10:00:00", "end": "2026-07-01T11:00:00"},
        )

    def test_no_http_on_propose_update_calendar_event(self):
        self._assert_no_http_and_confirm(
            "test_exec_nhttp_update",
            "propose_update_calendar_event",
            {"event_id": "ev1", "event_title": "Meeting", "new_title": "Sync"},
        )

    def test_no_http_on_propose_delete_calendar_event(self):
        self._assert_no_http_and_confirm(
            "test_exec_nhttp_delete",
            "propose_delete_calendar_event",
            {"event_id": "ev2", "event_title": "Old Meeting"},
        )

    def test_no_http_on_propose_create_recurring_event(self):
        self._assert_no_http_and_confirm(
            "test_exec_nhttp_recurring",
            "propose_create_recurring_event",
            {
                "title": "Standup",
                "start": "2026-07-01T09:00:00",
                "end": "2026-07-01T09:30:00",
                "recurrence": "weekly",
            },
        )


# =============================================================================
# read_emails updates ConversationMemory email fields
# =============================================================================

class TestReadEmailsUpdatesMemory:

    def setup_method(self):
        _clear_sessions()

    def teardown_method(self):
        _clear_sessions()

    def _email_list_response(self):
        return {
            "emails": [
                {
                    "id": "msg-001",
                    "thread_id": "thread-XYZ",
                    "subject": "Budget Q3",
                    "from": "Alice Example <alice@example.com>",
                    "received": "2026-05-05T10:00:00Z",
                    "preview": "See attached",
                    "unread": True,
                }
            ],
            "total": 1,
        }

    def _make_http_mock(self, json_data):
        """Build an httpx.AsyncClient mock that returns json_data on .get()."""
        mock_resp = MagicMock()
        mock_resp.is_success = True
        mock_resp.status_code = 200
        mock_resp.json.return_value = json_data

        mock_http = AsyncMock()
        mock_http.get = AsyncMock(return_value=mock_resp)

        mock_cm = MagicMock()
        mock_cm.__aenter__ = AsyncMock(return_value=mock_http)
        mock_cm.__aexit__ = AsyncMock(return_value=False)

        mock_cls = MagicMock(return_value=mock_cm)
        return mock_cls

    def test_read_emails_sets_thread_id(self):
        sid = "test_mem_thread_id"
        svc = MagicMock()
        svc.chat_with_tools = AsyncMock(side_effect=[
            _llm_response("read_emails", {"count": 3}),
            {"tool_calls": None, "content": "Here are your emails."},
        ])
        mock_cls = self._make_http_mock(self._email_list_response())

        with patch("services.executive_agent_service.get_chat_service", return_value=svc), \
             patch("services.executive_agent_service.httpx.AsyncClient", mock_cls):
            agent = ExecutiveAgent(session_id=sid)
            _run(agent.process_message("show my emails", user_id="test_user"))

        assert agent.memory.last_email_thread_id == "thread-XYZ"

    def test_read_emails_sets_message_id(self):
        sid = "test_mem_message_id"
        svc = MagicMock()
        svc.chat_with_tools = AsyncMock(side_effect=[
            _llm_response("read_emails", {"count": 3}),
            {"tool_calls": None, "content": "Here are your emails."},
        ])
        mock_cls = self._make_http_mock(self._email_list_response())

        with patch("services.executive_agent_service.get_chat_service", return_value=svc), \
             patch("services.executive_agent_service.httpx.AsyncClient", mock_cls):
            agent = ExecutiveAgent(session_id=sid)
            _run(agent.process_message("show my emails", user_id="test_user"))

        assert agent.memory.last_email_message_id == "msg-001"

    def test_read_emails_sets_subject(self):
        sid = "test_mem_subject"
        svc = MagicMock()
        svc.chat_with_tools = AsyncMock(side_effect=[
            _llm_response("read_emails", {"count": 3}),
            {"tool_calls": None, "content": "Here are your emails."},
        ])
        mock_cls = self._make_http_mock(self._email_list_response())

        with patch("services.executive_agent_service.get_chat_service", return_value=svc), \
             patch("services.executive_agent_service.httpx.AsyncClient", mock_cls):
            agent = ExecutiveAgent(session_id=sid)
            _run(agent.process_message("show my emails", user_id="test_user"))

        assert agent.memory.last_email_subject == "Budget Q3"

    def test_read_emails_sets_sender_and_address(self):
        sid = "test_mem_sender"
        svc = MagicMock()
        svc.chat_with_tools = AsyncMock(side_effect=[
            _llm_response("read_emails", {"count": 3}),
            {"tool_calls": None, "content": "Here are your emails."},
        ])
        mock_cls = self._make_http_mock(self._email_list_response())

        with patch("services.executive_agent_service.get_chat_service", return_value=svc), \
             patch("services.executive_agent_service.httpx.AsyncClient", mock_cls):
            agent = ExecutiveAgent(session_id=sid)
            _run(agent.process_message("show my emails", user_id="test_user"))

        assert agent.memory.last_email_sender == "Alice Example <alice@example.com>"
        assert agent.memory.last_email_sender_address == "alice@example.com"

    def test_read_emails_no_angle_brackets_uses_full_from(self):
        sid = "test_mem_sender_plain"
        data = {
            "emails": [{
                "id": "msg-002",
                "thread_id": "thread-AAA",
                "subject": "Hello",
                "from": "bob@example.com",
                "received": "",
                "preview": "",
                "unread": False,
            }],
            "total": 1,
        }
        svc = MagicMock()
        svc.chat_with_tools = AsyncMock(side_effect=[
            _llm_response("read_emails", {"count": 1}),
            {"tool_calls": None, "content": "Got it."},
        ])
        mock_cls = self._make_http_mock(data)

        with patch("services.executive_agent_service.get_chat_service", return_value=svc), \
             patch("services.executive_agent_service.httpx.AsyncClient", mock_cls):
            agent = ExecutiveAgent(session_id=sid)
            _run(agent.process_message("show my emails", user_id="test_user"))

        assert agent.memory.last_email_sender_address == "bob@example.com"


# =============================================================================
# Empty/missing thread_id blocks reply before any HTTP call
# =============================================================================

class TestReplyEmailEmptyThreadIdGuard:

    def setup_method(self):
        _clear_sessions()

    def teardown_method(self):
        _clear_sessions()

    def _agent_with_pending_reply(self, sid, thread_id_value, include_key=True):
        svc = MagicMock()
        svc.chat_with_tools = AsyncMock()
        with patch("services.executive_agent_service.get_chat_service", return_value=svc):
            agent = ExecutiveAgent(session_id=sid)
        args = {"original_subject": "Test", "body": "Hello", "provider": "gmail"}
        if include_key:
            args["thread_id"] = thread_id_value
        agent.memory.set_pending_action("propose_reply_email", args)
        return agent

    def test_empty_thread_id_returns_error(self):
        sid = "test_guard_empty_tid_err"
        agent = self._agent_with_pending_reply(sid, "")

        with patch("services.executive_agent_service.httpx.AsyncClient") as mock_http:
            result = _run(agent.process_message("yes", user_id="test_user"))

        assert result["type"] == "error"
        assert result["success"] is False
        mock_http.assert_not_called()

    def test_empty_thread_id_clears_pending_action(self):
        sid = "test_guard_empty_tid_clear"
        agent = self._agent_with_pending_reply(sid, "")

        with patch("services.executive_agent_service.httpx.AsyncClient"):
            _run(agent.process_message("yes", user_id="test_user"))

        assert agent.memory.get_pending_action() is None

    def test_missing_thread_id_key_returns_error(self):
        sid = "test_guard_missing_tid_err"
        agent = self._agent_with_pending_reply(sid, None, include_key=False)

        with patch("services.executive_agent_service.httpx.AsyncClient") as mock_http:
            result = _run(agent.process_message("yes", user_id="test_user"))

        assert result["type"] == "error"
        mock_http.assert_not_called()

    def test_missing_thread_id_clears_pending_action(self):
        sid = "test_guard_missing_tid_clear"
        agent = self._agent_with_pending_reply(sid, None, include_key=False)

        with patch("services.executive_agent_service.httpx.AsyncClient"):
            _run(agent.process_message("yes", user_id="test_user"))

        assert agent.memory.get_pending_action() is None

    def test_valid_thread_id_does_not_trigger_guard(self):
        """Confirm that a real thread_id still reaches httpx (the guard is not over-blocking)."""
        sid = "test_guard_valid_tid"
        svc = MagicMock()
        svc.chat_with_tools = AsyncMock()
        with patch("services.executive_agent_service.get_chat_service", return_value=svc):
            agent = ExecutiveAgent(session_id=sid)
        agent.memory.set_pending_action("propose_reply_email", {
            "thread_id": "thread-REAL",
            "original_subject": "Budget",
            "body": "Confirmed.",
            "provider": "gmail",
        })

        mock_resp = MagicMock()
        mock_resp.is_success = True
        mock_resp.json.return_value = {}
        mock_http = AsyncMock()
        mock_http.post = AsyncMock(return_value=mock_resp)
        mock_cm = MagicMock()
        mock_cm.__aenter__ = AsyncMock(return_value=mock_http)
        mock_cm.__aexit__ = AsyncMock(return_value=False)
        mock_cls = MagicMock(return_value=mock_cm)

        with patch("services.executive_agent_service.httpx.AsyncClient", mock_cls):
            _run(agent.process_message("yes", user_id="test_user"))

        mock_cls.assert_called_once()


# =============================================================================
# System prompt includes last email context when memory is set
# =============================================================================

class TestSystemPromptEmailContext:

    def setup_method(self):
        _clear_sessions()

    def teardown_method(self):
        _clear_sessions()

    def _make_agent(self, sid):
        svc = MagicMock()
        with patch("services.executive_agent_service.get_chat_service", return_value=svc):
            return ExecutiveAgent(session_id=sid)

    def test_email_context_in_prompt_when_memory_set(self):
        agent = self._make_agent("test_sp_email_set")
        agent.memory.last_email_subject = "Budget Q3"
        agent.memory.last_email_thread_id = "thread-XYZ"
        agent.memory.last_email_sender = "Alice <alice@example.com>"

        prompt = agent._build_system_prompt()

        assert "thread-XYZ" in prompt
        assert "Budget Q3" in prompt

    def test_email_context_absent_when_memory_empty(self):
        agent = self._make_agent("test_sp_email_empty")
        # All email fields default to None — no writes

        prompt = agent._build_system_prompt()

        assert "Last email thread" not in prompt

    def test_system_prompt_contains_reply_instruction(self):
        agent = self._make_agent("test_sp_reply_instr")

        prompt = agent._build_system_prompt()

        assert "propose_reply_email" in prompt
        assert "thread_id" in prompt


# =============================================================================
# read_email_detail and read_email_thread tool definitions
# =============================================================================

class TestEmailContextToolDefinitions:
    """Pure data tests — no agent or HTTP needed."""

    def test_read_email_detail_in_tools(self):
        names = [t["function"]["name"] for t in TOOLS]
        assert "read_email_detail" in names

    def test_read_email_thread_in_tools(self):
        names = [t["function"]["name"] for t in TOOLS]
        assert "read_email_thread" in names

    def test_read_email_detail_not_confirmation_required(self):
        assert "read_email_detail" not in CONFIRMATION_REQUIRED_TOOLS

    def test_read_email_thread_not_confirmation_required(self):
        assert "read_email_thread" not in CONFIRMATION_REQUIRED_TOOLS


# =============================================================================
# read_email_detail — HTTP routing, memory updates, safety
# =============================================================================

class TestReadEmailDetail:

    def setup_method(self):
        _clear_sessions()

    def teardown_method(self):
        _clear_sessions()

    def _make_http_mock(self, json_data, status_code=200):
        mock_resp = MagicMock()
        mock_resp.is_success = 200 <= status_code < 300
        mock_resp.status_code = status_code
        mock_resp.json.return_value = json_data

        mock_http = AsyncMock()
        mock_http.get = AsyncMock(return_value=mock_resp)

        mock_cm = MagicMock()
        mock_cm.__aenter__ = AsyncMock(return_value=mock_http)
        mock_cm.__aexit__ = AsyncMock(return_value=False)

        return MagicMock(return_value=mock_cm), mock_http

    def _detail_payload(self, body_text="Meeting on Friday at 14:00.", body_html="<p>...</p>"):
        return {
            "id": "msg-detail-001",
            "thread_id": "thread-DET",
            "subject": "Upcoming Meeting",
            "from": "Boss <boss@corp.com>",
            "body_text": body_text,
            "body_html": body_html,
        }

    def test_gmail_endpoint_called(self):
        msg_id = "msg-gmail-123"
        svc = MagicMock()
        svc.chat_with_tools = AsyncMock(side_effect=[
            _llm_response("read_email_detail", {"message_id": msg_id, "provider": "gmail"}),
            {"tool_calls": None, "content": "Done."},
        ])
        mock_cls, mock_http = self._make_http_mock(self._detail_payload())

        with patch("services.executive_agent_service.get_chat_service", return_value=svc), \
             patch("services.executive_agent_service.httpx.AsyncClient", mock_cls):
            agent = ExecutiveAgent(session_id="test_det_gmail")
            _run(agent.process_message("read the email", user_id="u1"))

        call_url = mock_http.get.call_args[0][0]
        assert "google/gmail/messages/" in call_url
        assert msg_id in call_url

    def test_outlook_endpoint_called(self):
        msg_id = "msg-outlook-456"
        svc = MagicMock()
        svc.chat_with_tools = AsyncMock(side_effect=[
            _llm_response("read_email_detail", {"message_id": msg_id, "provider": "outlook"}),
            {"tool_calls": None, "content": "Done."},
        ])
        mock_cls, mock_http = self._make_http_mock(self._detail_payload())

        with patch("services.executive_agent_service.get_chat_service", return_value=svc), \
             patch("services.executive_agent_service.httpx.AsyncClient", mock_cls):
            agent = ExecutiveAgent(session_id="test_det_outlook")
            _run(agent.process_message("read the email", user_id="u1"))

        call_url = mock_http.get.call_args[0][0]
        assert "microsoft/mail/messages/" in call_url
        assert msg_id in call_url

    def test_updates_memory_fields(self):
        svc = MagicMock()
        svc.chat_with_tools = AsyncMock(side_effect=[
            _llm_response("read_email_detail", {"message_id": "msg-detail-001", "provider": "gmail"}),
            {"tool_calls": None, "content": "Here is the email."},
        ])
        mock_cls, _ = self._make_http_mock(self._detail_payload())

        with patch("services.executive_agent_service.get_chat_service", return_value=svc), \
             patch("services.executive_agent_service.httpx.AsyncClient", mock_cls):
            agent = ExecutiveAgent(session_id="test_det_memory")
            _run(agent.process_message("read the email", user_id="u1"))

        assert agent.memory.last_email_thread_id == "thread-DET"
        assert agent.memory.last_email_message_id == "msg-detail-001"
        assert agent.memory.last_email_subject == "Upcoming Meeting"
        assert agent.memory.last_email_sender == "Boss <boss@corp.com>"
        assert agent.memory.last_email_sender_address == "boss@corp.com"

    def test_body_html_stripped(self):
        """body_html must not appear in the tool result sent back to the LLM."""
        svc = MagicMock()
        svc.chat_with_tools = AsyncMock(side_effect=[
            _llm_response("read_email_detail", {"message_id": "msg-x", "provider": "gmail"}),
            {"tool_calls": None, "content": "Done."},
        ])
        mock_cls, _ = self._make_http_mock(self._detail_payload(body_html="<html>SECRET_HTML</html>"))

        with patch("services.executive_agent_service.get_chat_service", return_value=svc), \
             patch("services.executive_agent_service.httpx.AsyncClient", mock_cls):
            agent = ExecutiveAgent(session_id="test_det_no_html")
            _run(agent.process_message("read the email", user_id="u1"))

        second_call_messages = svc.chat_with_tools.call_args_list[1][0][0]
        tool_msgs = [m for m in second_call_messages if m.get("role") == "tool"]
        assert tool_msgs, "No tool result message found in second LLM call"
        tool_content = json.loads(tool_msgs[0]["content"])
        assert "body_html" not in tool_content
        assert "SECRET_HTML" not in str(tool_content)

    def test_body_text_truncated_to_3000(self):
        """body_text returned to the LLM must be capped at 3000 characters."""
        svc = MagicMock()
        svc.chat_with_tools = AsyncMock(side_effect=[
            _llm_response("read_email_detail", {"message_id": "msg-y", "provider": "gmail"}),
            {"tool_calls": None, "content": "Done."},
        ])
        mock_cls, _ = self._make_http_mock(self._detail_payload(body_text="A" * 5000, body_html=""))

        with patch("services.executive_agent_service.get_chat_service", return_value=svc), \
             patch("services.executive_agent_service.httpx.AsyncClient", mock_cls):
            agent = ExecutiveAgent(session_id="test_det_truncate")
            _run(agent.process_message("read the email", user_id="u1"))

        second_call_messages = svc.chat_with_tools.call_args_list[1][0][0]
        tool_msgs = [m for m in second_call_messages if m.get("role") == "tool"]
        tool_content = json.loads(tool_msgs[0]["content"])
        assert len(tool_content.get("body_text", "")) <= 3000

    def test_body_not_in_log_calls(self):
        """logger.info must not emit the raw body text."""
        secret_body = "CONFIDENTIAL_BODY_XYZ_12345"
        svc = MagicMock()
        svc.chat_with_tools = AsyncMock(side_effect=[
            _llm_response("read_email_detail", {"message_id": "msg-z", "provider": "gmail"}),
            {"tool_calls": None, "content": "Done."},
        ])
        mock_cls, _ = self._make_http_mock(self._detail_payload(body_text=secret_body, body_html=""))

        with patch("services.executive_agent_service.get_chat_service", return_value=svc), \
             patch("services.executive_agent_service.httpx.AsyncClient", mock_cls), \
             patch("services.executive_agent_service.logger") as mock_logger:
            agent = ExecutiveAgent(session_id="test_det_no_log_body")
            _run(agent.process_message("read the email", user_id="u1"))

        all_log_text = " ".join(
            str(arg)
            for call in mock_logger.info.call_args_list
            for arg in call[0]
        )
        assert secret_body not in all_log_text


# =============================================================================
# read_email_thread — HTTP routing, memory updates, safety
# =============================================================================

class TestReadEmailThread:

    def setup_method(self):
        _clear_sessions()

    def teardown_method(self):
        _clear_sessions()

    def _make_http_mock(self, json_data, status_code=200):
        mock_resp = MagicMock()
        mock_resp.is_success = 200 <= status_code < 300
        mock_resp.status_code = status_code
        mock_resp.json.return_value = json_data

        mock_http = AsyncMock()
        mock_http.get = AsyncMock(return_value=mock_resp)

        mock_cm = MagicMock()
        mock_cm.__aenter__ = AsyncMock(return_value=mock_http)
        mock_cm.__aexit__ = AsyncMock(return_value=False)

        return MagicMock(return_value=mock_cm), mock_http

    def _thread_payload(self, n_messages=3, body_text_len=50):
        return {
            "thread_id": "thread-THR",
            "messages": [
                {
                    "id": f"msg-{i}",
                    "thread_id": "thread-THR",
                    "subject": "Project" if i == 0 else "Re: Project",
                    "from": f"Person{i} <p{i}@corp.com>",
                    "body_text": "X" * body_text_len,
                    "body_html": f"<p>Message {i}</p>",
                }
                for i in range(n_messages)
            ],
        }

    def test_gmail_thread_endpoint_called(self):
        thread_id = "thread-gmail-999"
        svc = MagicMock()
        svc.chat_with_tools = AsyncMock(side_effect=[
            _llm_response("read_email_thread", {"thread_id": thread_id, "provider": "gmail"}),
            {"tool_calls": None, "content": "Done."},
        ])
        mock_cls, mock_http = self._make_http_mock(self._thread_payload())

        with patch("services.executive_agent_service.get_chat_service", return_value=svc), \
             patch("services.executive_agent_service.httpx.AsyncClient", mock_cls):
            agent = ExecutiveAgent(session_id="test_thr_gmail")
            _run(agent.process_message("read the thread", user_id="u1"))

        call_url = mock_http.get.call_args[0][0]
        assert "google/gmail/threads/" in call_url
        assert thread_id in call_url

    def test_outlook_thread_endpoint_called(self):
        thread_id = "thread-outlook-777"
        svc = MagicMock()
        svc.chat_with_tools = AsyncMock(side_effect=[
            _llm_response("read_email_thread", {"thread_id": thread_id, "provider": "outlook"}),
            {"tool_calls": None, "content": "Done."},
        ])
        mock_cls, mock_http = self._make_http_mock(self._thread_payload())

        with patch("services.executive_agent_service.get_chat_service", return_value=svc), \
             patch("services.executive_agent_service.httpx.AsyncClient", mock_cls):
            agent = ExecutiveAgent(session_id="test_thr_outlook")
            _run(agent.process_message("read the thread", user_id="u1"))

        call_url = mock_http.get.call_args[0][0]
        assert "microsoft/mail/threads/" in call_url
        assert thread_id in call_url

    def test_updates_memory_from_thread(self):
        """Memory fields come from first message (sender/subject) and thread_id from response."""
        svc = MagicMock()
        svc.chat_with_tools = AsyncMock(side_effect=[
            _llm_response("read_email_thread", {"thread_id": "thread-THR", "provider": "gmail"}),
            {"tool_calls": None, "content": "Here is the thread."},
        ])
        mock_cls, _ = self._make_http_mock(self._thread_payload(3))

        with patch("services.executive_agent_service.get_chat_service", return_value=svc), \
             patch("services.executive_agent_service.httpx.AsyncClient", mock_cls):
            agent = ExecutiveAgent(session_id="test_thr_memory")
            _run(agent.process_message("read the thread", user_id="u1"))

        assert agent.memory.last_email_thread_id == "thread-THR"
        assert agent.memory.last_email_subject == "Project"
        assert agent.memory.last_email_sender_address == "p0@corp.com"

    def test_truncates_to_8_messages(self):
        """A thread with 15 messages must be cut to 8 before returning to the LLM."""
        svc = MagicMock()
        svc.chat_with_tools = AsyncMock(side_effect=[
            _llm_response("read_email_thread", {"thread_id": "thread-THR", "provider": "gmail"}),
            {"tool_calls": None, "content": "Done."},
        ])
        mock_cls, _ = self._make_http_mock(self._thread_payload(n_messages=15))

        with patch("services.executive_agent_service.get_chat_service", return_value=svc), \
             patch("services.executive_agent_service.httpx.AsyncClient", mock_cls):
            agent = ExecutiveAgent(session_id="test_thr_truncate_msgs")
            _run(agent.process_message("read the thread", user_id="u1"))

        second_call_messages = svc.chat_with_tools.call_args_list[1][0][0]
        tool_msgs = [m for m in second_call_messages if m.get("role") == "tool"]
        tool_content = json.loads(tool_msgs[0]["content"])
        assert len(tool_content.get("messages", [])) <= 8

    def test_truncates_message_body_text(self):
        """Each message's body_text must be capped at 2000 characters."""
        svc = MagicMock()
        svc.chat_with_tools = AsyncMock(side_effect=[
            _llm_response("read_email_thread", {"thread_id": "thread-THR", "provider": "gmail"}),
            {"tool_calls": None, "content": "Done."},
        ])
        mock_cls, _ = self._make_http_mock(self._thread_payload(n_messages=2, body_text_len=4000))

        with patch("services.executive_agent_service.get_chat_service", return_value=svc), \
             patch("services.executive_agent_service.httpx.AsyncClient", mock_cls):
            agent = ExecutiveAgent(session_id="test_thr_truncate_body")
            _run(agent.process_message("read the thread", user_id="u1"))

        second_call_messages = svc.chat_with_tools.call_args_list[1][0][0]
        tool_msgs = [m for m in second_call_messages if m.get("role") == "tool"]
        tool_content = json.loads(tool_msgs[0]["content"])
        for msg in tool_content.get("messages", []):
            assert len(msg.get("body_text", "")) <= 2000

    def test_body_html_stripped_from_thread_messages(self):
        """body_html must not appear in any thread message returned to the LLM."""
        svc = MagicMock()
        svc.chat_with_tools = AsyncMock(side_effect=[
            _llm_response("read_email_thread", {"thread_id": "thread-THR", "provider": "gmail"}),
            {"tool_calls": None, "content": "Done."},
        ])
        mock_cls, _ = self._make_http_mock(self._thread_payload(2))

        with patch("services.executive_agent_service.get_chat_service", return_value=svc), \
             patch("services.executive_agent_service.httpx.AsyncClient", mock_cls):
            agent = ExecutiveAgent(session_id="test_thr_no_html")
            _run(agent.process_message("read the thread", user_id="u1"))

        second_call_messages = svc.chat_with_tools.call_args_list[1][0][0]
        tool_msgs = [m for m in second_call_messages if m.get("role") == "tool"]
        tool_content = json.loads(tool_msgs[0]["content"])
        for msg in tool_content.get("messages", []):
            assert "body_html" not in msg

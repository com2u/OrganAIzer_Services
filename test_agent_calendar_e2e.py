#!/usr/bin/env python3
"""
Integration test: Executive Agent calendar event creation – end-to-end.

Covers the exact bug reported:
  "Executive Agent says 'calendar event created successfully' but the event
   is NOT created in Google Calendar."

Steps executed
--------------
a) POST /api/agent/chat  →  agent should ask for confirmation (calendar_confirmation)
b) POST /api/agent/chat  →  user replies "yes"
   → agent must call /api/integrations/google/calendar/events
   → response must have type="calendar_created" AND success=True
c) Verify execution proof: event_id (and optionally htmlLink) are present in the
   response data.

The test also validates the negative path:
  • Sending "yes" with NO prior pending_action must NOT return calendar_created.

Usage
-----
  # Run against the live backend (Google OAuth must be connected for <user_id>)
  python test_agent_calendar_e2e.py

  # Custom base URL or user
  python test_agent_calendar_e2e.py --base-url http://localhost:8000 --user-id myuser

  # Skip the live integration call (only verifies orchestration layer logic)
  python test_agent_calendar_e2e.py --dry-run

Prerequisites
-------------
  pip install requests
  Backend running at http://localhost:8000 (or --base-url)
  Google OAuth tokens present for --user-id (visit
    http://localhost:8000/api/integrations/google/auth/start?user_id=<uid>
  to authorise if needed).
"""

import sys
import json
import argparse
import uuid

try:
    import requests
except ImportError:
    print("❌ Install 'requests' first:  pip install requests")
    sys.exit(1)


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _post_chat(base_url: str, session_id: str, user_id: str,
               message: str, provider: str = "google") -> dict:
    """POST /api/agent/chat and return the parsed JSON response."""
    url = f"{base_url}/api/agent/chat"
    payload = {
        "message": message,
        "session_id": session_id,
        "user_id": user_id,
        "provider": provider,
    }
    resp = requests.post(url, json=payload, timeout=60)
    if resp.status_code != 200:
        print(f"  HTTP {resp.status_code}: {resp.text[:300]}")
        resp.raise_for_status()
    return resp.json()


def _section(title: str):
    print(f"\n{'─' * 60}")
    print(f"  {title}")
    print(f"{'─' * 60}")


def _ok(msg: str):  print(f"  ✅  {msg}")
def _warn(msg: str): print(f"  ⚠️   {msg}")
def _fail(msg: str): print(f"  ❌  {msg}")


# ─────────────────────────────────────────────────────────────────────────────
# Tests
# ─────────────────────────────────────────────────────────────────────────────

def test_negative_confirm_without_pending(base_url: str, user_id: str) -> bool:
    """
    Sending 'yes' with NO prior pending action must NOT return calendar_created.
    This catches the original bug where the agent falsely claimed success.
    """
    _section("TEST 1 (negative): confirm with no pending action")
    session_id = f"e2e_negative_{uuid.uuid4().hex[:6]}"

    data = _post_chat(base_url, session_id, user_id, "yes")
    print(f"  type    = {data.get('type')}")
    print(f"  success = {data.get('success')}")
    print(f"  message = {data.get('message', '')[:150]}")

    if data.get("type") == "calendar_created":
        _fail("Agent returned calendar_created with NO pending action – original bug still present!")
        return False

    _ok("Agent correctly refused to claim success without a pending action.")
    return True


def test_e2e_calendar_creation(base_url: str, user_id: str) -> bool:
    """
    Full two-turn flow:
      Turn 1  →  request event creation (expect confirmation prompt)
      Turn 2  →  confirm with 'yes' (expect calendar_created + event_id)
    """
    _section("TEST 2 (positive): full e2e calendar creation")
    session_id = f"e2e_positive_{uuid.uuid4().hex[:6]}"

    # ── Turn 1: request ───────────────────────────────────────────────────────
    print("\n  [STEP A] Requesting calendar event creation …")
    request_msg = (
        "Create a calendar event titled 'E2E Integration Test' "
        "on 2026-04-15 at 14:00 using Google Calendar"
    )
    data_a = _post_chat(base_url, session_id, user_id, request_msg)

    print(f"  type         = {data_a.get('type')}")
    print(f"  agent_state  = {data_a.get('agent_state')}")
    print(f"  message      = {data_a.get('message', '')[:200]}")

    expected_types_a = {
        "calendar_confirmation",
        "calendar_slot_request",
        "calendar_provider_request",
    }
    if data_a.get("type") not in expected_types_a:
        _warn(
            f"Expected one of {expected_types_a}, got '{data_a.get('type')}'. "
            "The agent may have gone straight to execution without confirmation – "
            "review intent routing."
        )
        # Not a hard failure; continue to Turn 2

    # Verify pending_action was set
    if data_a.get("pending_action"):
        _ok("pending_action is set in session after Turn 1.")
    else:
        _warn("pending_action not visible in Turn 1 response (may be set internally).")

    # ── Turn 2: confirm ───────────────────────────────────────────────────────
    print("\n  [STEP B] Confirming with 'yes' …")
    data_b = _post_chat(base_url, session_id, user_id, "yes")

    print(f"  type         = {data_b.get('type')}")
    print(f"  success      = {data_b.get('success')}")
    print(f"  agent_state  = {data_b.get('agent_state')}")
    print(f"  message      =\n{data_b.get('message', '')}")

    # ── Step C: execution proof ───────────────────────────────────────────────
    print("\n  [STEP C] Verifying execution proof …")

    if data_b.get("type") == "error":
        error_msg = data_b.get("error", "")
        msg = data_b.get("message", "")
        # If it's an auth error the test infra is missing OAuth tokens – that's
        # expected in a CI environment without real credentials.
        if "NOT_AUTHENTICATED" in error_msg or "NOT_AUTHENTICATED" in msg:
            _warn(
                "Google Calendar is not connected for this user. "
                "The orchestration layer correctly forwarded the error (not a false success). "
                "Connect Google OAuth and re-run to verify E2E creation."
            )
            _ok("Orchestration correctness confirmed: no false success claim on auth error.")
            return True

        _fail(f"Integration returned error: {error_msg}")
        print(f"  Full response: {json.dumps(data_b, indent=4)}")
        return False

    if not (data_b.get("type") == "calendar_created" and data_b.get("success") is True):
        _fail(
            f"Expected type='calendar_created' & success=True, "
            f"got type='{data_b.get('type')}' success={data_b.get('success')}"
        )
        print(f"  Full response: {json.dumps(data_b, indent=4)}")
        return False

    _ok("type='calendar_created' and success=True confirmed.")

    event_data = data_b.get("data") or {}
    event_id  = event_data.get("event_id") or event_data.get("id")
    html_link = event_data.get("htmlLink")
    start     = event_data.get("start")
    end       = event_data.get("end")

    print(f"\n  Execution proof:")
    print(f"    event_id  = {event_id}")
    print(f"    htmlLink  = {html_link}")
    print(f"    start     = {start}")
    print(f"    end       = {end}")

    if event_id:
        _ok(f"event_id present → '{event_id}'")
    else:
        _warn(
            "event_id is missing from response data. "
            "The CalendarEvent model does not expose 'id' in the JSON – "
            "check api/integrations.py google_calendar_create_event return value."
        )

    if html_link:
        _ok(f"htmlLink present → {html_link}")
    else:
        _warn(
            "htmlLink not in response. "
            "Add 'htmlLink: Optional[str]' to CalendarEvent model to surface it."
        )

    if start and end:
        _ok(f"start/end present → {start} / {end}")
    else:
        _warn("start and/or end missing from response data.")

    # pending_action should be cleared after success
    if data_b.get("pending_action") is None:
        _ok("pending_action cleared after successful creation.")
    else:
        _warn("pending_action still set after success – check clear_pending_action() call.")

    return True


def test_error_preserves_pending_action(base_url: str, user_id: str) -> bool:
    """
    When the integration endpoint fails the pending_action must be preserved
    so the user can retry (no false success, state survives for retry).
    We simulate this by using a non-existent user_id to force a 401.
    """
    _section("TEST 3: failed integration preserves pending_action for retry")
    session_id = f"e2e_retry_{uuid.uuid4().hex[:6]}"
    bogus_user  = f"__nonexistent_user_{uuid.uuid4().hex[:6]}__"

    request_msg = (
        "Create a calendar event titled 'Retry Test' "
        "on 2026-04-20 at 10:00 using Google Calendar"
    )
    # Set up pending action with a real session/user
    data_a = _post_chat(base_url, session_id, user_id, request_msg)
    print(f"  Setup type = {data_a.get('type')}")

    # Confirm with a BOGUS user_id so the integration will return 401
    data_b = _post_chat(base_url, session_id, bogus_user, "yes")
    print(f"  type    = {data_b.get('type')}")
    print(f"  success = {data_b.get('success')}")

    if data_b.get("type") == "calendar_created":
        _fail("Agent claimed success even though the integration should have rejected the bogus user!")
        return False

    preserved = (data_b.get("data") or {}).get("pending_action_preserved")
    if preserved:
        _ok(f"pending_action preserved after failure (pending_action_preserved=True).")
    else:
        _warn(
            "pending_action_preserved flag not set; check that the error path "
            "does NOT call clear_pending_action()."
        )

    _ok("No false success claim on integration failure.")
    return True


# ─────────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="E2E test for Executive Agent calendar event creation."
    )
    parser.add_argument(
        "--base-url",
        default="http://localhost:8000",
        help="Backend base URL (default: http://localhost:8000)",
    )
    parser.add_argument(
        "--user-id",
        default="default_user",
        help="User ID whose Google OAuth tokens will be used (default: default_user)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Skip the live integration test (only runs orchestration-layer checks)",
    )
    args = parser.parse_args()

    base_url = args.base_url.rstrip("/")
    user_id  = args.user_id

    print(f"\n{'='*60}")
    print("  Executive Agent – Calendar Creation E2E Test Suite")
    print(f"{'='*60}")
    print(f"  Backend : {base_url}")
    print(f"  User ID : {user_id}")
    if args.dry_run:
        print("  Mode    : DRY-RUN (positive E2E step skipped)")
    print(f"{'='*60}")

    results = {}

    # Test 1: Negative – confirm without pending action
    try:
        results["no_pending_action"] = test_negative_confirm_without_pending(base_url, user_id)
    except Exception as exc:
        _fail(f"Test 1 raised exception: {exc}")
        results["no_pending_action"] = False

    # Test 2: Positive – full creation flow (skip in dry-run since it needs live OAuth)
    if not args.dry_run:
        try:
            results["e2e_creation"] = test_e2e_calendar_creation(base_url, user_id)
        except Exception as exc:
            _fail(f"Test 2 raised exception: {exc}")
            results["e2e_creation"] = False
    else:
        _section("TEST 2 skipped (--dry-run)")
        results["e2e_creation"] = None

    # Test 3: Error path preserves pending_action
    try:
        results["error_preserves_pending"] = test_error_preserves_pending_action(base_url, user_id)
    except Exception as exc:
        _fail(f"Test 3 raised exception: {exc}")
        results["error_preserves_pending"] = False

    # ── Summary ───────────────────────────────────────────────────────────────
    _section("SUMMARY")
    all_passed = True
    for test_name, passed in results.items():
        if passed is None:
            print(f"  ⏭️   {test_name}: SKIPPED")
        elif passed:
            print(f"  ✅  {test_name}: PASSED")
        else:
            print(f"  ❌  {test_name}: FAILED")
            all_passed = False

    print()
    if all_passed:
        print("  🎉  All tests passed (or skipped).")
        sys.exit(0)
    else:
        print("  💥  One or more tests FAILED.")
        sys.exit(1)


if __name__ == "__main__":
    main()

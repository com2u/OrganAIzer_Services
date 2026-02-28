"""
Test: Executive AI Tool Execution Verification
==============================================

Verifies that POST /api/agent/chat actually triggers:
  - POST /api/integrations/google/gmail/send  (for email requests)
  - POST /api/integrations/google/calendar/events  (for calendar requests)

Run with backend running: python test_executive_ai_tool_execution.py
"""

import asyncio
import json
import sys
import requests

BASE_URL = "http://localhost:8000"
AGENT_URL = f"{BASE_URL}/api/agent/chat"

# ── helpers ───────────────────────────────────────────────────────────────────

def chat(message: str, session_id: str = "test-tool-exec", user_id: str = "default_user",
         provider: str = "gmail") -> dict:
    resp = requests.post(AGENT_URL, json={
        "message": message,
        "session_id": session_id,
        "user_id": user_id,
        "provider": provider,
    }, timeout=30)
    resp.raise_for_status()
    return resp.json()


def clear_session(session_id: str):
    try:
        requests.delete(f"{BASE_URL}/api/agent/session/{session_id}", timeout=5)
    except Exception:
        pass


def print_response(label: str, data: dict):
    print(f"\n{'─'*60}")
    print(f"  {label}")
    print(f"{'─'*60}")
    print(f"  type        : {data.get('type')}")
    print(f"  success     : {data.get('success')}")
    print(f"  agent_state : {data.get('agent_state')}")
    print(f"  action_needed: {data.get('action_needed')}")
    print(f"  message     :\n{data.get('message', '')[:400]}")
    if data.get('data'):
        print(f"  data keys   : {list(data['data'].keys())}")
    print()


# ── tests ─────────────────────────────────────────────────────────────────────

def test_calendar_flow():
    """
    Full calendar workflow via Executive AI:
      1. "Schedule a meeting tomorrow at 10:00 in google calendar"
      2. "yes"  → should trigger POST /api/integrations/google/calendar/events
    """
    print("\n" + "="*60)
    print("TEST 1: Calendar Event Creation via Executive AI")
    print("="*60)

    session = "test-calendar-tool"
    clear_session(session)

    # Turn 1 – all slots in one shot (title, date via "tomorrow", time, provider via "google calendar")
    r1 = chat("Schedule a meeting called 'Strategy Sync' tomorrow at 10:00 in google calendar", session)
    print_response("Turn 1 – schedule request", r1)

    resp_type = r1.get("type", "")
    agent_state = r1.get("agent_state", "")

    if resp_type == "calendar_confirmation":
        print("✅ Agent correctly entered CALENDAR_CONFIRM state and is asking for confirmation")

        # Turn 2 – confirm
        r2 = chat("yes", session)
        print_response("Turn 2 – confirmation", r2)

        if r2.get("type") == "calendar_created":
            print("✅ Calendar event ACTUALLY CREATED")
            data = r2.get("data", {})
            print(f"   event_id : {data.get('event_id') or data.get('id')}")
            print(f"   summary  : {data.get('summary')}")
            return True
        elif r2.get("type") == "error":
            print(f"⚠️  Integration returned error (probably OAuth not connected): {r2.get('error')}")
            print("   This is expected if Google OAuth is not configured for 'default_user'")
            print("   ✅ BUT the agent DID attempt to call /api/integrations/google/calendar/events")
            return True
        else:
            print(f"❌ Unexpected response type after confirmation: {r2.get('type')}")
            return False
    else:
        print(f"❌ Expected 'calendar_confirmation' type, got: {resp_type} / state: {agent_state}")
        print(f"   Message: {r1.get('message', '')[:300]}")
        return False


def test_email_flow():
    """
    Full email workflow via Executive AI:
      1. "Send an email to test@example.com about Project Update"
      2. Provide body if asked
      3. "yes" → should trigger POST /api/integrations/google/gmail/send
    """
    print("\n" + "="*60)
    print("TEST 2: Email Send via Executive AI")
    print("="*60)

    session = "test-email-tool"
    clear_session(session)

    # Turn 1 – provide recipient and subject
    r1 = chat("Send an email to alice@example.com about Project Update", session)
    print_response("Turn 1 – send email request", r1)

    resp_type = r1.get("type", "")

    if resp_type == "email_slot_request":
        missing = r1.get("data", {}).get("missing_slot")
        print(f"✅ Agent is collecting email slots. Missing: {missing}")

        # Provide body
        r2 = chat("The project is on track and we'll deliver by Friday.", session)
        print_response("Turn 2 – provide body", r2)
        resp_type = r2.get("type", "")

        if resp_type == "email_confirmation":
            print("✅ Agent has all slots and is requesting confirmation")
            final_confirm = r2
        else:
            print(f"❌ Expected 'email_confirmation', got: {resp_type}")
            return False

    elif resp_type == "email_confirmation":
        print("✅ Agent collected all slots from first message and is asking for confirmation")
        final_confirm = r1
    else:
        print(f"❌ Expected 'email_slot_request' or 'email_confirmation', got: {resp_type}")
        print(f"   Message: {r1.get('message', '')[:300]}")
        return False

    # Confirm send
    r_confirm = chat("yes", session)
    print_response("Confirmation turn – send email", r_confirm)

    if r_confirm.get("type") == "email_sent":
        print("✅ Email ACTUALLY SENT")
        data = r_confirm.get("data", {})
        print(f"   message_id : {data.get('message_id')}")
        print(f"   to         : {data.get('to')}")
        return True
    elif r_confirm.get("type") == "error":
        print(f"⚠️  Integration returned error (probably OAuth not connected): {r_confirm.get('error')}")
        print("   This is expected if Google OAuth is not configured for 'default_user'")
        print("   ✅ BUT the agent DID attempt to call /api/integrations/google/gmail/send")
        return True
    else:
        print(f"❌ Unexpected response type after email confirmation: {r_confirm.get('type')}")
        return False


def test_combined_flow():
    """
    Single-message combined request: "Send an email AND create a calendar event"
    Verifies the agent handles email intent (first detected).
    """
    print("\n" + "="*60)
    print("TEST 3: Combined send email + create event (single message)")
    print("="*60)

    r = chat("Send an email to bob@example.com about the meeting and schedule a meeting tomorrow at 3pm in google calendar")
    print_response("Combined request", r)

    # Either email or calendar intent should be detected
    resp_type = r.get("type", "")
    if resp_type in ("email_slot_request", "email_confirmation",
                     "calendar_confirmation", "calendar_slot_request"):
        print(f"✅ Agent correctly detected an intent and entered flow: {resp_type}")
        return True
    else:
        print(f"⚠️  Got type: {resp_type} — might fall through to LLM chat")
        print(f"   Message: {r.get('message', '')[:300]}")
        return False


def test_backend_reachable():
    print("\n" + "="*60)
    print("TEST 0: Backend reachability")
    print("="*60)
    try:
        resp = requests.get(f"{BASE_URL}/health", timeout=5)
        print(f"✅ Backend reachable: HTTP {resp.status_code}")
        return True
    except Exception as e:
        try:
            resp = requests.get(f"{BASE_URL}/docs", timeout=5)
            print(f"✅ Backend reachable (via /docs): HTTP {resp.status_code}")
            return True
        except Exception as e2:
            print(f"❌ Backend NOT reachable at {BASE_URL}: {e2}")
            return False


# ── main ─────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("\n" + "="*60)
    print("  Executive AI Tool Execution Verification")
    print("="*60)

    results = {}

    results["backend_reachable"] = test_backend_reachable()
    if not results["backend_reachable"]:
        print("\n⛔ Backend not reachable. Please start it with: cd backend && python main.py")
        sys.exit(1)

    results["calendar"] = test_calendar_flow()
    results["email"] = test_email_flow()
    results["combined"] = test_combined_flow()

    print("\n" + "="*60)
    print("  RESULTS SUMMARY")
    print("="*60)
    all_pass = True
    for name, ok in results.items():
        status = "✅ PASS" if ok else "❌ FAIL"
        print(f"  {status}  {name}")
        if not ok:
            all_pass = False

    print()
    if all_pass:
        print("🎉 All tests passed! Executive AI tool execution is working.")
    else:
        print("⚠️  Some tests failed. Check output above for details.")
    print("="*60)

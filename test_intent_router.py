"""
Acceptance Tests for Intent Router + Slot-Aware Routing

Tests all scenarios from the task specification:
1. Calendar optional decline ("no thank you" for reminders)
2. Calendar attendees ("no one" for attendees)
3. Email sender selection ("gmail" not appended to body)
4. Sentence slot extraction (multiple details in one message)
5. Confirmation binding ("yes" executes pending action)
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))

from utils.intent_router import IntentRouter, IntentType
from utils.slot_extraction import SlotExtractor


def test_calendar_optional_decline():
    """
    TEST 1: Calendar optional decline
    
    User adds event, agent asks about reminders, user says "no thank you"
    Expected: DECLINE_OPTIONAL, NOT cancel action
    """
    print("\n" + "="*70)
    print("TEST 1: Calendar Optional Decline")
    print("="*70)
    
    # Scenario: User is creating calendar event, agent asks about reminders
    active_task = {
        "type": "calendar_event",
        "status": "collecting",
        "data": {
            "title": "Test5",
            "date": "2024-12-26",
            "time": "08:30",
            "state": "CAL_COLLECTING"
        }
    }
    
    pending_action = {
        "type": "create_calendar_event",
        "status": "collecting_details",
        "data": active_task["data"]
    }
    
    # Agent just asked: "Would you like to add reminders?"
    last_question = "optional_reminders"
    
    # User replies: "no thank you"
    message = "no thank you"
    
    result = IntentRouter.route_message(
        message,
        active_task,
        pending_action,
        last_question
    )
    
    print(f"Input: '{message}'")
    print(f"Context: Agent asked about {last_question}")
    print(f"Intent Type: {result['intent_type']}")
    print(f"Reasoning: {result['reasoning']}")
    
    # ASSERTIONS
    assert result['intent_type'] == IntentType.DECLINE_OPTIONAL, \
        f"Expected DECLINE_OPTIONAL, got {result['intent_type']}"
    
    print("✅ PASS: 'no thank you' correctly classified as DECLINE_OPTIONAL")
    print("   Task will continue with reminders=[]")
    return True


def test_calendar_no_attendees():
    """
    TEST 2: Calendar "no one" for attendees
    
    Agent asks "Who to invite?", user says "no one"
    Expected: DECLINE_OPTIONAL, attendees=[]
    """
    print("\n" + "="*70)
    print("TEST 2: Calendar 'No One' for Attendees")
    print("="*70)
    
    active_task = {
        "type": "calendar_event",
        "status": "collecting",
        "data": {
            "title": "Team Meeting",
            "date": "2024-12-26",
            "time": "10:00",
            "state": "CAL_COLLECTING"
        }
    }
    
    pending_action = {
        "type": "create_calendar_event",
        "status": "collecting_details",
        "data": active_task["data"]
    }
    
    # Agent asked: "Who would you like to invite?"
    last_question = "optional_attendees"
    
    message = "no one"
    
    result = IntentRouter.route_message(
        message,
        active_task,
        pending_action,
        last_question
    )
    
    print(f"Input: '{message}'")
    print(f"Context: Agent asked about {last_question}")
    print(f"Intent Type: {result['intent_type']}")
    print(f"Reasoning: {result['reasoning']}")
    
    assert result['intent_type'] == IntentType.DECLINE_OPTIONAL, \
        f"Expected DECLINE_OPTIONAL, got {result['intent_type']}"
    
    print("✅ PASS: 'no one' correctly classified as DECLINE_OPTIONAL")
    print("   Task will continue with attendees=[]")
    return True


def test_email_sender_selection():
    """
    TEST 3: Email sender selection
    
    Agent asks "Which account?", user says "gmail"
    Expected: SELECT_SENDER_ACCOUNT with provider=gmail
    NOT appended to email body
    """
    print("\n" + "="*70)
    print("TEST 3: Email Sender Selection")
    print("="*70)
    
    active_task = {
        "type": "send_email",
        "status": "awaiting_confirmation",
        "data": {
            "to_email": "test@example.com",
            "subject": "Test Subject",
            "body": "Test message",
            "state": "EMAIL_SELECT_SENDER"  # CRITICAL state
        }
    }
    
    pending_action = {
        "type": "send_email",
        "status": "awaiting_confirmation",
        "data": active_task["data"]
    }
    
    message = "gmail"
    
    result = IntentRouter.route_message(
        message,
        active_task,
        pending_action,
        None
    )
    
    print(f"Input: '{message}'")
    print(f"Context: State is EMAIL_SELECT_SENDER")
    print(f"Intent Type: {result['intent_type']}")
    print(f"Extracted Slots: {result['extracted_slots']}")
    print(f"Reasoning: {result['reasoning']}")
    
    assert result['intent_type'] == IntentType.SELECT_SENDER_ACCOUNT, \
        f"Expected SELECT_SENDER_ACCOUNT, got {result['intent_type']}"
    assert result['extracted_slots'].get('provider') == 'gmail', \
        f"Expected provider=gmail, got {result['extracted_slots']}"
    
    print("✅ PASS: 'gmail' correctly classified as SELECT_SENDER_ACCOUNT")
    print("   Will set sender_account=gmail, NOT append to body")
    return True


def test_sentence_slot_extraction():
    """
    TEST 4: Multi-slot extraction from sentence
    
    User: "Meeting with Chef tomorrow at 08:00 in Google calendar"
    Expected: Extract title, date, time, provider in ONE pass
    FORBIDDEN: Re-asking for title
    """
    print("\n" + "="*70)
    print("TEST 4: Multi-Slot Extraction from Single Sentence")
    print("="*70)
    
    message = "Meeting with Chef tomorrow at 08:00 in Google calendar"
    
    # No active task yet - this is initial message
    extracted = SlotExtractor.extract_calendar_slots(message, {})
    
    print(f"Input: '{message}'")
    print(f"Extracted Slots:")
    for key, value in extracted.items():
        print(f"  - {key}: {value}")
    
    # ASSERTIONS
    assert 'title' in extracted, "Should extract title"
    assert 'Meeting' in extracted['title'], f"Expected title with 'Meeting', got {extracted.get('title')}"
    
    assert 'time' in extracted, "Should extract time"
    assert extracted['time'] == '08:00', f"Expected time=08:00, got {extracted.get('time')}"
    
    assert 'date' in extracted, "Should extract date"
    # Date will be tomorrow's date in YYYY-MM-DD format
    
    assert 'provider' in extracted, "Should extract provider"
    assert extracted['provider'] == 'google', f"Expected provider=google, got {extracted.get('provider')}"
    
    print("✅ PASS: All slots extracted from single sentence")
    print("   Agent should NOT re-ask for title or other extracted fields")
    return True


def test_confirmation_binding():
    """
    TEST 5: Confirmation binding
    
    After showing draft/summary, user says "yes"
    Expected: CONFIRM_ACTION, executes pending action
    NOT "no pending actions"
    """
    print("\n" + "="*70)
    print("TEST 5: Confirmation Binding")
    print("="*70)
    
    # Scenario: Email draft ready, awaiting confirmation
    active_task = {
        "type": "send_email",
        "status": "awaiting_confirmation",
        "data": {
            "to_email": "test@example.com",
            "subject": "Test",
            "body": "Test message",
            "state": "EMAIL_DRAFT_READY"
        }
    }
    
    pending_action = {
        "type": "send_email",
        "status": "awaiting_confirmation",  # CRITICAL
        "data": active_task["data"]
    }
    
    message = "yes"
    
    result = IntentRouter.route_message(
        message,
        active_task,
        pending_action,
        None
    )
    
    print(f"Input: '{message}'")
    print(f"Context: pending_action with status='awaiting_confirmation'")
    print(f"Intent Type: {result['intent_type']}")
    print(f"Reasoning: {result['reasoning']}")
    
    assert result['intent_type'] == IntentType.CONFIRM_ACTION, \
        f"Expected CONFIRM_ACTION, got {result['intent_type']}"
    
    print("✅ PASS: 'yes' correctly classified as CONFIRM_ACTION")
    print("   Will execute pending_action (send email)")
    return True


def test_active_task_lock():
    """
    TEST 6: Active task lock prevents fallbacks
    
    During calendar creation, should NOT list events or say "no pending actions"
    """
    print("\n" + "="*70)
    print("TEST 6: Active Task Lock")
    print("="*70)
    
    active_task = {
        "type": "calendar_event",
        "status": "collecting",
        "data": {
            "title": "Meeting",
            "state": "CAL_COLLECTING"
        }
    }
    
    # Check if fallback should be prevented
    should_prevent = IntentRouter.should_prevent_fallback(active_task)
    
    print(f"Active Task: {active_task['type']} (status: {active_task['status']})")
    print(f"Should Prevent Fallback: {should_prevent}")
    
    assert should_prevent == True, "Should prevent fallback during active task"
    
    print("✅ PASS: Active task lock prevents fallback responses")
    print("   Agent will NOT list events or say 'no pending actions'")
    return True


def test_cancel_vs_decline():
    """
    TEST 7: Distinguish cancel from decline
    
    "cancel" → CANCEL_ACTION (stop everything)
    "no" (when asked about optional) → DECLINE_OPTIONAL (continue task)
    """
    print("\n" + "="*70)
    print("TEST 7: Cancel vs Decline Distinction")
    print("="*70)
    
    active_task = {
        "type": "calendar_event",
        "status": "collecting",
        "data": {"title": "Test", "state": "CAL_COLLECTING"}
    }
    
    # Test "cancel"
    result_cancel = IntentRouter.route_message(
        "cancel",
        active_task,
        None,
        None
    )
    
    print(f"Input: 'cancel'")
    print(f"Intent: {result_cancel['intent_type']}")
    assert result_cancel['intent_type'] == IntentType.CANCEL_ACTION
    print("✅ 'cancel' → CANCEL_ACTION")
    
    # Test "no" with optional context
    result_decline = IntentRouter.route_message(
        "no",
        active_task,
        None,
        "optional_reminders"
    )
    
    print(f"\nInput: 'no' (context: optional_reminders)")
    print(f"Intent: {result_decline['intent_type']}")
    assert result_decline['intent_type'] == IntentType.DECLINE_OPTIONAL
    print("✅ 'no' (optional context) → DECLINE_OPTIONAL")
    
    return True


def test_provider_not_in_body():
    """
    TEST 8: Provider selection in correct state
    
    Ensure "gmail" is treated as provider ONLY in EMAIL_SELECT_SENDER state
    In other states, it might be part of message content
    """
    print("\n" + "="*70)
    print("TEST 8: Provider Selection State-Awareness")
    print("="*70)
    
    # Test 1: In EMAIL_SELECT_SENDER state → SELECT_SENDER_ACCOUNT
    active_task_selecting = {
        "type": "send_email",
        "status": "awaiting_confirmation",
        "data": {
            "state": "EMAIL_SELECT_SENDER",
            "to_email": "test@example.com",
            "body": "Test"
        }
    }
    
    result1 = IntentRouter.route_message(
        "gmail",
        active_task_selecting,
        None,
        None
    )
    
    print(f"State: EMAIL_SELECT_SENDER, Input: 'gmail'")
    print(f"Intent: {result1['intent_type']}")
    assert result1['intent_type'] == IntentType.SELECT_SENDER_ACCOUNT
    print("✅ Correctly identified as SELECT_SENDER_ACCOUNT")
    
    # Test 2: In EMAIL_COLLECTING state → might be slot value
    active_task_collecting = {
        "type": "send_email",
        "status": "collecting",
        "data": {
            "state": "EMAIL_COLLECTING",
            "to_email": "test@example.com"
        }
    }
    
    result2 = IntentRouter.route_message(
        "send it from my gmail account",
        active_task_collecting,
        None,
        None
    )
    
    print(f"\nState: EMAIL_COLLECTING, Input: 'send it from my gmail account'")
    print(f"Intent: {result2['intent_type']}")
    # Should NOT be SELECT_SENDER_ACCOUNT (that's the key point)
    assert result2['intent_type'] != IntentType.SELECT_SENDER_ACCOUNT
    print("✅ Correctly NOT identified as SELECT_SENDER_ACCOUNT")
    print(f"   (Classified as {result2['intent_type']} instead)")
    
    return True


def run_all_tests():
    """Run all acceptance tests."""
    print("\n" + "="*70)
    print("INTENT ROUTER + SLOT-AWARE ROUTING - ACCEPTANCE TESTS")
    print("="*70)
    
    tests = [
        ("Calendar Optional Decline", test_calendar_optional_decline),
        ("Calendar No Attendees", test_calendar_no_attendees),
        ("Email Sender Selection", test_email_sender_selection),
        ("Sentence Slot Extraction", test_sentence_slot_extraction),
        ("Confirmation Binding", test_confirmation_binding),
        ("Active Task Lock", test_active_task_lock),
        ("Cancel vs Decline", test_cancel_vs_decline),
        ("Provider State-Awareness", test_provider_not_in_body),
    ]
    
    results = []
    
    for test_name, test_func in tests:
        try:
            success = test_func()
            results.append((test_name, True, None))
        except AssertionError as e:
            print(f"\n❌ FAIL: {test_name}")
            print(f"   Error: {str(e)}")
            results.append((test_name, False, str(e)))
        except Exception as e:
            print(f"\n❌ ERROR: {test_name}")
            print(f"   Error: {str(e)}")
            results.append((test_name, False, str(e)))
    
    # Summary
    print("\n" + "="*70)
    print("TEST SUMMARY")
    print("="*70)
    
    passed = sum(1 for _, success, _ in results if success)
    total = len(results)
    
    for test_name, success, error in results:
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"{status}: {test_name}")
        if error:
            print(f"       {error}")
    
    print(f"\nTotal: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n🎉 ALL ACCEPTANCE TESTS PASSED!")
        return True
    else:
        print(f"\n⚠️  {total - passed} test(s) failed")
        return False


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)

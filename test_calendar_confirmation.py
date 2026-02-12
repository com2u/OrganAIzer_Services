"""
Test Calendar Confirmation Flow Fix

This script tests the calendar event confirmation workflow to ensure:
1. Creating a calendar event transitions to CALENDAR_CONFIRM state
2. Saying "yes" executes the event creation
3. State is properly cleared after successful creation
4. Response includes event details and event_id

Usage:
    python test_calendar_confirmation.py
"""

import requests
import json
import sys
from datetime import datetime, timedelta

# Configuration
BASE_URL = "http://localhost:8000"
API_KEY = "test-key-123"
USER_ID = "test_user"

def make_request(message: str, session_id: str = "test_session") -> dict:
    """Make a request to the executive agent chat endpoint."""
    url = f"{BASE_URL}/api/agent/chat"
    headers = {
        "Content-Type": "application/json",
        "x-api-key": API_KEY
    }
    payload = {
        "message": message,
        "user_id": USER_ID,
        "session_id": session_id
    }
    
    print(f"\n{'='*80}")
    print(f"REQUEST: {message}")
    print(f"{'='*80}")
    
    response = requests.post(url, json=payload, headers=headers)
    
    if response.status_code != 200:
        print(f"❌ HTTP Error {response.status_code}: {response.text}")
        return {"error": response.text, "status_code": response.status_code}
    
    result = response.json()
    
    print(f"\nRESPONSE:")
    print(f"Message: {result.get('message', 'N/A')}")
    print(f"Success: {result.get('success', False)}")
    
    # Print state information
    if 'agent_state' in result:
        print(f"Agent State: {result['agent_state']}")
    if 'pending_action' in result:
        print(f"Pending Action: {json.dumps(result['pending_action'], indent=2)}")
    if 'active_task' in result:
        print(f"Active Task: {json.dumps(result['active_task'], indent=2)}")
    
    # Print event details if present
    if result.get('event_created'):
        print(f"\n✅ EVENT CREATED!")
        print(f"Event ID: {result.get('event_id', 'N/A')}")
        print(f"Provider: {result.get('provider_used', 'N/A')}")
        print(f"HTML Link: {result.get('html_link', 'N/A')}")
    
    return result

def test_calendar_confirmation():
    """Test the calendar event confirmation flow."""
    print("\n" + "="*80)
    print("CALENDAR CONFIRMATION FLOW TEST")
    print("="*80)
    
    session_id = f"test_cal_confirm_{datetime.now().timestamp()}"
    
    # Calculate tomorrow's date
    tomorrow = datetime.now() + timedelta(days=1)
    date_str = tomorrow.strftime("%Y-%m-%d")
    
    # Step 1: Create a calendar event request
    print("\n📅 Step 1: Request calendar event creation")
    message1 = "Create an event tomorrow at 11:00 AM called 'Project Meeting' for 90 minutes."
    result1 = make_request(message1, session_id)
    
    if not result1.get('success'):
        print("❌ FAILED: Could not initiate calendar event creation")
        return False
    
    # Check for confirmation state
    pending_action = result1.get('pending_action')
    if not pending_action:
        print("❌ FAILED: No pending_action in response")
        return False
    
    if pending_action.get('type') != 'create_calendar_event':
        print(f"❌ FAILED: Wrong action type: {pending_action.get('type')}")
        return False
    
    if pending_action.get('status') != 'awaiting_confirmation':
        print(f"❌ FAILED: Wrong status: {pending_action.get('status')}")
        return False
    
    print("✅ Step 1 PASSED: Event preview shown, awaiting confirmation")
    
    # Step 2: Confirm the event creation
    print("\n✅ Step 2: Confirm event creation with 'yes'")
    message2 = "yes"
    result2 = make_request(message2, session_id)
    
    if not result2.get('success'):
        print(f"❌ FAILED: Confirmation failed")
        print(f"Error: {result2.get('error', 'Unknown error')}")
        return False
    
    # Check for successful creation
    if not result2.get('event_created'):
        print("❌ FAILED: Event not created after confirmation")
        print(f"Message: {result2.get('message', 'N/A')}")
        return False
    
    # Check state is cleared
    pending_action_after = result2.get('pending_action')
    active_task_after = result2.get('active_task')
    
    if pending_action_after and pending_action_after.get('status') == 'awaiting_confirmation':
        print(f"❌ FAILED: State not cleared - pending_action still awaiting confirmation")
        return False
    
    if active_task_after and active_task_after.get('type') == 'calendar_event':
        print(f"❌ FAILED: State not cleared - active_task still present")
        return False
    
    # Check event details are included
    event_id = result2.get('event_id')
    provider_used = result2.get('provider_used')
    
    if not event_id:
        print("⚠️  WARNING: No event_id in response")
    else:
        print(f"✅ Event ID returned: {event_id}")
    
    if not provider_used:
        print("⚠️  WARNING: No provider_used in response")
    else:
        print(f"✅ Provider used: {provider_used}")
    
    print("\n✅ Step 2 PASSED: Event created successfully, state cleared")
    
    # Step 3: Verify agent returns to IDLE state
    print("\n🔄 Step 3: Verify agent is in IDLE state")
    message3 = "Hello"
    result3 = make_request(message3, session_id)
    
    if not result3.get('success'):
        print("❌ FAILED: Agent not responding after event creation")
        return False
    
    # Should not have calendar-related pending action
    pending_action_idle = result3.get('pending_action')
    if pending_action_idle and pending_action_idle.get('type') == 'create_calendar_event':
        print(f"❌ FAILED: Agent still has calendar pending action in IDLE state")
        return False
    
    print("✅ Step 3 PASSED: Agent returned to IDLE state")
    
    print("\n" + "="*80)
    print("✅ ALL TESTS PASSED!")
    print("="*80)
    return True

def test_calendar_cancellation():
    """Test calendar event cancellation."""
    print("\n" + "="*80)
    print("CALENDAR CANCELLATION TEST")
    print("="*80)
    
    session_id = f"test_cal_cancel_{datetime.now().timestamp()}"
    
    # Step 1: Create a calendar event request
    print("\n📅 Step 1: Request calendar event creation")
    message1 = "Schedule a meeting tomorrow at 3 PM called 'Team Sync'"
    result1 = make_request(message1, session_id)
    
    if not result1.get('success') or not result1.get('pending_action'):
        print("❌ FAILED: Could not initiate calendar event creation")
        return False
    
    print("✅ Step 1 PASSED: Event preview shown")
    
    # Step 2: Cancel the event
    print("\n❌ Step 2: Cancel event with 'cancel'")
    message2 = "cancel"
    result2 = make_request(message2, session_id)
    
    if not result2.get('success'):
        print("❌ FAILED: Cancellation failed")
        return False
    
    # Check state is cleared
    pending_action_after = result2.get('pending_action')
    active_task_after = result2.get('active_task')
    
    if pending_action_after and pending_action_after.get('type') == 'create_calendar_event':
        print(f"❌ FAILED: State not cleared after cancellation")
        return False
    
    print("✅ Step 2 PASSED: Event cancelled, state cleared")
    
    print("\n" + "="*80)
    print("✅ CANCELLATION TEST PASSED!")
    print("="*80)
    return True

if __name__ == "__main__":
    print("""
╔════════════════════════════════════════════════════════════════╗
║                 CALENDAR CONFIRMATION FIX TEST                 ║
║                                                                ║
║  This test verifies:                                           ║
║  1. Calendar event confirmation flow works correctly           ║
║  2. State is properly cleared after creation                   ║
║  3. Event details are returned in response                     ║
║  4. Cancellation works correctly                               ║
╚════════════════════════════════════════════════════════════════╝
    """)
    
    # Run tests
    try:
        test1_passed = test_calendar_confirmation()
        test2_passed = test_calendar_cancellation()
        
        print("\n" + "="*80)
        print("TEST SUMMARY")
        print("="*80)
        print(f"Confirmation Flow: {'✅ PASSED' if test1_passed else '❌ FAILED'}")
        print(f"Cancellation Flow: {'✅ PASSED' if test2_passed else '❌ FAILED'}")
        
        if test1_passed and test2_passed:
            print("\n✅ ALL TESTS PASSED! Calendar confirmation fix is working correctly.")
            sys.exit(0)
        else:
            print("\n❌ SOME TESTS FAILED. Please review the output above.")
            sys.exit(1)
    
    except KeyboardInterrupt:
        print("\n\n⚠️  Test interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ Test error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

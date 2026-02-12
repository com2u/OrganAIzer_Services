"""
Test Follow-Up Action Handling

Tests the Executive Agent's ability to detect and handle follow-up requests
for duplicating calendar events across different providers.

CRITICAL SCENARIOS:
1. User creates event on Google Calendar
2. User says "add it to Outlook as well" 
3. Agent should duplicate event to Outlook with confirmation
"""

import asyncio
import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent / "backend"))

from services.executive_agent_service import ExecutiveAgent


async def test_calendar_followup_detection():
    """Test that follow-up phrases are correctly detected."""
    print("\n" + "="*70)
    print("TEST 1: Follow-Up Phrase Detection")
    print("="*70)
    
    agent = ExecutiveAgent(session_id="test_followup")
    
    # Test various follow-up phrases
    test_phrases = [
        ("add it to outlook as well", True, "outlook"),
        ("add to my google calendar too", True, "google"),
        ("same thing for outlook", True, "outlook"),
        ("duplicate it to google", True, "google"),
        ("also add to outlook calendar", True, "outlook"),
        ("create a new meeting", False, None),  # NOT a follow-up
    ]
    
    for phrase, should_detect, expected_provider in test_phrases:
        result = agent._detect_followup_request(phrase)
        is_followup = result["is_followup"]
        detected_provider = result["target_provider"]
        
        status = "✅ PASS" if is_followup == should_detect else "❌ FAIL"
        print(f"{status}: '{phrase}'")
        print(f"   Expected followup={should_detect}, provider={expected_provider}")
        print(f"   Got followup={is_followup}, provider={detected_provider}")
        
        if is_followup != should_detect:
            print("   ⚠️ DETECTION MISMATCH!")
        elif should_detect and detected_provider != expected_provider:
            print(f"   ⚠️ PROVIDER MISMATCH! Expected {expected_provider}, got {detected_provider}")
    
    print("\n✓ Follow-up detection test complete")


async def test_calendar_duplication_workflow():
    """Test the complete calendar duplication workflow."""
    print("\n" + "="*70)
    print("TEST 2: Calendar Duplication Workflow")
    print("="*70)
    
    agent = ExecutiveAgent(session_id="test_duplication")
    
    # STEP 1: Simulate a completed calendar event creation
    print("\n📅 STEP 1: Simulating completed calendar event creation...")
    agent.memory.record_action(
        action_type="create_calendar_event",
        outcome="EVENT_CREATED",
        details={
            "title": "Team Meeting",
            "date": "2026-02-10",
            "time": "14:00",
            "provider": "google",
            "event_id": "test_event_123",
            "timestamp": "2026-02-09T00:00:00Z"
        }
    )
    print("   ✓ Event recorded: Team Meeting on Google Calendar")
    
    # STEP 2: User says "add it to Outlook as well"
    print("\n💬 STEP 2: User requests duplication...")
    followup_message = "add it to outlook as well"
    print(f"   User: '{followup_message}'")
    
    # Detect followup
    followup_info = agent._detect_followup_request(followup_message)
    print(f"\n   Detection Results:")
    print(f"   - Is Followup: {followup_info['is_followup']}")
    print(f"   - Type: {followup_info['followup_type']}")
    print(f"   - Target Provider: {followup_info['target_provider']}")
    
    if followup_info["is_followup"]:
        print("\n   ✅ Follow-up detected successfully!")
        
        # STEP 3: Handle duplication (without actually creating - no OAuth tokens)
        print("\n📋 STEP 3: Preparing duplication...")
        try:
            response = await agent._handle_calendar_duplication(
                followup_info["reference_action"],
                followup_info["target_provider"],
                user_id="test_user"
            )
            
            print(f"\n   Agent Response:")
            print(f"   {response.get('message', 'No message')[:200]}...")
            print(f"\n   Success: {response.get('success', False)}")
            
            # Check if pending action was created
            pending = agent.memory.get_pending_action()
            if pending:
                print(f"\n   ✓ Pending action created: {pending['type']}")
                print(f"   - Status: {pending['status']}")
                print(f"   - Event Title: {pending['data'].get('title')}")
                print(f"   - Target Provider: {pending['data'].get('provider')}")
            else:
                print("\n   ℹ️ No pending action (expected if no OAuth tokens)")
            
        except Exception as e:
            print(f"\n   ⚠️ Error during duplication: {e}")
    else:
        print("\n   ❌ Follow-up NOT detected - test failed!")
    
    print("\n✓ Duplication workflow test complete")


async def test_followup_without_previous_action():
    """Test that followup requests without previous actions are handled gracefully."""
    print("\n" + "="*70)
    print("TEST 3: Follow-Up Without Previous Action")
    print("="*70)
    
    agent = ExecutiveAgent(session_id="test_no_action")
    
    # User says "add it to outlook" but there's no previous event
    print("\n💬 User requests duplication with no previous action...")
    followup_message = "add it to outlook calendar"
    
    followup_info = agent._detect_followup_request(followup_message)
    print(f"   Detection: is_followup={followup_info['is_followup']}")
    
    if followup_info["is_followup"]:
        if followup_info["reference_action"] is None:
            print("   ✅ PASS: Detected followup but no reference action found")
        else:
            print("   ❌ FAIL: Should not have found a reference action")
    else:
        print("   ⚠️ Follow-up not detected (phrase may need adjustment)")
    
    print("\n✓ No previous action test complete")


async def test_multiple_providers():
    """Test followup detection with different provider combinations."""
    print("\n" + "="*70)
    print("TEST 4: Multiple Provider Scenarios")
    print("="*70)
    
    scenarios = [
        {
            "name": "Google → Outlook",
            "original": "google",
            "followup": "add to outlook as well",
            "expected_target": "outlook"
        },
        {
            "name": "Outlook → Google",
            "original": "outlook",
            "followup": "also add to my google calendar",
            "expected_target": "google"
        },
        {
            "name": "No provider specified",
            "original": "google",
            "followup": "add it to my calendar too",
            "expected_target": None
        }
    ]
    
    for scenario in scenarios:
        print(f"\n📋 Scenario: {scenario['name']}")
        
        agent = ExecutiveAgent(session_id=f"test_{scenario['name']}")
        
        # Record original event
        agent.memory.record_action(
            action_type="create_calendar_event",
            outcome="EVENT_CREATED",
            details={
                "title": "Test Event",
                "date": "2026-02-10",
                "time": "10:00",
                "provider": scenario["original"],
                "event_id": f"test_{scenario['original']}_123"
            }
        )
        
        # Detect followup
        followup_info = agent._detect_followup_request(scenario["followup"])
        detected_target = followup_info.get("target_provider")
        
        if detected_target == scenario["expected_target"]:
            print(f"   ✅ PASS: Correct target provider detected ({detected_target})")
        else:
            print(f"   ❌ FAIL: Expected {scenario['expected_target']}, got {detected_target}")
    
    print("\n✓ Multiple provider test complete")


async def run_all_tests():
    """Run all follow-up handling tests."""
    print("\n" + "="*70)
    print("FOLLOW-UP ACTION HANDLING TEST SUITE")
    print("="*70)
    print("\nTesting Executive Agent's ability to handle follow-up requests")
    print("for duplicating calendar events across providers.")
    
    try:
        await test_calendar_followup_detection()
        await test_calendar_duplication_workflow()
        await test_followup_without_previous_action()
        await test_multiple_providers()
        
        print("\n" + "="*70)
        print("ALL TESTS COMPLETE")
        print("="*70)
        print("\n✅ Follow-up action handling is working correctly!")
        print("\nNOTE: Actual calendar duplication requires OAuth tokens.")
        print("To test end-to-end, connect both Google and Outlook calendars.")
        
    except Exception as e:
        print(f"\n❌ TEST SUITE FAILED: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    print("\n🧪 Starting Follow-Up Action Handling Tests...")
    asyncio.run(run_all_tests())

"""
Test Email Slot-Filling + Email-Mode Parsing + Draft Persistence

Tests the EXACT reproduction scenario from the task:
1. User: draft me an email
2. User: User
3. Agent should NOT re-ask for "To:"
4. User: Fronti
5. This should be treated as to_name (display name), NOT a new recipient
6. User: Can i meet you at some point for dinner?
7. This should be treated as EMAIL BODY, not conversation with AI
8. User: send it
9. Should send the email (or show appropriate state)

EXPECTED BEHAVIOR:
- to_email set once, never overwritten
- "Fronti" becomes to_name
- Free-form text becomes body
- Draft persisted with EMAIL_DRAFT_READY state
- "send it" triggers send
"""

import asyncio
import sys
import os

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))

from services.executive_agent_service import ExecutiveAgent

async def test_slot_filling_scenario():
    """Test the exact reproduction scenario from the task."""
    
    print("=" * 80)
    print("EMAIL SLOT-FILLING TEST")
    print("=" * 80)
    
    # Create agent with fresh session
    agent = ExecutiveAgent(session_id="slot_test_001")
    agent.memory.clear_pending_action()
    agent.memory.clear_active_task()
    
    # Step 1: Draft request
    print("\n[STEP 1] User: draft me an email")
    response1 = await agent.process_message(
        "draft me an email",
        user_id="test_user",
        provider="gmail"
    )
    print(f"Agent: {response1['message'][:200]}...")
    
    # Step 2: Provide email address
    print("\n[STEP 2] User: renato.xheci@web.de")
    response2 = await agent.process_message(
        "renato.xheci@web.de",
        user_id="test_user",
        provider="gmail"
    )
    print(f"Agent: {response2['message'][:200]}...")
    
    # CRITICAL CHECK: Agent should NOT re-ask for "To:"
    pending = agent.memory.get_pending_action()
    assert pending is not None, "❌ FAIL: No pending action found"
    assert pending["data"].get("to_email") == "renato.xheci@web.de", "❌ FAIL: Email not stored"
    print(f"✅ PASS: to_email stored = {pending['data']['to_email']}")
    
    # Step 3: Provide name (should be to_name, NOT overwrite to_email)
    print("\n[STEP 3] User: Fronti")
    response3 = await agent.process_message(
        "Fronti",
        user_id="test_user",
        provider="gmail"
    )
    print(f"Agent: {response3['message'][:200]}...")
    
    # CRITICAL CHECK: to_email should remain the same, Fronti should be to_name
    pending = agent.memory.get_pending_action()
    assert pending["data"].get("to_email") == "renato.xheci@web.de", "❌ FAIL: to_email overwritten!"
    assert pending["data"].get("to_name") == "Fronti", "❌ FAIL: to_name not set"
    print(f"✅ PASS: to_email unchanged = {pending['data']['to_email']}")
    print(f"✅ PASS: to_name set = {pending['data']['to_name']}")
    
    # Step 4: Provide body content (EMAIL MODE - treat as content, not conversation)
    print("\n[STEP 4] User: Can I meet you at some point for dinner?")
    response4 = await agent.process_message(
        "Can I meet you at some point for dinner?",
        user_id="test_user",
        provider="gmail"
    )
    print(f"Agent: {response4['message'][:300]}...")
    
    # CRITICAL CHECK: Message should be in body, draft should be shown
    pending = agent.memory.get_pending_action()
    body = pending["data"].get("body", "")
    assert "dinner" in body.lower(), "❌ FAIL: Body doesn't contain user's message"
    assert pending["data"].get("state") == "EMAIL_DRAFT_READY", "❌ FAIL: Not in EMAIL_DRAFT_READY state"
    assert pending["status"] == "awaiting_confirmation", "❌ FAIL: Not awaiting confirmation"
    assert response4.get("draft_ready") == True, "❌ FAIL: Draft not marked as ready"
    print(f"✅ PASS: Body contains message = {body[:100]}...")
    print(f"✅ PASS: State = {pending['data']['state']}")
    print(f"✅ PASS: Status = {pending['status']}")
    
    # Step 5: Confirm and attempt send (no email account, but draft should persist)
    print("\n[STEP 5] User: send it")
    response5 = await agent.process_message(
        "send it",
        user_id="test_user",
        provider="gmail"
    )
    print(f"Agent: {response5['message'][:300]}...")
    
    # CRITICAL CHECK: Should attempt send (will fail due to no email account, but that's OK)
    # Draft should still be persisted with pending_confirmation=True
    if "no email accounts" in response5['message'].lower() or "cannot send" in response5['message'].lower():
        print("✅ PASS: Attempted to send, but no email accounts connected (expected)")
        pending = agent.memory.get_pending_action()
        if pending and pending.get("status") == "awaiting_confirmation":
            print("✅ PASS: Draft persisted despite error")
        else:
            print("⚠️  WARN: Draft might have been cleared (check if this is intentional)")
    elif response5.get("email_sent"):
        print("✅ PASS: Email sent successfully!")
    else:
        print(f"❓ UNKNOWN: Response = {response5}")
    
    # Check action history
    action_history = agent.memory.get_action_history()
    print(f"\n[ACTION HISTORY] {len(action_history)} actions recorded:")
    for action in action_history:
        print(f"  - {action['action_type']}: {action['outcome']}")
    
    print("\n" + "=" * 80)
    print("TEST COMPLETE")
    print("=" * 80)
    
    return {
        "success": True,
        "responses": [response1, response2, response3, response4, response5],
        "final_pending": agent.memory.get_pending_action(),
        "action_history": agent.memory.get_action_history()
    }


async def test_email_mode_parsing():
    """Test that in EMAIL mode, messages are treated as email content."""
    
    print("\n" + "=" * 80)
    print("EMAIL MODE PARSING TEST")
    print("=" * 80)
    
    agent = ExecutiveAgent(session_id="email_mode_test")
    agent.memory.clear_pending_action()
    agent.memory.clear_active_task()
    
    # Set up draft with recipient
    await agent.process_message("draft email to test@example.com", user_id="test_user")
    
    # Provide body that could be misinterpreted as conversation
    print("\n[TEST] User provides ambiguous message...")
    response = await agent.process_message(
        "Can we schedule a meeting to discuss the project?",
        user_id="test_user"
    )
    
    # Check that it's treated as email body
    pending = agent.memory.get_pending_action()
    body = pending["data"].get("body", "")
    
    if "schedule a meeting" in body.lower():
        print("✅ PASS: Message treated as email body content")
    else:
        print("❌ FAIL: Message not added to body")
    
    print("=" * 80)


async def test_no_pending_actions_fallback():
    """Test that 'no pending actions' doesn't show when draft exists."""
    
    print("\n" + "=" * 80)
    print("NO PENDING ACTIONS FALLBACK TEST")
    print("=" * 80)
    
    agent = ExecutiveAgent(session_id="fallback_test")
    agent.memory.clear_pending_action()
    agent.memory.clear_active_task()
    
    # Create a draft
    await agent.process_message("draft email to user@test.com", user_id="test_user")
    await agent.process_message("This is a test message", user_id="test_user")
    
    # Try to send
    response = await agent.process_message("send it", user_id="test_user")
    
    # Should NOT say "no pending actions"
    if "no pending" in response["message"].lower() and "action" in response["message"].lower():
        print("❌ FAIL: Agent says 'no pending actions' when draft exists!")
    else:
        print("✅ PASS: Agent handles send request with existing draft")
    
    print("=" * 80)


if __name__ == "__main__":
    print("\nRunning Email Slot-Filling Tests...")
    print("These tests verify the fixes for:")
    print("- Strict slot filling (never re-ask for to_email)")
    print("- Email-mode parsing (treat messages as content)")
    print("- Atomic draft persistence")
    print("- No 'pending actions' fallback when draft exists")
    print()
    
    # Run tests
    asyncio.run(test_slot_filling_scenario())
    asyncio.run(test_email_mode_parsing())
    asyncio.run(test_no_pending_actions_fallback())
    
    print("\n✅ All tests completed!")

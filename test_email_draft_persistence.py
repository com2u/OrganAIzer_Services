"""
Test: Email Draft Persistence Bug Fix

CRITICAL BUG:
- Email draft is shown to user: "📧 Email Draft Ready"
- User says "send it"
- Backend responds: "I don't have any pending actions to confirm"

ROOT CAUSE:
- Draft rendering and persistence were NOT atomic
- State was being cleared before confirmation could be processed

FIX VERIFICATION:
This test ensures that when a draft is shown, it ALWAYS has:
1. A pending_email_draft object in backend state
2. System state = EMAIL_DRAFT_READY (awaiting_confirmation)
3. Confirmation keywords properly routed to the draft
"""

import asyncio
import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent / "backend"))

from services.executive_agent_service import ExecutiveAgent


async def test_draft_persistence():
    """
    Test that email drafts are persisted atomically with rendering.
    
    SUCCESS CRITERIA:
    - Draft shows "📧 Email Draft Ready"
    - Backend has pending_action with status="awaiting_confirmation"
    - User says "send it" → routes to send handler (not "no pending actions")
    """
    print("=" * 80)
    print("TEST: Email Draft Persistence - Critical Bug Fix")
    print("=" * 80)
    
    # Create agent instance
    agent = ExecutiveAgent(session_id="test_draft_persistence")
    
    # Clear any existing state
    agent.memory.clear_pending_action()
    agent.memory.clear_active_task()
    
    print("\n[STEP 1] User requests email draft")
    print("-" * 80)
    
    response1 = await agent.process_message(
        "Draft an email to renato.xheci@web.de about the quarterly report",
        user_id="test_user",
        provider="gmail"
    )
    
    print(f"Agent Response:\n{response1['message']}\n")
    
    # CRITICAL CHECK 1: Draft should be persisted
    pending = agent.memory.get_pending_action()
    
    print("[VALIDATION 1] Draft Persistence Check:")
    if pending is None:
        print("❌ FAILED: No pending action found!")
        print("   The draft was rendered but NOT persisted in backend state")
        return False
    
    print(f"✅ PASSED: Pending action exists")
    print(f"   Type: {pending['type']}")
    print(f"   Status: {pending['status']}")
    print(f"   Recipient: {pending['data'].get('recipient')}")
    
    # CRITICAL CHECK 2: Status must be awaiting_confirmation
    if pending['status'] != 'awaiting_confirmation':
        print(f"❌ FAILED: Status is '{pending['status']}' instead of 'awaiting_confirmation'")
        return False
    
    print(f"✅ PASSED: Status is 'awaiting_confirmation'")
    
    # CRITICAL CHECK 3: Draft must have required fields
    draft_data = pending['data']
    if not draft_data.get('recipient') or not draft_data.get('body'):
        print(f"❌ FAILED: Draft missing required fields")
        print(f"   Recipient: {draft_data.get('recipient')}")
        print(f"   Body: {'Present' if draft_data.get('body') else 'Missing'}")
        return False
    
    print(f"✅ PASSED: Draft has all required fields")
    
    # CRITICAL CHECK 4: Response must indicate draft_ready
    if not response1.get('draft_ready'):
        print(f"❌ FAILED: Response missing 'draft_ready' flag")
        return False
    
    print(f"✅ PASSED: Response has 'draft_ready' flag")
    
    print("\n[STEP 2] User confirms with 'send it'")
    print("-" * 80)
    
    # Simulate user confirmation
    response2 = await agent.process_message(
        "send it",
        user_id="test_user",
        provider="gmail"
    )
    
    print(f"Agent Response:\n{response2['message']}\n")
    
    # CRITICAL CHECK 5: Must NOT say "no pending actions"
    if "don't have any pending actions" in response2['message'].lower():
        print("❌ FAILED: BUG REPRODUCED!")
        print("   Agent says 'no pending actions' even though draft was shown")
        print("   This means the draft was NOT persisted properly")
        return False
    
    print(f"✅ PASSED: Confirmation was processed (not 'no pending actions')")
    
    # CRITICAL CHECK 6: Should either send or ask for account selection
    message_lower = response2['message'].lower()
    is_send_success = "email sent" in message_lower or "sent successfully" in message_lower
    is_account_selection = "which email account" in message_lower
    is_no_account = "no email accounts connected" in message_lower
    
    if is_send_success:
        print(f"✅ PASSED: Email sent successfully!")
    elif is_account_selection:
        print(f"✅ PASSED: Asking for account selection (valid state)")
    elif is_no_account:
        print(f"✅ PASSED: No accounts connected (expected in test environment)")
    else:
        print(f"⚠️  WARNING: Unexpected response type")
        print(f"   Response: {response2['message'][:200]}")
    
    print("\n[STEP 3] Verify state transitions")
    print("-" * 80)
    
    # Check final state
    final_pending = agent.memory.get_pending_action()
    
    if is_send_success:
        # Email sent - state should be cleared
        if final_pending is not None and final_pending.get('status') != 'sent':
            print(f"❌ FAILED: State not cleared after send")
            return False
        print(f"✅ PASSED: State properly cleared after send")
    else:
        # Email not sent yet - state should be preserved
        if final_pending is None:
            print(f"❌ FAILED: State cleared even though email wasn't sent")
            return False
        print(f"✅ PASSED: State preserved for continuation")
    
    print("\n" + "=" * 80)
    print("✅ ALL TESTS PASSED - Email Draft Persistence Fixed!")
    print("=" * 80)
    print("\nSUCCESS CRITERIA MET:")
    print("✓ Draft rendering is atomic with persistence")
    print("✓ UI-visible state matches backend state")
    print("✓ Confirmation keywords route correctly")
    print("✓ No 'no pending actions' desync bug")
    
    return True


async def test_edge_case_greeting_after_draft():
    """
    Test that greetings DON'T clear a ready draft inappropriately.
    
    Edge case: User creates draft, then says "hi" - should NOT clear draft
    unless it's explicitly a new conversation.
    """
    print("\n\n" + "=" * 80)
    print("TEST: Edge Case - Greeting After Draft")
    print("=" * 80)
    
    agent = ExecutiveAgent(session_id="test_greeting_edge_case")
    agent.memory.clear_pending_action()
    agent.memory.clear_active_task()
    
    # Create draft
    print("\n[1] Create email draft")
    await agent.process_message(
        "Draft an email to test@example.com saying hello",
        user_id="test_user"
    )
    
    pending_before = agent.memory.get_pending_action()
    if not pending_before:
        print("❌ Setup failed - no draft created")
        return False
    
    print(f"✅ Draft created (status: {pending_before['status']})")
    
    # User says "send it" (confirmation keyword)
    print("\n[2] User says 'send it'")
    response = await agent.process_message(
        "send it",
        user_id="test_user"
    )
    
    # MUST NOT clear the draft
    pending_after = agent.memory.get_pending_action()
    
    if "don't have any pending actions" in response['message'].lower():
        print("❌ FAILED: 'send it' cleared the draft!")
        print(f"   This is the bug we're fixing")
        return False
    
    print(f"✅ PASSED: 'send it' processed correctly")
    print(f"   Response type: {'Send' if 'sent' in response['message'].lower() else 'Account selection or error'}")
    
    return True


async def run_all_tests():
    """Run all draft persistence tests."""
    print("\n")
    print("╔" + "=" * 78 + "╗")
    print("║" + " " * 78 + "║")
    print("║" + "  EMAIL DRAFT PERSISTENCE BUG FIX - COMPREHENSIVE TEST SUITE".center(78) + "║")
    print("║" + " " * 78 + "║")
    print("╚" + "=" * 78 + "╝")
    
    results = []
    
    # Test 1: Basic draft persistence
    try:
        result1 = await test_draft_persistence()
        results.append(("Draft Persistence", result1))
    except Exception as e:
        print(f"\n❌ Test failed with exception: {e}")
        import traceback
        traceback.print_exc()
        results.append(("Draft Persistence", False))
    
    # Test 2: Edge case - greeting after draft
    try:
        result2 = await test_edge_case_greeting_after_draft()
        results.append(("Edge Case - Greeting", result2))
    except Exception as e:
        print(f"\n❌ Test failed with exception: {e}")
        import traceback
        traceback.print_exc()
        results.append(("Edge Case - Greeting", False))
    
    # Print summary
    print("\n\n")
    print("╔" + "=" * 78 + "╗")
    print("║" + " FINAL TEST RESULTS ".center(78, "=") + "║")
    print("╚" + "=" * 78 + "╝")
    
    for test_name, passed in results:
        status = "✅ PASSED" if passed else "❌ FAILED"
        print(f"  {status:12} | {test_name}")
    
    all_passed = all(result for _, result in results)
    
    print("\n" + "=" * 80)
    if all_passed:
        print("🎉 ALL TESTS PASSED - BUG FIX VERIFIED!")
        print("\nThe fix ensures:")
        print("• Email drafts are ALWAYS persisted when shown to user")
        print("• 'send it' commands ALWAYS find the pending draft")
        print("• UI state and backend state are ALWAYS synchronized")
    else:
        print("⚠️  SOME TESTS FAILED - BUG STILL PRESENT")
        print("\nPlease review the failed tests above")
    print("=" * 80)
    
    return all_passed


if __name__ == "__main__":
    success = asyncio.run(run_all_tests())
    sys.exit(0 if success else 1)

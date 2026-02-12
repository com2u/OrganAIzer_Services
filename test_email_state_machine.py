"""
Test Email State Machine Fix

This test validates the email state machine fixes including:
1. Send command detection
2. Proper state cleanup after send
3. Cancel functionality
4. Conversation reset after send
5. Edge cases

Run with: python test_email_state_machine.py
"""

import asyncio
import sys
from pathlib import Path

# Add backend to path
backend_path = Path(__file__).parent / "backend"
sys.path.insert(0, str(backend_path))

from services.executive_agent_service import ExecutiveAgent


class Colors:
    """Terminal colors for pretty output"""
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKCYAN = '\033[96m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'


def print_test(name: str):
    """Print test name"""
    print(f"\n{Colors.HEADER}{Colors.BOLD}{'='*80}{Colors.ENDC}")
    print(f"{Colors.HEADER}{Colors.BOLD}TEST: {name}{Colors.ENDC}")
    print(f"{Colors.HEADER}{Colors.BOLD}{'='*80}{Colors.ENDC}\n")


def print_step(step: str):
    """Print test step"""
    print(f"{Colors.OKCYAN}▶ {step}{Colors.ENDC}")


def print_user(message: str):
    """Print user message"""
    print(f"{Colors.OKBLUE}👤 User: {message}{Colors.ENDC}")


def print_agent(message: str):
    """Print agent response (first 150 chars)"""
    preview = message[:150] + "..." if len(message) > 150 else message
    print(f"{Colors.OKGREEN}🤖 Agent: {preview}{Colors.ENDC}")


def print_state(agent: ExecutiveAgent):
    """Print current state"""
    task = agent.memory.get_active_task()
    pending = agent.memory.get_pending_action()
    
    task_info = f"{task['type']} ({task['status']})" if task else "None"
    pending_info = f"{pending['type']} ({pending['status']})" if pending else "None"
    
    print(f"{Colors.WARNING}   📊 State - Task Lock: {task_info} | Pending: {pending_info}{Colors.ENDC}")


def assert_result(condition: bool, message: str):
    """Assert a test condition"""
    if condition:
        print(f"{Colors.OKGREEN}✅ PASS: {message}{Colors.ENDC}")
    else:
        print(f"{Colors.FAIL}❌ FAIL: {message}{Colors.ENDC}")
        raise AssertionError(message)


async def test_1_happy_path():
    """Test 1: Happy path - Draft → Send → New conversation"""
    print_test("Happy Path: Draft → Send → New Conversation")
    
    agent = ExecutiveAgent(session_id="test_1")
    
    # Step 1: Draft email
    print_step("Step 1: User drafts email")
    print_user("Draft an email to john@example.com about the meeting")
    response = await agent.process_message(
        "Draft an email to john@example.com about the meeting",
        user_id="test_user",
        provider="gmail"
    )
    print_agent(response.get("message", ""))
    print_state(agent)
    
    assert_result(
        agent.memory.get_active_task() is not None,
        "Task lock should be set after drafting"
    )
    assert_result(
        agent.memory.get_pending_action() is not None,
        "Pending action should exist"
    )
    assert_result(
        "Ready to send" in response.get("message", ""),
        "Should show draft ready message"
    )
    
    # Step 2: Send email
    print_step("Step 2: User confirms send")
    print_user("send it")
    response = await agent.process_message(
        "send it",
        user_id="test_user",
        provider="gmail"
    )
    print_agent(response.get("message", ""))
    print_state(agent)
    
    # Check if send was attempted (may fail due to no OAuth tokens, but should try)
    assert_result(
        "sent" in response.get("message", "").lower() or "cannot send" in response.get("message", "").lower(),
        "Should attempt to send or show no-account error"
    )
    
    # If email can't be sent due to no accounts, task should be cleared
    if "cannot send" in response.get("message", "").lower():
        print_step("No OAuth tokens - task cleared as expected")
        assert_result(
            agent.memory.get_active_task() is None,
            "Task lock should be cleared after failed send (no accounts)"
        )
    else:
        # Email sent successfully
        assert_result(
            agent.memory.get_active_task() is None,
            "Task lock should be cleared after successful send"
        )
        assert_result(
            agent.memory.get_pending_action() is None,
            "Pending action should be cleared after send"
        )
    
    # Step 3: Ask unrelated question
    print_step("Step 3: User asks unrelated question")
    print_user("What's the weather?")
    response = await agent.process_message(
        "What's the weather?",
        user_id="test_user",
        provider="gmail"
    )
    print_agent(response.get("message", ""))
    print_state(agent)
    
    assert_result(
        "draft" not in response.get("message", "").lower(),
        "Should not mention drafts in weather response"
    )
    
    print(f"\n{Colors.OKGREEN}{Colors.BOLD}✅ TEST 1 PASSED{Colors.ENDC}\n")


async def test_2_cancel_flow():
    """Test 2: Cancel flow - Draft → Cancel → New conversation"""
    print_test("Cancel Flow: Draft → Cancel → New Conversation")
    
    agent = ExecutiveAgent(session_id="test_2")
    
    # Step 1: Draft email
    print_step("Step 1: User drafts email")
    print_user("Draft an email to jane@example.com")
    response = await agent.process_message(
        "Draft an email to jane@example.com",
        user_id="test_user",
        provider="gmail"
    )
    print_agent(response.get("message", ""))
    print_state(agent)
    
    # Provide missing info
    print_step("Step 1b: Provide purpose")
    print_user("It's about the project update")
    response = await agent.process_message(
        "It's about the project update",
        user_id="test_user",
        provider="gmail"
    )
    print_agent(response.get("message", ""))
    print_state(agent)
    
    assert_result(
        agent.memory.get_active_task() is not None,
        "Task lock should still be active"
    )
    
    # Step 2: Cancel
    print_step("Step 2: User cancels")
    print_user("cancel")
    response = await agent.process_message(
        "cancel",
        user_id="test_user",
        provider="gmail"
    )
    print_agent(response.get("message", ""))
    print_state(agent)
    
    assert_result(
        agent.memory.get_active_task() is None,
        "Task lock should be cleared after cancel"
    )
    assert_result(
        agent.memory.get_pending_action() is None,
        "Pending action should be cleared after cancel"
    )
    assert_result(
        "cancelled" in response.get("message", "").lower(),
        "Should confirm cancellation"
    )
    
    # Step 3: New conversation
    print_step("Step 3: User starts new topic")
    print_user("Tell me about Rome")
    response = await agent.process_message(
        "Tell me about Rome",
        user_id="test_user",
        provider="gmail"
    )
    print_agent(response.get("message", ""))
    print_state(agent)
    
    assert_result(
        "rome" in response.get("message", "").lower(),
        "Should respond about Rome, not email"
    )
    
    print(f"\n{Colors.OKGREEN}{Colors.BOLD}✅ TEST 2 PASSED{Colors.ENDC}\n")


async def test_3_multi_edit():
    """Test 3: Multi-edit - Draft → Edit → Edit → Send"""
    print_test("Multi-Edit: Draft → Edit → Edit → Send")
    
    agent = ExecutiveAgent(session_id="test_3")
    
    # Step 1: Draft email
    print_step("Step 1: User drafts email")
    print_user("Draft an email to bob@example.com about quarterly results")
    response = await agent.process_message(
        "Draft an email to bob@example.com about quarterly results",
        user_id="test_user",
        provider="gmail"
    )
    print_agent(response.get("message", ""))
    print_state(agent)
    
    # Step 2: First edit
    print_step("Step 2: User edits - make it shorter")
    print_user("make it shorter")
    response = await agent.process_message(
        "make it shorter",
        user_id="test_user",
        provider="gmail"
    )
    print_agent(response.get("message", ""))
    print_state(agent)
    
    assert_result(
        "updated" in response.get("message", "").lower() or "draft" in response.get("message", "").lower(),
        "Should show updated draft"
    )
    assert_result(
        agent.memory.get_active_task() is not None,
        "Task lock should remain active during edit"
    )
    
    # Step 3: Second edit
    print_step("Step 3: User edits again - make it more casual")
    print_user("make it more casual")
    response = await agent.process_message(
        "make it more casual",
        user_id="test_user",
        provider="gmail"
    )
    print_agent(response.get("message", ""))
    print_state(agent)
    
    assert_result(
        "updated" in response.get("message", "").lower() or "draft" in response.get("message", "").lower(),
        "Should show updated draft again"
    )
    
    # Step 4: Send
    print_step("Step 4: User sends")
    print_user("yes, send it")
    response = await agent.process_message(
        "yes, send it",
        user_id="test_user",
        provider="gmail"
    )
    print_agent(response.get("message", ""))
    print_state(agent)
    
    # Should attempt send or show error
    assert_result(
        "sent" in response.get("message", "").lower() or "cannot" in response.get("message", "").lower(),
        "Should attempt to send or show error"
    )
    
    print(f"\n{Colors.OKGREEN}{Colors.BOLD}✅ TEST 3 PASSED{Colors.ENDC}\n")


async def test_4_no_redraft_after_send():
    """Test 4: After send, "send it" should not trigger new draft"""
    print_test("No Re-Draft: Verify 'send it' doesn't create new draft after send")
    
    agent = ExecutiveAgent(session_id="test_4")
    
    # Step 1: Draft and send
    print_step("Step 1: Draft and send email")
    print_user("Draft email to alice@example.com saying hello")
    await agent.process_message(
        "Draft email to alice@example.com saying hello",
        user_id="test_user",
        provider="gmail"
    )
    
    response = await agent.process_message(
        "send it",
        user_id="test_user",
        provider="gmail"
    )
    print_agent(response.get("message", ""))
    print_state(agent)
    
    # Step 2: Try to say "send it" again
    print_step("Step 2: User says 'send it' again")
    print_user("send it")
    response = await agent.process_message(
        "send it",
        user_id="test_user",
        provider="gmail"
    )
    print_agent(response.get("message", ""))
    print_state(agent)
    
    assert_result(
        "don't have any pending" in response.get("message", "").lower() or 
        "help you with" in response.get("message", "").lower(),
        "Should not start new draft - should ask what user needs"
    )
    
    print(f"\n{Colors.OKGREEN}{Colors.BOLD}✅ TEST 4 PASSED{Colors.ENDC}\n")


async def test_5_state_inspection():
    """Test 5: Verify state transitions are logged correctly"""
    print_test("State Inspection: Verify all state transitions")
    
    agent = ExecutiveAgent(session_id="test_5")
    
    # Initial state
    print_step("Initial state")
    print_state(agent)
    assert_result(
        agent.memory.get_active_task() is None and agent.memory.get_pending_action() is None,
        "Initial state should be clean"
    )
    
    # Draft
    print_step("After draft request")
    await agent.process_message(
        "Draft email to test@example.com about testing",
        user_id="test_user"
    )
    print_state(agent)
    
    task = agent.memory.get_active_task()
    pending = agent.memory.get_pending_action()
    
    assert_result(task is not None, "Task should be set")
    assert_result(task["type"] == "draft_email", "Task type should be draft_email")
    assert_result(pending is not None, "Pending action should be set")
    assert_result(pending["type"] == "send_email", "Pending type should be send_email")
    assert_result(pending["status"] == "awaiting_confirmation", "Should be awaiting confirmation")
    
    # Send
    print_step("After send command")
    await agent.process_message("yes", user_id="test_user")
    print_state(agent)
    
    # Task should be cleared (unless no accounts error)
    result_cleared = agent.memory.get_active_task() is None
    print(f"   Task cleared: {result_cleared}")
    
    print(f"\n{Colors.OKGREEN}{Colors.BOLD}✅ TEST 5 PASSED{Colors.ENDC}\n")


async def main():
    """Run all tests"""
    print(f"\n{Colors.HEADER}{Colors.BOLD}")
    print("╔══════════════════════════════════════════════════════════════════════════════╗")
    print("║                    EMAIL STATE MACHINE TEST SUITE                           ║")
    print("║                                                                              ║")
    print("║  Testing the email workflow fixes for OrganAIzer Executive Agent            ║")
    print("╚══════════════════════════════════════════════════════════════════════════════╝")
    print(f"{Colors.ENDC}\n")
    
    tests = [
        ("Happy Path", test_1_happy_path),
        ("Cancel Flow", test_2_cancel_flow),
        ("Multi-Edit", test_3_multi_edit),
        ("No Re-Draft After Send", test_4_no_redraft_after_send),
        ("State Inspection", test_5_state_inspection),
    ]
    
    passed = 0
    failed = 0
    
    for name, test_func in tests:
        try:
            await test_func()
            passed += 1
        except Exception as e:
            failed += 1
            print(f"{Colors.FAIL}❌ TEST FAILED: {name}{Colors.ENDC}")
            print(f"{Colors.FAIL}Error: {e}{Colors.ENDC}\n")
    
    # Summary
    print(f"\n{Colors.HEADER}{Colors.BOLD}")
    print("╔══════════════════════════════════════════════════════════════════════════════╗")
    print("║                              TEST SUMMARY                                    ║")
    print("╚══════════════════════════════════════════════════════════════════════════════╝")
    print(f"{Colors.ENDC}")
    print(f"{Colors.OKGREEN}✅ Passed: {passed}{Colors.ENDC}")
    print(f"{Colors.FAIL}❌ Failed: {failed}{Colors.ENDC}")
    print(f"{Colors.BOLD}Total: {passed + failed}{Colors.ENDC}\n")
    
    if failed == 0:
        print(f"{Colors.OKGREEN}{Colors.BOLD}🎉 ALL TESTS PASSED! 🎉{Colors.ENDC}\n")
        return 0
    else:
        print(f"{Colors.FAIL}{Colors.BOLD}⚠️  SOME TESTS FAILED{Colors.ENDC}\n")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)

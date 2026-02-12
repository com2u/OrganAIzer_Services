"""
Test Suite for Calendar Intent Normalization

Tests the CRITICAL implementation of:
1. CALENDAR_CREATE intent normalization
2. EVENT vs PERSONAL_NOTE type detection
3. Task persistence rules (NON-NEGOTIABLE)
4. Semantic slot extraction
5. Confirmation flow
6. Explicit cancel only

Run with: python test_calendar_intent_normalization.py
"""

import asyncio
import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent / "backend"))

from services.executive_agent_service import ExecutiveAgent
from utils.slot_extraction import SlotExtractor


class TestCalendarIntentNormalization:
    """Test calendar intent normalization implementation."""
    
    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.test_results = []
    
    def log(self, message: str, level: str = "INFO"):
        """Log test message."""
        prefix = {
            "INFO": "ℹ️",
            "PASS": "✅",
            "FAIL": "❌",
            "WARN": "⚠️"
        }.get(level, "•")
        print(f"{prefix} {message}")
    
    def assert_true(self, condition: bool, message: str):
        """Assert condition is true."""
        if condition:
            self.passed += 1
            self.log(f"PASS: {message}", "PASS")
            self.test_results.append(("PASS", message))
        else:
            self.failed += 1
            self.log(f"FAIL: {message}", "FAIL")
            self.test_results.append(("FAIL", message))
        return condition
    
    async def run_all_tests(self):
        """Run all test cases."""
        self.log("=" * 60)
        self.log("CALENDAR INTENT NORMALIZATION - TEST SUITE")
        self.log("=" * 60)
        
        await self.test_intent_normalization()
        await self.test_type_detection()
        await self.test_slot_extraction()
        await self.test_task_persistence()
        await self.test_confirmation_flow()
        await self.test_explicit_cancel()
        
        self.print_results()
    
    async def test_intent_normalization(self):
        """Test TC1: Intent normalization for CALENDAR_CREATE."""
        self.log("\n[TC1] Testing Intent Normalization...")
        
        agent = ExecutiveAgent(session_id="test_tc1")
        
        test_cases = [
            ("add to my calendar", "CALENDAR_CREATE"),
            ("add an event", "CALENDAR_CREATE"),
            ("note it down", "CALENDAR_CREATE"),
            ("just a note for myself", "CALENDAR_CREATE"),
            ("reminder for myself", "CALENDAR_CREATE"),
            ("schedule a meeting", "CALENDAR_CREATE"),
            ("appointment tomorrow", "CALENDAR_CREATE"),
        ]
        
        for message, expected_intent in test_cases:
            intent = await agent._analyze_intent(message)
            self.assert_true(
                intent.get("intent") == expected_intent,
                f"'{message}' → {expected_intent}"
            )
    
    async def test_type_detection(self):
        """Test TC2: EVENT vs PERSONAL_NOTE type detection."""
        self.log("\n[TC2] Testing Type Detection...")
        
        agent = ExecutiveAgent(session_id="test_tc2")
        
        # Personal note indicators
        personal_note_cases = [
            "note it down meeting with chef",
            "just a note for myself: call mom",
            "personal reminder to buy groceries",
            "reminder for myself about appointment"
        ]
        
        for message in personal_note_cases:
            intent = await agent._analyze_intent(message)
            self.assert_true(
                intent.get("calendar_type") == "PERSONAL_NOTE",
                f"'{message}' → PERSONAL_NOTE"
            )
        
        # Event cases (default)
        event_cases = [
            "schedule a meeting",
            "add event tomorrow",
            "appointment with dentist"
        ]
        
        for message in event_cases:
            intent = await agent._analyze_intent(message)
            self.assert_true(
                intent.get("calendar_type") == "EVENT",
                f"'{message}' → EVENT"
            )
    
    async def test_slot_extraction(self):
        """Test TC3: Semantic slot extraction."""
        self.log("\n[TC3] Testing Slot Extraction...")
        
        # Test comprehensive extraction
        message = "Meeting with Chef tomorrow at 08:00"
        slots = SlotExtractor.extract_calendar_slots(message)
        
        self.assert_true(
            "Meeting" in slots.get("title", ""),
            f"Title extracted from '{message}'"
        )
        self.assert_true(
            slots.get("time") == "08:00",
            f"Time '08:00' extracted from '{message}'"
        )
        self.assert_true(
            slots.get("date") is not None,
            f"Date extracted from '{message}'"
        )
        
        # Test time parsing
        time_tests = [
            ("meeting at 2pm", "14:00"),
            ("event at 09:30", "09:30"),
            ("call at 8:00", "08:00"),
        ]
        
        for msg, expected_time in time_tests:
            slots = SlotExtractor.extract_calendar_slots(msg)
            self.assert_true(
                slots.get("time") == expected_time,
                f"Time '{expected_time}' from '{msg}'"
            )
        
        # Test date parsing
        date_tests = [
            "meeting today",
            "event tomorrow",
            "call next week"
        ]
        
        for msg in date_tests:
            slots = SlotExtractor.extract_calendar_slots(msg)
            self.assert_true(
                slots.get("date") is not None,
                f"Date extracted from '{msg}'"
            )
    
    async def test_task_persistence(self):
        """Test TC4: Task persistence rules (CRITICAL)."""
        self.log("\n[TC4] Testing Task Persistence (NON-NEGOTIABLE)...")
        
        agent = ExecutiveAgent(session_id="test_tc4")
        
        # Start calendar creation
        response1 = await agent.process_message(
            "Schedule a meeting with chef",
            user_id="test_user"
        )
        
        # Verify active task is set
        active_task = agent.memory.get_active_task()
        self.assert_true(
            active_task is not None,
            "Active task created for calendar event"
        )
        self.assert_true(
            active_task.get("type") == "calendar_event",
            "Active task type is calendar_event"
        )
        
        # CRITICAL: Try to list events (should be FORBIDDEN)
        response2 = await agent.process_message(
            "Show my calendar",
            user_id="test_user"
        )
        
        # Task should STILL be active (not cleared)
        active_task_after = agent.memory.get_active_task()
        self.assert_true(
            active_task_after is not None,
            "FORBIDDEN: Task persistence maintained (did not switch to list events)"
        )
        
        # Agent should ask for missing slots, NOT list events
        self.assert_true(
            "event" in response2.get("message", "").lower() or 
            "when" in response2.get("message", "").lower() or
            "what" in response2.get("message", "").lower(),
            "Agent continues collecting slots instead of listing events"
        )
    
    async def test_confirmation_flow(self):
        """Test TC5: Confirmation flow format."""
        self.log("\n[TC5] Testing Confirmation Flow...")
        
        agent = ExecutiveAgent(session_id="test_tc5")
        
        # Simulate full slot filling
        agent.memory.set_active_task("calendar_event", status="collecting", data={})
        agent.memory.set_pending_action("create_calendar_event", {
            "title": "Meeting with Chef",
            "date": "2026-02-10",
            "time": "08:00",
            "duration": 30,
            "state": "CAL_COLLECTING",
            "type": "EVENT"
        }, status="collecting_details")
        
        # Trigger finalization
        response = await agent._finalize_calendar_event(
            agent.memory.get_pending_action()["data"],
            "test_user",
            "google"
        )
        
        message = response.get("message", "")
        
        # Verify confirmation format
        self.assert_true(
            "Type:" in message,
            "Confirmation includes Type field"
        )
        self.assert_true(
            "Title:" in message,
            "Confirmation includes Title field"
        )
        self.assert_true(
            "Date:" in message,
            "Confirmation includes Date field"
        )
        self.assert_true(
            "Time:" in message,
            "Confirmation includes Time field"
        )
        self.assert_true(
            "Create it?" in message or "yes / cancel" in message.lower(),
            "Confirmation includes prompt"
        )
        
        # Verify state transition
        pending = agent.memory.get_pending_action()
        self.assert_true(
            pending.get("data", {}).get("state") == "CAL_CONFIRM",
            "State transitioned to CAL_CONFIRM"
        )
    
    async def test_explicit_cancel(self):
        """Test TC6: Explicit cancel only."""
        self.log("\n[TC6] Testing Explicit Cancel...")
        
        agent = ExecutiveAgent(session_id="test_tc6")
        
        # Start calendar creation
        await agent.process_message("Schedule meeting", user_id="test_user")
        
        # Verify task is active
        self.assert_true(
            agent.memory.get_active_task() is not None,
            "Task active before cancel"
        )
        
        # Test cancel keywords
        cancel_keywords = ["cancel", "stop", "never mind", "abort"]
        
        for keyword in cancel_keywords:
            agent_test = ExecutiveAgent(session_id=f"test_tc6_{keyword}")
            await agent_test.process_message("Schedule meeting", user_id="test_user")
            
            response = await agent_test.process_message(keyword, user_id="test_user")
            
            self.assert_true(
                agent_test.memory.get_active_task() is None,
                f"Task cleared after '{keyword}'"
            )
            self.assert_true(
                "cancelled" in response.get("message", "").lower(),
                f"Confirmation message for '{keyword}'"
            )
    
    def print_results(self):
        """Print test results summary."""
        self.log("\n" + "=" * 60)
        self.log("TEST RESULTS SUMMARY")
        self.log("=" * 60)
        
        total = self.passed + self.failed
        pass_rate = (self.passed / total * 100) if total > 0 else 0
        
        self.log(f"Total Tests: {total}")
        self.log(f"Passed: {self.passed} ✅", "PASS")
        self.log(f"Failed: {self.failed} ❌", "FAIL" if self.failed > 0 else "INFO")
        self.log(f"Pass Rate: {pass_rate:.1f}%")
        
        if self.failed > 0:
            self.log("\nFailed Tests:")
            for status, message in self.test_results:
                if status == "FAIL":
                    self.log(f"  • {message}", "FAIL")
        
        self.log("=" * 60)
        
        if self.failed == 0:
            self.log("\n🎉 ALL TESTS PASSED! 🎉\n", "PASS")
        else:
            self.log(f"\n⚠️  {self.failed} TEST(S) FAILED ⚠️\n", "WARN")


async def main():
    """Run test suite."""
    test_suite = TestCalendarIntentNormalization()
    await test_suite.run_all_tests()
    
    # Exit with appropriate code
    sys.exit(0 if test_suite.failed == 0 else 1)


if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("CALENDAR INTENT NORMALIZATION - AUTOMATED TEST SUITE")
    print("=" * 60 + "\n")
    
    asyncio.run(main())

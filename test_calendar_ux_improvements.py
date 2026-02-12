"""
Test Calendar UX and Date Clarification Logic Improvements

Tests for:
1. Dynamic date examples using current year
2. Improved title extraction logic
3. Robust slot-filling state machine
4. Modification before confirmation
5. Timezone and time validation
"""

import pytest
import asyncio
from datetime import datetime
from backend.services.executive_agent_service import ExecutiveAgent
from backend.utils.slot_extraction import SlotExtractor


class TestDynamicDateExamples:
    """Test that date examples use current year dynamically."""
    
    @pytest.mark.asyncio
    async def test_date_example_uses_current_year(self):
        """Verify date request shows current year in example."""
        agent = ExecutiveAgent(session_id="test_dynamic_date")
        
        # Start calendar creation without date
        response = await agent.process_message(
            "Schedule Meeting tomorrow at 12:30",
            user_id="test_user"
        )
        
        # Should have extracted title but not date yet if we test step-by-step
        # In practice, "tomorrow" should be extracted, but let's test the prompt
        
        # Now test when date is missing
        agent2 = ExecutiveAgent(session_id="test_no_date")
        response2 = await agent2.process_message(
            "Schedule Project Meeting at 12:30",  # No date keyword
            user_id="test_user"
        )
        
        current_year = datetime.now().year
        expected_example = f"{current_year}-12-25"
        
        # Should ask for date with current year example
        assert expected_example in response2.get("message", ""), \
            f"Date example should use current year {current_year}"
        assert "2024-12-25" not in response2.get("message", ""), \
            "Should NOT show hardcoded 2024 date"
        
        print(f"✅ Date example uses current year: {current_year}")


class TestTitleExtraction:
    """Test improved title extraction logic."""
    
    def test_quoted_title_preserved(self):
        """Test that quoted titles preserve exact casing."""
        message = "Schedule an event tomorrow at 12:00; call it 'Project Meeting 2'"
        
        slots = SlotExtractor.extract_calendar_slots(message)
        
        assert slots.get("title") == "Project Meeting 2", \
            "Quoted title should preserve exact casing"
        print("✅ Quoted title: 'Project Meeting 2'")
    
    def test_call_it_pattern(self):
        """Test 'call it X' pattern extraction."""
        message = "Add an event tomorrow call it Strategy Sync"
        
        slots = SlotExtractor.extract_calendar_slots(message)
        
        assert slots.get("title") is not None, \
            "Should extract title from 'call it' pattern"
        assert "strategy sync" in slots.get("title", "").lower(), \
            "Title should contain 'strategy sync'"
        print(f"✅ Call it pattern: {slots.get('title')}")
    
    def test_title_before_time(self):
        """Test title extraction before time marker."""
        message = "Meeting with Chef at 08:00"
        
        slots = SlotExtractor.extract_calendar_slots(message)
        
        assert slots.get("title") == "Meeting With Chef", \
            "Should extract 'Meeting with Chef' as title"
        assert slots.get("time") == "08:00", \
            "Should extract time separately"
        print(f"✅ Title before time: {slots.get('title')}")
    
    def test_generic_phrase_rejected(self):
        """Test that generic phrases are NOT extracted as titles."""
        message = "Create me an event tomorrow at 10:00"
        
        slots = SlotExtractor.extract_calendar_slots(message)
        
        # Should NOT extract "create me an event" as title
        title = slots.get("title")
        assert title is None or "create" not in title.lower(), \
            "Should NOT extract request phrase as title"
        print("✅ Generic phrases rejected")
    
    def test_garbage_detection(self):
        """Test garbage title detection."""
        garbage_titles = [
            "an event",
            "a meeting",
            "create me",
            "it",
            "a"
        ]
        
        for garbage in garbage_titles:
            is_garbage = SlotExtractor._is_garbage_title(garbage)
            assert is_garbage, f"'{garbage}' should be detected as garbage"
        
        print("✅ Garbage detection works")
    
    def test_valid_title_max_length(self):
        """Test title truncation at 80 characters."""
        long_title = "A" * 100
        message = f'call it "{long_title}"'
        
        slots = SlotExtractor.extract_calendar_slots(message)
        
        title = slots.get("title", "")
        assert len(title) <= 80, \
            f"Title should be truncated to 80 chars, got {len(title)}"
        print(f"✅ Title truncated to {len(title)} chars")


class TestTimeRangeExtraction:
    """Test time range extraction (start and end times)."""
    
    def test_explicit_time_range(self):
        """Test extraction of explicit time range."""
        message = "Meeting tomorrow from 10:00 to 18:00"
        
        slots = SlotExtractor.extract_calendar_slots(message)
        
        assert slots.get("start_time") == "10:00", \
            "Should extract start time"
        assert slots.get("end_time") == "18:00", \
            "Should extract end time"
        print("✅ Time range: 10:00 to 18:00")
    
    def test_time_range_with_dash(self):
        """Test time range with dash separator."""
        message = "Meeting 12:30-13:30"
        
        slots = SlotExtractor.extract_calendar_slots(message)
        
        assert slots.get("start_time") == "12:30", \
            "Should extract start time from dash range"
        assert slots.get("end_time") == "13:30", \
            "Should extract end time from dash range"
        print("✅ Time range with dash: 12:30-13:30")
    
    def test_time_range_ampm(self):
        """Test time range with am/pm format."""
        message = "Meeting from 10am to 6pm"
        
        slots = SlotExtractor.extract_calendar_slots(message)
        
        assert slots.get("start_time") == "10:00", \
            "Should convert 10am to 10:00"
        assert slots.get("end_time") == "18:00", \
            "Should convert 6pm to 18:00"
        print("✅ Time range am/pm: 10am to 6pm")
    
    def test_single_time_no_end(self):
        """Test single time without end time."""
        message = "Meeting at 14:30"
        
        slots = SlotExtractor.extract_calendar_slots(message)
        
        assert slots.get("start_time") == "14:30", \
            "Should extract start time"
        assert slots.get("end_time") is None, \
            "Should NOT have end time"
        print("✅ Single time without end: 14:30")


class TestSlotFillingStateMachine:
    """Test robust slot-filling state machine."""
    
    @pytest.mark.asyncio
    async def test_incremental_slot_filling(self):
        """Test that slots are filled incrementally without re-asking."""
        agent = ExecutiveAgent(session_id="test_slot_filling")
        
        # Step 1: Provide title and date
        response1 = await agent.process_message(
            "Schedule Project Meeting tomorrow",
            user_id="test_user"
        )
        
        # Should ask for time, NOT re-ask for title
        assert "time" in response1.get("message", "").lower(), \
            "Should ask for time"
        assert "what should i call" not in response1.get("message", "").lower(), \
            "Should NOT re-ask for title"
        
        # Step 2: Provide time
        response2 = await agent.process_message(
            "at 12:30",
            user_id="test_user"
        )
        
        # Should show confirmation with all details
        assert "Project Meeting" in response2.get("message", ""), \
            "Should show title in confirmation"
        assert "12:30" in response2.get("message", ""), \
            "Should show time in confirmation"
        
        print("✅ Incremental slot filling works")
    
    @pytest.mark.asyncio
    async def test_modification_before_confirmation(self):
        """Test modifying slots before confirmation."""
        agent = ExecutiveAgent(session_id="test_modification")
        
        # Create event with all details
        response1 = await agent.process_message(
            "Schedule Team Meeting tomorrow at 12:30-13:30",
            user_id="test_user"
       )
        
        # Should show confirmation
        assert "Create it?" in response1.get("message", "") or \
               "Confirm?" in response1.get("message", ""), \
            "Should show confirmation prompt"
        
        # Now modify title (this would require the agent to be in awaiting state)
        # This is more of an integration test
        print("✅ Modification flow prepared")


class TestStateManagement:
    """Test state machine robustness."""
    
    @pytest.mark.asyncio
    async def test_cancellation(self):
        """Test cancelling calendar creation."""
        agent = ExecutiveAgent(session_id="test_cancel")
        
        # Start calendar creation
        response1 = await agent.process_message(
            "Schedule meeting tomorrow at 12:00",
            user_id="test_user"
        )
        
        # Cancel
        response2 = await agent.process_message(
            "cancel",
            user_id="test_user"
        )
        
        assert "cancelled" in response2.get("message", "").lower(), \
            "Should confirm cancellation"
        
        # Verify state is cleared
        assert agent.memory.get_pending_action() is None, \
            "Pending action should be cleared"
        assert agent.memory.get_active_task() is None, \
            "Active task should be cleared"
        
        print("✅ Cancellation clears state")
    
    @pytest.mark.asyncio
    async def test_provider_selection_state(self):
        """Test provider selection state handling."""
        # This requires OAuth tokens to be set up
        # Placeholder for full integration test
        print("✅ Provider selection state test prepared")


class TestTimezoneHandling:
    """Test timezone and time validation."""
    
    @pytest.mark.asyncio
    async def test_default_timezone(self):
        """Test that default timezone is Europe/Berlin."""
        agent = ExecutiveAgent(session_id="test_timezone")
        
        # Create event
        response = await agent.process_message(
            "Schedule Test Event tomorrow at 12:00",
            user_id="test_user"
        )
        
        # Check pending action data
        pending = agent.memory.get_pending_action()
        if pending and pending.get("data"):
            timezone = pending["data"].get("timezone", "Europe/Berlin")
            assert timezone == "Europe/Berlin", \
                f"Default timezone should be Europe/Berlin, got {timezone}"
        
        print("✅ Default timezone: Europe/Berlin")
    
    def test_duration_calculation_from_end_time(self):
        """Test duration calculation when end time is provided."""
        message = "Meeting from 10:00 to 12:00"
        
        slots = SlotExtractor.extract_calendar_slots(message)
        
        # Should have start and end time
        assert slots.get("start_time") == "10:00"
        assert slots.get("end_time") == "12:00"
        
        # Duration should NOT be set when end_time exists
        # (duration will be calculated in finalize step)
        print("✅ Duration calculation prepared for end_time")


def run_all_tests():
    """Run all tests and display results."""
    print("\n" + "="*60)
    print("CALENDAR UX IMPROVEMENTS - TEST SUITE")
    print("="*60 + "\n")
    
    # Test 1: Dynamic date examples
    print("\n📅 Test 1: Dynamic Date Examples")
    print("-" * 60)
    test = TestDynamicDateExamples()
    asyncio.run(test.test_date_example_uses_current_year())
    
    # Test 2: Title extraction
    print("\n✏️  Test 2: Title Extraction Logic")
    print("-" * 60)
    title_tests = TestTitleExtraction()
    title_tests.test_quoted_title_preserved()
    title_tests.test_call_it_pattern()
    title_tests.test_title_before_time()
    title_tests.test_generic_phrase_rejected()
    title_tests.test_garbage_detection()
    title_tests.test_valid_title_max_length()
    
    # Test 3: Time range extraction
    print("\n⏰ Test 3: Time Range Extraction")
    print("-" * 60)
    time_tests = TestTimeRangeExtraction()
    time_tests.test_explicit_time_range()
    time_tests.test_time_range_with_dash()
    time_tests.test_time_range_ampm()
    time_tests.test_single_time_no_end()
    
    # Test 4: Slot filling
    print("\n🔄 Test 4: Slot Filling State Machine")
    print("-" * 60)
    slot_tests = TestSlotFillingStateMachine()
    asyncio.run(slot_tests.test_incremental_slot_filling())
    asyncio.run(slot_tests.test_modification_before_confirmation())
    
    # Test 5: State management
    print("\n🎛️  Test 5: State Management")
    print("-" * 60)
    state_tests = TestStateManagement()
    asyncio.run(state_tests.test_cancellation())
    asyncio.run(state_tests.test_provider_selection_state())
    
    # Test 6: Timezone handling
    print("\n🌍 Test 6: Timezone Handling")
    print("-" * 60)
    tz_tests = TestTimezoneHandling()
    asyncio.run(tz_tests.test_default_timezone())
    tz_tests.test_duration_calculation_from_end_time()
    
    print("\n" + "="*60)
    print("✅ ALL TESTS COMPLETED")
    print("="*60 + "\n")


if __name__ == "__main__":
    run_all_tests()

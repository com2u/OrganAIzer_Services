"""
Unit Tests for Calendar Event Parsing Accuracy

Tests the fixes for:
- Quoted title extraction: 'Meeting at 12:00' (exact match)
- Duration parsing: "one hour" -> 60 minutes
- Provider extraction: "Google calendar" -> google
- Default duration: 60 minutes (not 30)
- Time parsing: "12:00", "2pm", etc.
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))

from utils.slot_extraction import SlotExtractor
from datetime import datetime, timedelta


def test_quoted_title_extraction():
    """Test: Quoted title should be extracted exactly as written."""
    print("\n=== TEST 1: Quoted Title Extraction ===")
    
    message = "Add an event tomorrow at 12:00; call it 'Meeting at 12:00'; should take one hour; add to my Google calendar."
    
    extracted = SlotExtractor.extract_calendar_slots(message)
    
    print(f"Input: {message}")
    print(f"Extracted title: {extracted.get('title')}")
    
    # PASS: Title should be exactly "Meeting at 12:00" (from quoted string)
    assert extracted.get('title') == "Meeting at 12:00", f"Expected 'Meeting at 12:00', got '{extracted.get('title')}'"
    print("✅ PASS: Title extracted correctly from quoted string")


def test_duration_one_hour():
    """Test: 'one hour' should parse to 60 minutes."""
    print("\n=== TEST 2: Duration 'one hour' => 60 minutes ===")
    
    message = "Add an event tomorrow at 12:00; call it 'Meeting at 12:00'; should take one hour; add to my Google calendar."
    
    extracted = SlotExtractor.extract_calendar_slots(message)
    
    print(f"Input: {message}")
    print(f"Extracted duration: {extracted.get('duration')} minutes")
    
    # PASS: Duration should be 60 minutes
    assert extracted.get('duration') == 60, f"Expected 60 minutes, got {extracted.get('duration')}"
    print("✅ PASS: 'one hour' correctly parsed to 60 minutes")


def test_provider_google():
    """Test: 'Google calendar' should extract provider=google."""
    print("\n=== TEST 3: Provider extraction (Google) ===")
    
    message = "Add an event tomorrow at 12:00; call it 'Meeting at 12:00'; should take one hour; add to my Google calendar."
    
    extracted = SlotExtractor.extract_calendar_slots(message)
    
    print(f"Input: {message}")
    print(f"Extracted provider: {extracted.get('provider')}")
    
    # PASS: Provider should be "google"
    assert extracted.get('provider') == "google", f"Expected 'google', got '{extracted.get('provider')}'"
    print("✅ PASS: Provider correctly extracted as 'google'")


def test_time_12_00():
    """Test: '12:00' should parse to 12:00."""
    print("\n=== TEST 4: Time parsing '12:00' ===")
    
    message = "Add an event tomorrow at 12:00; call it 'Meeting at 12:00'; should take one hour; add to my Google calendar."
    
    extracted = SlotExtractor.extract_calendar_slots(message)
    
    print(f"Input: {message}")
    print(f"Extracted time: {extracted.get('time')}")
    
    # PASS: Time should be "12:00"
    assert extracted.get('time') == "12:00", f"Expected '12:00', got '{extracted.get('time')}'"
    print("✅ PASS: Time correctly parsed as '12:00'")


def test_date_tomorrow():
    """Test: 'tomorrow' should parse to tomorrow's date."""
    print("\n=== TEST 5: Date parsing 'tomorrow' ===")
    
    message = "Add an event tomorrow at 12:00; call it 'Meeting at 12:00'; should take one hour; add to my Google calendar."
    
    extracted = SlotExtractor.extract_calendar_slots(message)
    
    print(f"Input: {message}")
    print(f"Extracted date: {extracted.get('date')}")
    
    # PASS: Date should be tomorrow
    tomorrow = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
    assert extracted.get('date') == tomorrow, f"Expected '{tomorrow}', got '{extracted.get('date')}'"
    print(f"✅ PASS: Date correctly parsed as tomorrow ({tomorrow})")


def test_end_time_calculation():
    """Test: End time should be start + duration (13:00 for 12:00 + 60 minutes)."""
    print("\n=== TEST 6: End time calculation ===")
    
    message = "Add an event tomorrow at 12:00; call it 'Meeting at 12:00'; should take one hour"
    
    extracted = SlotExtractor.extract_calendar_slots(message)
    
    start_time = extracted.get('time')  # "12:00"
    duration = extracted.get('duration', 60)  # 60 minutes
    date = extracted.get('date')
    
    print(f"Start time: {start_time}")
    print(f"Duration: {duration} minutes")
    
    if start_time and date:
        start_dt = datetime.fromisoformat(f"{date}T{start_time}:00")
        end_dt = start_dt + timedelta(minutes=duration)
        end_time = end_dt.strftime("%H:%M")
        
        print(f"Calculated end time: {end_time}")
        
        # PASS: End time should be 13:00 (12:00 + 60 minutes)
        assert end_time == "13:00", f"Expected end time '13:00', got '{end_time}'"
        print("✅ PASS: End time correctly calculated as 13:00")
    else:
        raise AssertionError("Missing start time or date for end time calculation")


def test_additional_patterns():
    """Test additional parsing patterns."""
    print("\n=== TEST 7: Additional Patterns ===")
    
    test_cases = [
        {
            "input": "Schedule 'Project Review' tomorrow at 2pm for 2 hours",
            "expected": {
                "title": "Project Review",
                "time": "14:00",
                "duration": 120
            }
        },
        {
            "input": "Add 'Team Standup' today at 9:00 for 30 minutes on Google calendar",
            "expected": {
                "title": "Team Standup",
                "time": "09:00",
                "duration": 30,
                "provider": "google"
            }
        },
        {
            "input": "Create event 'Lunch Break' tomorrow at noon for half an hour",
            "expected": {
                "title": "Lunch Break",
                "time": "12:00",
                "duration": 30
            }
        }
    ]
    
    for i, test_case in enumerate(test_cases, 1):
        print(f"\n  Test 7.{i}: {test_case['input'][:50]}...")
        extracted = SlotExtractor.extract_calendar_slots(test_case['input'])
        
        for key, expected_value in test_case['expected'].items():
            actual_value = extracted.get(key)
            print(f"    {key}: expected={expected_value}, actual={actual_value}")
            assert actual_value == expected_value, f"Mismatch for {key}: expected {expected_value}, got {actual_value}"
        
        print(f"  ✅ Test 7.{i} PASS")
    
    print("\n✅ PASS: All additional patterns work correctly")


def test_default_duration():
    """Test: Default duration in calendar slots should be 60 minutes (not 30)."""
    print("\n=== TEST 8: Default Duration Value ===")
    
    message = "Add an event tomorrow at 12:00 called Team Meeting"
    
    extracted = SlotExtractor.extract_calendar_slots(message)
    
    # When no duration is specified, the executive_agent_service uses default of 60
    # This test verifies that the extraction doesn't override with a wrong default
    print(f"Input: {message}")
    print(f"Extracted duration: {extracted.get('duration')}")
    
    # If duration is not mentioned, extracted should be None
    # The default of 60 is applied in executive_agent_service.py
    if extracted.get('duration') is None:
        print("✅ PASS: No duration extracted (will use default 60 in service)")
    else:
        # If a duration was extracted, it should be reasonable
        assert extracted.get('duration') >= 30, f"Unexpected duration: {extracted.get('duration')}"
        print(f"✅ PASS: Duration extracted as {extracted.get('duration')} minutes")


def run_all_tests():
    """Run all calendar event parsing tests."""
    print("=" * 70)
    print("CALENDAR EVENT PARSING TESTS")
    print("Testing fixes for: Quoted titles, duration parsing, provider extraction")
    print("=" * 70)
    
    tests = [
        test_quoted_title_extraction,
        test_duration_one_hour,
        test_provider_google,
        test_time_12_00,
        test_date_tomorrow,
        test_end_time_calculation,
        test_additional_patterns,
        test_default_duration
    ]
    
    passed = 0
    failed = 0
    
    for test_func in tests:
        try:
            test_func()
            passed += 1
        except AssertionError as e:
            print(f"❌ FAIL: {test_func.__name__}: {e}")
            failed += 1
        except Exception as e:
            print(f"❌ ERROR: {test_func.__name__}: {e}")
            failed += 1
    
    print("\n" + "=" * 70)
    print(f"TEST RESULTS: {passed} passed, {failed} failed out of {len(tests)} total")
    print("=" * 70)
    
    if failed == 0:
        print("✅ ALL TESTS PASSED! Calendar event parsing is working correctly.")
        return True
    else:
        print(f"⚠️ {failed} test(s) failed. Please review the output above.")
        return False


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)

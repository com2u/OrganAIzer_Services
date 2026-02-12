"""
Test script for Google Calendar event creation endpoints.

Tests both the canonical /api/google/calendar/events and alias /google/calendar/events routes.
"""

import requests
import json
from datetime import datetime, timedelta

BASE_URL = "http://localhost:8000"
USER_ID = "default_user"

def print_section(title):
    """Print a formatted section header."""
    print("\n" + "=" * 80)
    print(f"  {title}")
    print("=" * 80)

def test_canonical_endpoint():
    """Test POST /api/google/calendar/events (canonical route)."""
    print_section("TEST 1: Canonical Endpoint - POST /api/google/calendar/events")
    
    # Calculate tomorrow's date
    tomorrow = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
    
    # Test data
    event_data = {
        "title": "Test Event - Canonical Route",
        "date": tomorrow,
        "start_time": "14:00",
        "end_time": "15:30",
        "timezone": "Europe/Berlin",
        "description": "This is a test event created via the canonical API endpoint",
        "location": "Berlin Office",
        "confirm": True  # Actually create the event
    }
    
    print(f"\n📤 Request:")
    print(f"POST {BASE_URL}/api/google/calendar/events?user_id={USER_ID}")
    print(f"Body: {json.dumps(event_data, indent=2)}")
    
    try:
        response = requests.post(
            f"{BASE_URL}/api/google/calendar/events",
            params={"user_id": USER_ID},
            json=event_data,
            timeout=10
        )
        
        print(f"\n📥 Response:")
        print(f"Status: {response.status_code}")
        print(f"Body: {json.dumps(response.json(), indent=2)}")
        
        if response.status_code == 200:
            result = response.json()
            if result.get("event_id"):
                print(f"\n✅ SUCCESS: Event created with ID {result['event_id']}")
                print(f"🔗 Link: {result.get('html_link', 'N/A')}")
                return result["event_id"]
            else:
                print(f"\n⚠️  Event not created (preview mode or dry_run)")
        else:
            print(f"\n❌ FAILED: {response.status_code}")
            
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
    
    return None

def test_alias_endpoint():
    """Test POST /google/calendar/events (alias route)."""
    print_section("TEST 2: Alias Endpoint - POST /google/calendar/events")
    
    # Calculate day after tomorrow
    day_after_tomorrow = (datetime.now() + timedelta(days=2)).strftime("%Y-%m-%d")
    
    # Test data
    event_data = {
        "title": "Test Event - Alias Route",
        "date": day_after_tomorrow,
        "start_time": "10:00",
        "end_time": "11:00",
        "timezone": "Europe/Berlin",
        "description": "This is a test event created via the alias endpoint",
        "confirm": True
    }
    
    print(f"\n📤 Request:")
    print(f"POST {BASE_URL}/google/calendar/events?user_id={USER_ID}")
    print(f"Body: {json.dumps(event_data, indent=2)}")
    
    try:
        response = requests.post(
            f"{BASE_URL}/google/calendar/events",
            params={"user_id": USER_ID},
            json=event_data,
            timeout=10
        )
        
        print(f"\n📥 Response:")
        print(f"Status: {response.status_code}")
        print(f"Body: {json.dumps(response.json(), indent=2)}")
        
        if response.status_code == 200:
            result = response.json()
            if result.get("event_id"):
                print(f"\n✅ SUCCESS: Event created with ID {result['event_id']}")
                print(f"🔗 Link: {result.get('html_link', 'N/A')}")
                return result["event_id"]
            else:
                print(f"\n⚠️  Event not created (preview mode or dry_run)")
        else:
            print(f"\n❌ FAILED: {response.status_code}")
            
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
    
    return None

def test_dry_run_mode():
    """Test dry_run mode (preview without creating)."""
    print_section("TEST 3: Dry Run Mode (Preview)")
    
    tomorrow = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
    
    event_data = {
        "title": "Dry Run Test Event",
        "date": tomorrow,
        "start_time": "16:00",
        "end_time": "17:00",
        "timezone": "Europe/Berlin",
        "dry_run": True,  # Preview mode
        "confirm": True   # Confirm is ignored in dry_run
    }
    
    print(f"\n📤 Request:")
    print(f"POST {BASE_URL}/api/google/calendar/events?user_id={USER_ID}")
    print(f"Body: {json.dumps(event_data, indent=2)}")
    
    try:
        response = requests.post(
            f"{BASE_URL}/api/google/calendar/events",
            params={"user_id": USER_ID},
            json=event_data,
            timeout=10
        )
        
        print(f"\n📥 Response:")
        print(f"Status: {response.status_code}")
        print(f"Body: {json.dumps(response.json(), indent=2)}")
        
        if response.status_code == 200:
            result = response.json()
            if result.get("status") == "preview":
                print(f"\n✅ SUCCESS: Dry run returned preview")
                print(f"Preview: {json.dumps(result.get('preview', {}), indent=2)}")
            else:
                print(f"\n⚠️  Unexpected status: {result.get('status')}")
        else:
            print(f"\n❌ FAILED: {response.status_code}")
            
    except Exception as e:
        print(f"\n❌ ERROR: {e}")

def test_validation_errors():
    """Test input validation."""
    print_section("TEST 4: Validation Errors")
    
    tomorrow = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
    
    # Test 1: end_time before start_time
    print("\n--- Test 4a: Invalid times (end before start) ---")
    event_data = {
        "title": "Invalid Event",
        "date": tomorrow,
        "start_time": "15:00",
        "end_time": "14:00",  # Before start time!
        "confirm": True
    }
    
    try:
        response = requests.post(
            f"{BASE_URL}/api/google/calendar/events",
            params={"user_id": USER_ID},
            json=event_data,
            timeout=10
        )
        
        print(f"Status: {response.status_code}")
        print(f"Response: {json.dumps(response.json(), indent=2)}")
        
        if response.status_code == 400:
            print("✅ Correctly rejected invalid time range")
        else:
            print("❌ Should have rejected invalid time range")
            
    except Exception as e:
        print(f"❌ ERROR: {e}")
    
    # Test 2: Missing confirm flag
    print("\n--- Test 4b: Missing confirm flag ---")
    event_data = {
        "title": "No Confirm Event",
        "date": tomorrow,
        "start_time": "14:00",
        "end_time": "15:00",
        "confirm": False  # Not confirmed!
    }
    
    try:
        response = requests.post(
            f"{BASE_URL}/api/google/calendar/events",
            params={"user_id": USER_ID},
            json=event_data,
            timeout=10
        )
        
        print(f"Status: {response.status_code}")
        print(f"Response: {json.dumps(response.json(), indent=2)}")
        
        if response.status_code == 400:
            print("✅ Correctly rejected unconfirmed request")
        else:
            print("❌ Should have rejected unconfirmed request")
            
    except Exception as e:
        print(f"❌ ERROR: {e}")

def test_list_events():
    """Test GET /api/google/calendar/events to verify created events."""
    print_section("TEST 5: List Events (Verification)")
    
    print(f"\n📤 Request:")
    print(f"GET {BASE_URL}/api/google/calendar/events?user_id={USER_ID}")
    
    try:
        response = requests.get(
            f"{BASE_URL}/api/google/calendar/events",
            params={"user_id": USER_ID, "limit": 10},
            timeout=10
        )
        
        print(f"\n📥 Response:")
        print(f"Status: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            events = result.get("events", [])
            print(f"Found {len(events)} events")
            
            # Show first few events
            for i, event in enumerate(events[:5], 1):
                print(f"\n{i}. {event.get('summary', 'No title')}")
                print(f"   Start: {event.get('start', 'N/A')}")
                print(f"   End: {event.get('end', 'N/A')}")
                print(f"   ID: {event.get('id', 'N/A')}")
            
            print("\n✅ Successfully retrieved events")
        else:
            print(f"❌ FAILED: {response.status_code}")
            print(f"Response: {json.dumps(response.json(), indent=2)}")
            
    except Exception as e:
        print(f"❌ ERROR: {e}")

def main():
    """Run all tests."""
    print("=" * 80)
    print("  Google Calendar Event Creation - Test Suite")
    print("=" * 80)
    print(f"\nBase URL: {BASE_URL}")
    print(f"User ID: {USER_ID}")
    print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Run tests
    test_canonical_endpoint()
    test_alias_endpoint()
    test_dry_run_mode()
    test_validation_errors()
    test_list_events()
    
    # Summary
    print_section("TEST SUMMARY")
    print("\n✅ All tests completed!")
    print("\nEndpoints tested:")
    print("  1. POST /api/google/calendar/events (canonical)")
    print("  2. POST /google/calendar/events (alias)")
    print("  3. Dry run mode")
    print("  4. Input validation")
    print("  5. GET /api/google/calendar/events (list)")
    print("\n" + "=" * 80 + "\n")

if __name__ == "__main__":
    main()

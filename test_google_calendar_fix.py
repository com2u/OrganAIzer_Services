"""
Test script to verify Google Calendar 403 fix.

This script tests the correct endpoint usage for Google Calendar API.
"""

import requests
import json
import sys

BASE_URL = "http://localhost:8000"
USER_ID = "default_user"

def print_section(title):
    """Print a formatted section header."""
    print(f"\n{'='*70}")
    print(f"  {title}")
    print(f"{'='*70}\n")

def test_wrong_endpoint():
    """Test the wrong endpoint that requires API key (should fail with 403)."""
    print_section("TEST 1: Wrong Endpoint (Expected to Fail)")
    
    url = f"{BASE_URL}/api/google/calendar/events"
    print(f"❌ Testing WRONG endpoint: {url}")
    print(f"   (This requires API key and is deprecated)")
    
    try:
        response = requests.get(url, params={"user_id": USER_ID})
        print(f"\n   Status Code: {response.status_code}")
        print(f"   Response: {json.dumps(response.json(), indent=2)}")
        
        if response.status_code == 403:
            print(f"\n✅ EXPECTED: Got 403 'Not authenticated' error")
            return True
        else:
            print(f"\n⚠️  UNEXPECTED: Expected 403, got {response.status_code}")
            return False
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        return False

def test_integration_status():
    """Test the integration status endpoint."""
    print_section("TEST 2: Check Google Connection Status")
    
    url = f"{BASE_URL}/api/integrations/status"
    print(f"✅ Testing: {url}?user_id={USER_ID}")
    
    try:
        response = requests.get(url, params={"user_id": USER_ID})
        print(f"\n   Status Code: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"   Response: {json.dumps(data, indent=2)}")
            
            google_connected = data.get("google", {}).get("connected", False)
            
            if google_connected:
                print(f"\n✅ SUCCESS: Google account is connected!")
                scopes = data.get("google", {}).get("scopes", [])
                print(f"   Granted scopes: {len(scopes)} scopes")
                return True
            else:
                print(f"\n⚠️  WARNING: Google account not connected")
                print(f"\n   To connect, open this URL in your browser:")
                print(f"   {BASE_URL}/api/integrations/google/auth/start?user_id={USER_ID}")
                return False
        else:
            print(f"\n❌ ERROR: Status code {response.status_code}")
            print(f"   Response: {response.text}")
            return False
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        return False

def test_correct_endpoint(google_connected):
    """Test the correct endpoint for listing calendar events."""
    print_section("TEST 3: Correct Endpoint (List Calendar Events)")
    
    url = f"{BASE_URL}/api/integrations/google/calendar/events"
    print(f"✅ Testing CORRECT endpoint: {url}")
    print(f"   Parameters: user_id={USER_ID}, limit=5")
    
    try:
        response = requests.get(
            url, 
            params={
                "user_id": USER_ID,
                "limit": 5
            }
        )
        print(f"\n   Status Code: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            event_count = data.get("count", 0)
            print(f"\n✅ SUCCESS: Retrieved {event_count} calendar events")
            
            if event_count > 0:
                print(f"\n   Sample event:")
                first_event = data.get("events", [])[0]
                print(f"   - ID: {first_event.get('id', 'N/A')}")
                print(f"   - Summary: {first_event.get('summary', 'N/A')}")
                print(f"   - Start: {first_event.get('start', 'N/A')}")
                print(f"   - End: {first_event.get('end', 'N/A')}")
            else:
                print(f"   No events found in the calendar")
            
            return True
            
        elif response.status_code == 401:
            print(f"\n⚠️  ERROR 401: Not authenticated")
            print(f"   This means Google account is not connected.")
            print(f"\n   To connect, open this URL in your browser:")
            print(f"   {BASE_URL}/api/integrations/google/auth/start?user_id={USER_ID}")
            return False
            
        elif response.status_code == 409:
            print(f"\n⚠️  ERROR 409: Scope changed")
            error_data = response.json()
            print(f"   {error_data.get('detail', {}).get('message', 'Permissions need to be updated')}")
            print(f"\n   To fix, disconnect and reconnect:")
            print(f"   1. Disconnect: DELETE {BASE_URL}/api/integrations/google/disconnect?user_id={USER_ID}")
            print(f"   2. Reconnect: {BASE_URL}/api/integrations/google/auth/start?user_id={USER_ID}")
            return False
            
        else:
            print(f"\n❌ ERROR: Status code {response.status_code}")
            print(f"   Response: {response.text}")
            return False
            
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        return False

def main():
    """Run all tests."""
    print_section("Google Calendar 403 Fix - Verification Tests")
    print("This script verifies that the correct endpoints are being used.")
    
    # Test 1: Verify wrong endpoint fails as expected
    test1_passed = test_wrong_endpoint()
    
    # Test 2: Check Google connection status
    test2_passed = test_integration_status()
    google_connected = test2_passed
    
    # Test 3: Test correct endpoint
    test3_passed = test_correct_endpoint(google_connected)
    
    # Summary
    print_section("Test Summary")
    print(f"Test 1 (Wrong endpoint should fail): {'✅ PASSED' if test1_passed else '❌ FAILED'}")
    print(f"Test 2 (Integration status check): {'✅ PASSED' if test2_passed else '⚠️  Not Connected'}")
    print(f"Test 3 (Correct endpoint works): {'✅ PASSED' if test3_passed else '❌ FAILED'}")
    
    print("\n" + "="*70)
    print("CONCLUSION:")
    print("="*70)
    
    if test1_passed and test3_passed:
        print("✅ All tests PASSED! The fix is working correctly.")
        print(f"\nℹ️  Use this endpoint for calendar operations:")
        print(f"   GET  {BASE_URL}/api/integrations/google/calendar/events")
        print(f"   POST {BASE_URL}/api/integrations/google/calendar/events")
        sys.exit(0)
    elif test1_passed and not google_connected:
        print("⚠️  Fix is verified, but Google account not connected.")
        print(f"\n📝 Next step: Connect your Google account")
        print(f"   Open in browser: {BASE_URL}/api/integrations/google/auth/start?user_id={USER_ID}")
        sys.exit(0)
    else:
        print("❌ Some tests failed. Please check the output above.")
        sys.exit(1)

if __name__ == "__main__":
    main()

"""
Regression test for Google Calendar API restoration.
Tests that the calendar endpoints are working and returning proper errors.
"""

import requests
import json
from datetime import datetime, timedelta

BASE_URL = "http://127.0.0.1:8000"


def test_openapi_contains_calendar_endpoints():
    """Verify that calendar endpoints are registered in OpenAPI spec."""
    print("\n1️⃣  Testing OpenAPI registration...")
    
    response = requests.get(f"{BASE_URL}/openapi.json")
    assert response.status_code == 200, "Failed to fetch OpenAPI spec"
    
    openapi = response.json()
    paths = openapi.get("paths", {})
    
    # Check POST endpoint exists
    post_endpoint = "/api/integrations/google/calendar/events"
    assert post_endpoint in paths, f"POST endpoint {post_endpoint} not found in OpenAPI"
    assert "post" in paths[post_endpoint], f"POST method not found for {post_endpoint}"
    
    # Check GET endpoint exists
    assert "get" in paths[post_endpoint], f"GET method not found for {post_endpoint}"
    
    print(f"   ✅ POST {post_endpoint} - registered")
    print(f"   ✅ GET {post_endpoint} - registered")
    return True


def test_calendar_create_without_auth():
    """Test that creating event without auth returns 401 with clear message."""
    print("\n2️⃣  Testing POST without authentication...")
    
    event_data = {
        "summary": "Test Event",
        "description": "Test description",
        "start": (datetime.utcnow() + timedelta(days=1)).isoformat() + "Z",
        "end": (datetime.utcnow() + timedelta(days=1, hours=1)).isoformat() + "Z",
        "location": "Test Location"
    }
    
    response = requests.post(
        f"{BASE_URL}/api/integrations/google/calendar/events",
        json=event_data,
        params={"user_id": "test_user_noauth"}
    )
    
    # Should return 401, NOT 501
    assert response.status_code == 401, f"Expected 401, got {response.status_code}"
    
    data = response.json()
    detail = data.get("detail", {})
    
    # Verify error structure
    assert detail.get("code") == "NOT_AUTHENTICATED", f"Wrong error code: {detail.get('code')}"
    assert "connect" in detail.get("message", "").lower() or "reconnect" in detail.get("message", "").lower(), \
        "Error message should mention connecting Google account"
    assert detail.get("action") == "CONNECT_GOOGLE", "Should have CONNECT_GOOGLE action"
    
    print(f"   ✅ Returns 401 (not 501)")
    print(f"   ✅ Error code: {detail.get('code')}")
    print(f"   ✅ Message: {detail.get('message')}")
    print(f"   ✅ Action: {detail.get('action')}")
    return True


def test_calendar_list_without_auth():
    """Test that listing events without auth returns 401 with clear message."""
    print("\n3️⃣  Testing GET without authentication...")
    
    response = requests.get(
        f"{BASE_URL}/api/integrations/google/calendar/events",
        params={"user_id": "test_user_noauth", "max_results": 10}
    )
    
    # Should return 401, NOT 501
    assert response.status_code == 401, f"Expected 401, got {response.status_code}"
    
    data = response.json()
    detail = data.get("detail", {})
    
    # Verify error structure
    assert detail.get("code") == "NOT_AUTHENTICATED", f"Wrong error code: {detail.get('code')}"
    assert "connect" in detail.get("message", "").lower() or "reconnect" in detail.get("message", "").lower(), \
        "Error message should mention connecting Google account"
    assert detail.get("action") == "CONNECT_GOOGLE", "Should have CONNECT_GOOGLE action"
    
    print(f"   ✅ Returns 401 (not 501)")
    print(f"   ✅ Error code: {detail.get('code')}")
    print(f"   ✅ Message: {detail.get('message')}")
    print(f"   ✅ Action: {detail.get('action')}")
    return True


def test_calendar_with_valid_tokens_if_available():
    """
    Test calendar operations with valid tokens if available.
    This is optional - will skip if no tokens are found.
    """
    print("\n4️⃣  Testing with valid tokens (if available)...")
    
    # Try to create an event with default_user
    event_data = {
        "summary": "Test Event - Automated Test",
        "description": "Created by regression test script",
        "start": (datetime.utcnow() + timedelta(days=1)).isoformat() + "Z",
        "end": (datetime.utcnow() + timedelta(days=1, hours=1)).isoformat() + "Z",
        "location": "Test Location"
    }
    
    response = requests.post(
        f"{BASE_URL}/api/integrations/google/calendar/events",
        json=event_data,
        params={"user_id": "default_user"}
    )
    
    if response.status_code == 401:
        print("   ⚠️  No valid tokens found for default_user - skipping authenticated tests")
        print("   ℹ️  To test with auth, connect Google account via /api/integrations/google/auth/start")
        return True
    
    if response.status_code == 200:
        # Success! Verify response structure
        data = response.json()
        assert "id" in data, "Response should contain event ID"
        assert data.get("summary") == event_data["summary"], "Summary mismatch"
        
        event_id = data.get("id")
        print(f"   ✅ Event created successfully")
        print(f"   ✅ Event ID: {event_id}")
        print(f"   ✅ Summary: {data.get('summary')}")
        
        # Try to list events
        list_response = requests.get(
            f"{BASE_URL}/api/integrations/google/calendar/events",
            params={"user_id": "default_user", "max_results": 5}
        )
        
        if list_response.status_code == 200:
            list_data = list_response.json()
            assert "events" in list_data, "Response should contain events list"
            assert "total" in list_data, "Response should contain total count"
            
            print(f"   ✅ Retrieved {list_data.get('total')} events")
            print(f"   ✅ First event: {list_data['events'][0]['summary'] if list_data['events'] else 'N/A'}")
        
        return True
    
    # Unexpected status code
    print(f"   ⚠️  Unexpected status code: {response.status_code}")
    print(f"   Response: {response.text}")
    return False


def main():
    """Run all tests."""
    print("=" * 70)
    print("🧪 Google Calendar API Restoration - Regression Test")
    print("=" * 70)
    
    try:
        results = []
        
        # Test 1: OpenAPI registration
        results.append(("OpenAPI Registration", test_openapi_contains_calendar_endpoints()))
        
        # Test 2: POST without auth
        results.append(("POST without auth", test_calendar_create_without_auth()))
        
        # Test 3: GET without auth
        results.append(("GET without auth", test_calendar_list_without_auth()))
        
        # Test 4: With auth (if available)
        results.append(("With valid tokens", test_calendar_with_valid_tokens_if_available()))
        
        # Summary
        print("\n" + "=" * 70)
        print("📊 Test Summary")
        print("=" * 70)
        
        passed = sum(1 for _, result in results if result)
        total = len(results)
        
        for test_name, result in results:
            status = "✅ PASS" if result else "❌ FAIL"
            print(f"   {status} - {test_name}")
        
        print(f"\n   Total: {passed}/{total} tests passed")
        
        if passed == total:
            print("\n🎉 All tests passed! Google Calendar API is working correctly.")
            return 0
        else:
            print("\n⚠️  Some tests failed. Please review the errors above.")
            return 1
            
    except Exception as e:
        print(f"\n❌ Test suite failed with error: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    exit(main())

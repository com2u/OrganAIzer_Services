"""
Test script for Google OAuth callback URL configuration.

This script verifies that:
1. The canonical callback URL is properly configured
2. The start endpoint uses the correct redirect_uri
3. The callback endpoint validates parameters correctly
4. State handling works as expected
"""

import sys
import os
import requests
from urllib.parse import urlparse, parse_qs

# Configuration
BASE_URL = "http://localhost:8000"
EXPECTED_CALLBACK_URL = "http://localhost:8000/api/integrations/google/auth/callback"

def test_callback_url_constant():
    """Test 1: Verify the canonical callback URL constant is defined"""
    print("\n" + "="*70)
    print("Test 1: Verifying Canonical Callback URL Constant")
    print("="*70)
    
    # Read the integrations.py file to check the constant
    integrations_file = "backend/api/integrations.py"
    
    try:
        with open(integrations_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Check if the constant is defined
        if 'GOOGLE_OAUTH_CALLBACK_URL = "http://localhost:8000/api/integrations/google/auth/callback"' in content:
            print("✅ PASS: GOOGLE_OAUTH_CALLBACK_URL constant is properly defined")
            return True
        else:
            print("❌ FAIL: GOOGLE_OAUTH_CALLBACK_URL constant not found or incorrect")
            return False
    except FileNotFoundError:
        print(f"❌ FAIL: Could not find {integrations_file}")
        return False

def test_start_endpoint_redirect_uri():
    """Test 2: Verify start endpoint returns proper authorization URL"""
    print("\n" + "="*70)
    print("Test 2: Verifying Start Endpoint Uses Correct redirect_uri")
    print("="*70)
    
    try:
        # Call the start endpoint (it will redirect to Google)
        response = requests.get(
            f"{BASE_URL}/api/integrations/google/auth/start",
            params={"user_id": "test_user"},
            allow_redirects=False  # Don't follow the redirect
        )
        
        # Check if we got a redirect
        if response.status_code == 302:
            location = response.headers.get('Location', '')
            
            # Parse the redirect URL
            parsed = urlparse(location)
            query_params = parse_qs(parsed.query)
            
            # Check if redirect_uri is in the authorization URL
            redirect_uri = query_params.get('redirect_uri', [None])[0]
            
            if redirect_uri == EXPECTED_CALLBACK_URL:
                print(f"✅ PASS: Start endpoint uses correct redirect_uri")
                print(f"   redirect_uri: {redirect_uri}")
                return True
            else:
                print(f"❌ FAIL: Start endpoint uses wrong redirect_uri")
                print(f"   Expected: {EXPECTED_CALLBACK_URL}")
                print(f"   Got: {redirect_uri}")
                return False
        else:
            print(f"❌ FAIL: Start endpoint returned status {response.status_code} instead of 302")
            return False
            
    except requests.exceptions.ConnectionError:
        print("⚠️  SKIP: Backend server is not running. Start it with: python backend/main.py")
        return None
    except Exception as e:
        print(f"❌ FAIL: Error testing start endpoint: {e}")
        return False

def test_callback_missing_code():
    """Test 3: Verify callback endpoint handles missing code parameter"""
    print("\n" + "="*70)
    print("Test 3: Verifying Callback Handles Missing Code Parameter")
    print("="*70)
    
    try:
        # Call callback without code parameter
        response = requests.get(
            f"{BASE_URL}/api/integrations/google/auth/callback",
            params={"state": "dummy_state"}  # Only state, no code
        )
        
        # Should return detailed error JSON
        if response.status_code == 200:  # Now returns 200 with error JSON
            data = response.json()
            
            if data.get('error') == 'missing_code':
                print("✅ PASS: Callback returns proper missing_code error")
                print(f"   Error detail: {data.get('detail')}")
                
                # Check for troubleshooting steps
                if 'troubleshooting' in data:
                    print(f"   Troubleshooting steps provided: ✅")
                
                # Check for expected_redirect_uri
                if data.get('expected_redirect_uri') == EXPECTED_CALLBACK_URL:
                    print(f"   Expected redirect_uri correct: ✅")
                    return True
                else:
                    print(f"   ❌ Expected redirect_uri mismatch")
                    return False
            else:
                print(f"❌ FAIL: Wrong error type: {data.get('error')}")
                return False
        else:
            print(f"❌ FAIL: Callback returned status {response.status_code}")
            print(f"   Response: {response.text[:200]}")
            return False
            
    except requests.exceptions.ConnectionError:
        print("⚠️  SKIP: Backend server is not running")
        return None
    except Exception as e:
        print(f"❌ FAIL: Error testing callback: {e}")
        return False

def test_callback_missing_state():
    """Test 4: Verify callback endpoint handles missing state parameter"""
    print("\n" + "="*70)
    print("Test 4: Verifying Callback Handles Missing State Parameter")
    print("="*70)
    
    try:
        # Call callback without state parameter
        response = requests.get(
            f"{BASE_URL}/api/integrations/google/auth/callback",
            params={"code": "dummy_code"}  # Only code, no state
        )
        
        # Should return 400 error
        if response.status_code == 400:
            data = response.json()
            
            if 'state' in data.get('detail', '').lower():
                print("✅ PASS: Callback rejects missing state parameter")
                print(f"   Error: {data.get('detail')}")
                return True
            else:
                print(f"❌ FAIL: Error message doesn't mention state")
                return False
        else:
            print(f"❌ FAIL: Expected status 400, got {response.status_code}")
            return False
            
    except requests.exceptions.ConnectionError:
        print("⚠️  SKIP: Backend server is not running")
        return None
    except Exception as e:
        print(f"❌ FAIL: Error testing callback: {e}")
        return False

def test_startup_logging():
    """Test 5: Verify startup logging includes OAuth configuration"""
    print("\n" + "="*70)
    print("Test 5: Verifying Startup Logging Configuration")
    print("="*70)
    
    # Read the main.py file to check for OAuth logging
    main_file = "backend/main.py"
    
    try:
        with open(main_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Check if OAuth configuration logging is present
        if 'Google OAuth redirect_uri:' in content and 'google_redirect_uri' in content:
            print("✅ PASS: Startup logging includes OAuth configuration")
            return True
        else:
            print("❌ FAIL: Startup logging missing OAuth configuration")
            return False
    except FileNotFoundError:
        print(f"❌ FAIL: Could not find {main_file}")
        return False

def test_enhanced_logging():
    """Test 6: Verify enhanced emoji logging in integrations.py"""
    print("\n" + "="*70)
    print("Test 6: Verifying Enhanced Logging with Emojis")
    print("="*70)
    
    integrations_file = "backend/api/integrations.py"
    
    try:
        with open(integrations_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Check for emoji logging markers
        emojis = ['🔐', '📍', '✅', '❌', '📥', '🔑', '🔄', '📋']
        found_emojis = [emoji for emoji in emojis if emoji in content]
        
        if len(found_emojis) >= 6:
            print(f"✅ PASS: Enhanced emoji logging found ({len(found_emojis)}/8 emojis)")
            print(f"   Emojis detected: {', '.join(found_emojis)}")
            return True
        else:
            print(f"❌ FAIL: Insufficient emoji logging ({len(found_emojis)}/8 emojis)")
            return False
    except FileNotFoundError:
        print(f"❌ FAIL: Could not find {integrations_file}")
        return False

def run_all_tests():
    """Run all tests and report results"""
    print("\n" + "="*70)
    print("🧪 Google OAuth Callback URL Fix - Test Suite")
    print("="*70)
    
    tests = [
        ("Canonical Callback URL Constant", test_callback_url_constant),
        ("Start Endpoint redirect_uri", test_start_endpoint_redirect_uri),
        ("Callback Missing Code", test_callback_missing_code),
        ("Callback Missing State", test_callback_missing_state),
        ("Startup Logging", test_startup_logging),
        ("Enhanced Emoji Logging", test_enhanced_logging),
    ]
    
    results = []
    for test_name, test_func in tests:
        result = test_func()
        results.append((test_name, result))
    
    # Print summary
    print("\n" + "="*70)
    print("📊 Test Summary")
    print("="*70)
    
    passed = sum(1 for _, r in results if r is True)
    failed = sum(1 for _, r in results if r is False)
    skipped = sum(1 for _, r in results if r is None)
    total = len(results)
    
    for test_name, result in results:
        if result is True:
            print(f"✅ PASS: {test_name}")
        elif result is False:
            print(f"❌ FAIL: {test_name}")
        else:
            print(f"⚠️  SKIP: {test_name}")
    
    print("-"*70)
    print(f"Total: {total} | Passed: {passed} | Failed: {failed} | Skipped: {skipped}")
    print("="*70)
    
    # Exit code
    if failed > 0:
        print("\n❌ Some tests failed. Please review the output above.")
        sys.exit(1)
    elif skipped > 0:
        print("\n⚠️  Some tests were skipped (backend not running).")
        print("   Start backend with: python backend/main.py")
        sys.exit(0)
    else:
        print("\n✅ All tests passed!")
        sys.exit(0)

if __name__ == "__main__":
    run_all_tests()

"""
Test script to verify the Chrome Extension Translate & Summarize fix
"""
import requests
import json

API_URL = "http://localhost:8000/api/llm"

def test_without_api_key():
    """Test LLM endpoint without API key (Chrome Extension scenario)"""
    print("\n" + "="*70)
    print("Test 1: LLM Request WITHOUT API Key (Chrome Extension)")
    print("="*70)
    
    payload = {
        "prompt": "Translate to English: Hola, ¿cómo estás?"
    }
    
    try:
        response = requests.post(
            API_URL,
            json=payload,
            headers={"Content-Type": "application/json"}
        )
        
        print(f"Status Code: {response.status_code}")
        print(f"Response: {json.dumps(response.json(), indent=2)}")
        
        if response.status_code == 200:
            print("✅ SUCCESS: Request without API key works!")
            return True
        else:
            print("❌ FAILED: Request without API key failed")
            return False
    except Exception as e:
        print(f"❌ ERROR: {str(e)}")
        return False

def test_with_valid_api_key():
    """Test LLM endpoint with valid API key"""
    print("\n" + "="*70)
    print("Test 2: LLM Request WITH Valid API Key")
    print("="*70)
    
    payload = {
        "prompt": "Summarize in one sentence: The quick brown fox jumps over the lazy dog. This is a common English pangram used for testing."
    }
    
    try:
        response = requests.post(
            API_URL,
            json=payload,
            headers={
                "Content-Type": "application/json",
                "X-API-Key": "test-key-123"
            }
        )
        
        print(f"Status Code: {response.status_code}")
        print(f"Response: {json.dumps(response.json(), indent=2)}")
        
        if response.status_code == 200:
            print("✅ SUCCESS: Request with valid API key works!")
            return True
        else:
            print("❌ FAILED: Request with valid API key failed")
            return False
    except Exception as e:
        print(f"❌ ERROR: {str(e)}")
        return False

def test_with_invalid_api_key():
    """Test LLM endpoint with invalid API key"""
    print("\n" + "="*70)
    print("Test 3: LLM Request WITH Invalid API Key")
    print("="*70)
    
    payload = {
        "prompt": "Test prompt"
    }
    
    try:
        response = requests.post(
            API_URL,
            json=payload,
            headers={
                "Content-Type": "application/json",
                "X-API-Key": "invalid-key-xyz"
            }
        )
        
        print(f"Status Code: {response.status_code}")
        print(f"Response: {response.text}")
        
        if response.status_code == 401:
            print("✅ SUCCESS: Invalid API key correctly rejected!")
            return True
        else:
            print("❌ FAILED: Invalid API key should return 401")
            return False
    except Exception as e:
        print(f"❌ ERROR: {str(e)}")
        return False

def test_health_check():
    """Test if backend is running"""
    print("\n" + "="*70)
    print("Pre-Test: Backend Health Check")
    print("="*70)
    
    try:
        response = requests.get("http://localhost:8000/health", timeout=5)
        if response.status_code == 200:
            print("✅ Backend is running and healthy")
            return True
        else:
            print(f"⚠️  Backend responded with status: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Backend is not running: {str(e)}")
        print("\nPlease start the backend server with:")
        print("  cd backend && python main.py")
        return False

if __name__ == "__main__":
    print("\n" + "🧪 Chrome Extension Fix - Test Suite" + "\n")
    
    # Check if backend is running
    if not test_health_check():
        print("\n❌ Cannot proceed with tests - backend not available\n")
        exit(1)
    
    # Run all tests
    results = []
    results.append(("No API Key", test_without_api_key()))
    results.append(("Valid API Key", test_with_valid_api_key()))
    results.append(("Invalid API Key", test_with_invalid_api_key()))
    
    # Summary
    print("\n" + "="*70)
    print("TEST SUMMARY")
    print("="*70)
    
    for test_name, passed in results:
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{status} - {test_name}")
    
    all_passed = all(result[1] for result in results)
    
    print("\n" + "="*70)
    if all_passed:
        print("✅ ALL TESTS PASSED - Chrome Extension fix is working!")
        print(f"\nThe Translate and Summarize features should now work in the extension.")
    else:
        print("❌ SOME TESTS FAILED - Please review the errors above")
    print("="*70 + "\n")
    
    exit(0 if all_passed else 1)

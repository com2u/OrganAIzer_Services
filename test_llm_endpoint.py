"""
Test script for the /api/llm endpoint (Chrome Extension compatibility).
"""
import requests
import json

# Test the /api/llm endpoint
def test_llm_endpoint():
    url = "http://localhost:8000/api/llm"
    
    payload = {
        "prompt": "Say hello in one sentence."
    }
    
    headers = {
        "Content-Type": "application/json"
    }
    
    print("Testing POST /api/llm endpoint...")
    print(f"URL: {url}")
    print(f"Payload: {json.dumps(payload, indent=2)}")
    print("-" * 50)
    
    try:
        response = requests.post(url, json=payload, headers=headers, timeout=30)
        
        print(f"Status Code: {response.status_code}")
        print(f"Response Headers: {dict(response.headers)}")
        print("-" * 50)
        
        if response.status_code == 200:
            result = response.json()
            print("✅ SUCCESS!")
            print(f"Response: {json.dumps(result, indent=2)}")
            print("-" * 50)
            print("Chrome Extension /api/llm endpoint is working correctly!")
            return True
        else:
            print("❌ FAILED!")
            print(f"Response Text: {response.text}")
            return False
            
    except requests.exceptions.ConnectionError:
        print("❌ ERROR: Could not connect to backend server.")
        print("Make sure the backend is running on http://localhost:8000")
        return False
    except Exception as e:
        print(f"❌ ERROR: {str(e)}")
        return False

if __name__ == "__main__":
    test_llm_endpoint()

"""Quick test to verify executive agent endpoint is available."""
import requests
import os
from dotenv import load_dotenv

load_dotenv("backend/.env")

API_KEY = os.getenv("API_KEY", "test-key-123")
BASE_URL = "http://localhost:8000"

print("\n" + "="*70)
print("Testing Executive Agent Endpoints")
print("="*70)

# Test 1: Health check
print("\n1. Testing health endpoint...")
try:
    resp = requests.get(f"{BASE_URL}/health")
    print(f"   ✅ Health: {resp.status_code} - {resp.json()}")
except Exception as e:
    print(f"   ❌ Health failed: {e}")

# Test 2: Capabilities endpoint
print("\n2. Testing capabilities endpoint...")
try:
    headers = {"X-API-Key": API_KEY}
    resp = requests.get(f"{BASE_URL}/api/agent/capabilities", headers=headers)
    resp.raise_for_status()
    data = resp.json()
    print(f"   ✅ Capabilities: {resp.status_code}")
    print(f"   Agent: {data.get('agent_name', 'Unknown')}")
    print(f"   Version: {data.get('version', 'Unknown')}")
except requests.exceptions.HTTPError as e:
    print(f"   ❌ HTTP Error: {e.response.status_code} - {e.response.text}")
except Exception as e:
    print(f"   ❌ Failed: {e}")

# Test 3: Chat endpoint
print("\n3. Testing chat endpoint...")
try:
    headers = {"X-API-Key": API_KEY}
    payload = {
        "message": "Hello!",
        "session_id": "test_quick",
        "user_id": "test_user",
        "provider": "gmail"
    }
    resp = requests.post(f"{BASE_URL}/api/agent/chat", json=payload, headers=headers)
    resp.raise_for_status()
    data = resp.json()
    print(f"   ✅ Chat: {resp.status_code}")
    print(f"   Response: {data.get('message', 'No message')[:100]}")
except requests.exceptions.HTTPError as e:
    print(f"   ❌ HTTP Error: {e.response.status_code} - {e.response.text}")
except Exception as e:
    print(f"   ❌ Failed: {e}")

print("\n" + "="*70)
print("RESTART THE BACKEND to apply the changes:")
print("  1. Press Ctrl+C in the terminal running 'python backend/main.py'")
print("  2. Run: python backend/main.py")
print("  3. Then run this test again: python test_quick.py")
print("="*70 + "\n")

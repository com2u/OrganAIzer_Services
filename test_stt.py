"""
Test script for STT endpoint
"""
import requests
import sys

# Test health endpoint first
try:
    health_response = requests.get("http://localhost:8000/health")
    print(f"Health check: {health_response.status_code} - {health_response.json()}")
except Exception as e:
    print(f"Health check failed: {e}")
    sys.exit(1)

# Test STT endpoint with an empty file
try:
    print("\nTesting STT endpoint availability...")
    response = requests.post(
        "http://localhost:8000/api/stt/transcribe",
        files={"file": ("test.mp3", b"", "audio/mpeg")}
    )
    print(f"STT test response: {response.status_code}")
    print(f"Response body: {response.text}")
except Exception as e:
    print(f"STT test failed: {e}")
    import traceback
    traceback.print_exc()

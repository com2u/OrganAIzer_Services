"""
Test script for the organAIzer Executive Agent

This script demonstrates how to interact with the Executive Agent API.

Requirements:
1. Backend server must be running: python backend/main.py
2. API key must be set in backend/.env (default: test-key-123)

Usage:
    python test_executive_agent.py

Environment Variables (optional):
    BACKEND_URL - Backend base URL (default: http://localhost:8000)
    API_KEY - API key for authentication (default: test-key-123)
"""

import requests
import json
import os
from datetime import datetime
from dotenv import load_dotenv

# Load environment variables
load_dotenv("backend/.env")

# Configuration
BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000")
API_KEY = os.getenv("API_KEY", "test-key-123")
BASE_URL = f"{BACKEND_URL}/api/agent"
SESSION_ID = f"test_session_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
USER_ID = "demo_user"
PROVIDER = "gmail"


class ExecutiveAgentTester:
    """Test client for the Executive Agent."""
    
    def __init__(self, base_url, session_id, user_id, provider, api_key):
        self.base_url = base_url
        self.session_id = session_id
        self.user_id = user_id
        self.provider = provider
        self.headers = {"X-API-Key": api_key}
    
    def chat(self, message):
        """Send a chat message to the agent."""
        url = f"{self.base_url}/chat"
        payload = {
            "message": message,
            "session_id": self.session_id,
            "user_id": self.user_id,
            "provider": self.provider
        }
        
        print(f"\n{'='*70}")
        print(f"USER: {message}")
        print(f"{'='*70}")
        
        try:
            response = requests.post(url, json=payload, headers=self.headers)
            response.raise_for_status()
            data = response.json()
            
            print(f"\nAGENT: {data.get('message', 'No response')}")
            
            if data.get('data'):
                print(f"\n[Additional Data Available]")
                print(json.dumps(data['data'], indent=2)[:500])  # First 500 chars
            
            if data.get('action_needed'):
                print(f"\n⚠️  Action Needed: {data['action_needed']}")
            
            return data
            
        except requests.exceptions.RequestException as e:
            print(f"\n❌ Error: {e}")
            return None
    
    def get_session_info(self):
        """Get session information."""
        url = f"{self.base_url}/session/{self.session_id}"
        
        try:
            response = requests.get(url, headers=self.headers)
            response.raise_for_status()
            data = response.json()
            
            print(f"\n{'='*70}")
            print(f"SESSION INFO")
            print(f"{'='*70}")
            print(f"Session ID: {data['session_id']}")
            print(f"Messages: {data['message_count']}")
            print(f"Context: {json.dumps(data.get('context', {}), indent=2)}")
            print(f"Last Activity: {data['last_activity']}")
            
            return data
            
        except requests.exceptions.RequestException as e:
            print(f"\n❌ Error: {e}")
            return None
    
    def get_capabilities(self):
        """Get agent capabilities."""
        url = f"{self.base_url}/capabilities"
        
        try:
            response = requests.get(url, headers=self.headers)
            response.raise_for_status()
            data = response.json()
            
            print(f"\n{'='*70}")
            print(f"AGENT CAPABILITIES")
            print(f"{'='*70}")
            print(json.dumps(data, indent=2))
            
            return data
            
        except requests.exceptions.RequestException as e:
            print(f"\n❌ Error: {e}")
            return None
    
    def clear_session(self):
        """Clear the current session."""
        url = f"{self.base_url}/session/{self.session_id}"
        
        try:
            response = requests.delete(url, headers=self.headers)
            response.raise_for_status()
            data = response.json()
            
            print(f"\n✅ {data.get('message', 'Session cleared')}")
            
            return data
            
        except requests.exceptions.RequestException as e:
            print(f"\n❌ Error: {e}")
            return None


def run_conversation_test(tester):
    """Run a sample conversation with the agent."""
    
    print("\n" + "="*70)
    print("EXECUTIVE AGENT CONVERSATION TEST")
    print("="*70)
    print(f"Session ID: {tester.session_id}")
    print(f"User ID: {tester.user_id}")
    print(f"Provider: {tester.provider}")
    
    # Test 1: General greeting
    tester.chat("Hello! What can you help me with?")
    
    # Test 2: Email inquiry
    tester.chat("Show me my recent emails")
    
    # Test 3: Calendar inquiry
    tester.chat("What's on my calendar today?")
    
    # Test 4: Knowledge query - Geography
    tester.chat("Tell me about the history of Rome")
    
    # Test 5: Follow-up with context
    tester.chat("When did it fall?")
    
    # Test 6: Another knowledge query
    tester.chat("What's the capital of France?")
    
    # Test 7: Multimodal request
    tester.chat("Can you generate an image?")
    
    # Get session info
    tester.get_session_info()


def run_email_workflow_test(tester):
    """Test email-related workflows."""
    
    print("\n" + "="*70)
    print("EMAIL WORKFLOW TEST")
    print("="*70)
    
    tester.chat("Show me my inbox")
    tester.chat("Summarize the first email")
    tester.chat("Help me draft a reply")
    tester.chat("I want to send an email")


def run_calendar_workflow_test(tester):
    """Test calendar-related workflows."""
    
    print("\n" + "="*70)
    print("CALENDAR WORKFLOW TEST")
    print("="*70)
    
    tester.chat("What's on my calendar?")
    tester.chat("Schedule a meeting tomorrow at 2pm")
    tester.chat("Show me today's events")


def interactive_mode(tester):
    """Interactive chat mode."""
    
    print("\n" + "="*70)
    print("INTERACTIVE MODE")
    print("="*70)
    print("Type your messages to chat with the agent.")
    print("Commands: /session, /capabilities, /clear, /quit")
    print("="*70)
    
    while True:
        try:
            user_input = input("\nYou: ").strip()
            
            if not user_input:
                continue
            
            if user_input.lower() == '/quit':
                print("\nGoodbye! 👋")
                break
            elif user_input.lower() == '/session':
                tester.get_session_info()
            elif user_input.lower() == '/capabilities':
                tester.get_capabilities()
            elif user_input.lower() == '/clear':
                tester.clear_session()
            else:
                tester.chat(user_input)
                
        except KeyboardInterrupt:
            print("\n\nGoodbye! 👋")
            break
        except Exception as e:
            print(f"\n❌ Error: {e}")


def main():
    """Main test runner."""
    
    print("\n" + "="*70)
    print("organAIzer Executive Agent - Test Suite")
    print("="*70)
    print("\nMake sure the backend server is running on http://localhost:8000")
    print("Start it with: python backend/main.py")
    
    # Initialize tester
    tester = ExecutiveAgentTester(BASE_URL, SESSION_ID, USER_ID, PROVIDER, API_KEY)
    
    # Check if server is running
    try:
        headers = {"X-API-Key": API_KEY}
        response = requests.get(f"{BASE_URL}/capabilities", headers=headers)
        response.raise_for_status()
        print("\n✅ Backend server is running!")
    except requests.exceptions.RequestException as e:
        print("\n❌ Backend server is not running!")
        print(f"Error: {e}")
        print("Please start it with: python backend/main.py")
        return
    
    # Menu
    while True:
        print("\n" + "="*70)
        print("TEST MENU")
        print("="*70)
        print("1. Run Conversation Test (automated)")
        print("2. Run Email Workflow Test")
        print("3. Run Calendar Workflow Test")
        print("4. Interactive Chat Mode")
        print("5. Get Agent Capabilities")
        print("6. Get Session Info")
        print("7. Clear Session")
        print("0. Exit")
        print("="*70)
        
        choice = input("\nSelect option: ").strip()
        
        if choice == '1':
            run_conversation_test(tester)
        elif choice == '2':
            run_email_workflow_test(tester)
        elif choice == '3':
            run_calendar_workflow_test(tester)
        elif choice == '4':
            interactive_mode(tester)
        elif choice == '5':
            tester.get_capabilities()
        elif choice == '6':
            tester.get_session_info()
        elif choice == '7':
            tester.clear_session()
        elif choice == '0':
            print("\nGoodbye! 👋")
            break
        else:
            print("\n❌ Invalid option. Please try again.")


if __name__ == "__main__":
    main()

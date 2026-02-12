#!/usr/bin/env python3
"""
Calendar Event Creation Test Script

Tests end-to-end calendar event creation for both Google and Outlook providers.

Usage:
    python scripts/test_calendar.py

Environment Variables Required:
    BASE_URL - Backend API URL (default: http://localhost:8000)
    API_KEY - API key for authentication
    USER_ID - User identifier (default: default_user)
    PROVIDER - Calendar provider: google or outlook (default: google)
"""

import os
import sys
import requests
from datetime import datetime, timedelta
import json

# Configuration from environment
BASE_URL = os.getenv("BASE_URL", "http://localhost:8000")
API_KEY = os.getenv("API_KEY")
USER_ID = os.getenv("USER_ID", "default_user")
PROVIDER = os.getenv("PROVIDER", "google").lower()

# Colors for terminal output
class Colors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKCYAN = '\033[96m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'


def print_header(text):
    print(f"\n{Colors.HEADER}{Colors.BOLD}{'='*70}{Colors.ENDC}")
    print(f"{Colors.HEADER}{Colors.BOLD}{text}{Colors.ENDC}")
    print(f"{Colors.HEADER}{Colors.BOLD}{'='*70}{Colors.ENDC}\n")


def print_success(text):
    print(f"{Colors.OKGREEN}✅ {text}{Colors.ENDC}")


def print_error(text):
    print(f"{Colors.FAIL}❌ {text}{Colors.ENDC}")


def print_warning(text):
    print(f"{Colors.WARNING}⚠️  {text}{Colors.ENDC}")


def print_info(text):
    print(f"{Colors.OKCYAN}ℹ️  {text}{Colors.ENDC}")


def create_calendar_event(provider: str = "google"):
    """
    Create a test calendar event.
    
    Args:
        provider: Calendar provider (google or outlook)
    
    Returns:
        Response dict or None on failure
    """
    # Calculate test event time (tomorrow at 2 PM, 1 hour duration)
    tomorrow = datetime.now() + timedelta(days=1)
    start_time = tomorrow.replace(hour=14, minute=0, second=0, microsecond=0)
    end_time = start_time + timedelta(hours=1)
    
    # Prepare event data
    event_data = {
        "summary": f"OrganAIzer Test Event ({provider.title()})",
        "description": f"This is a test event created by test_calendar.py to verify {provider} calendar integration.",
        "location": "Test Location",
        "start": start_time.strftime("%Y-%m-%dT%H:%M:%S") + "Z",
        "end": end_time.strftime("%Y-%m-%dT%H:%M:%S") + "Z",
        "timezone": "UTC",
        "dry_run": False,
        "confirm": True
    }
    
    print_info(f"Creating test event on {provider} calendar...")
    print_info(f"  Title: {event_data['summary']}")
    print_info(f"  Start: {start_time.strftime('%Y-%m-%d %H:%M UTC')}")
    print_info(f"  End: {end_time.strftime('%Y-%m-%d %H:%M UTC')}")
    
    # Make API request
    url = f"{BASE_URL}/api/calendar/create"
    headers = {}
    if API_KEY:
        headers["X-API-Key"] = API_KEY
    
    params = {
        "provider": provider,
        "user_id": USER_ID
    }
    
    try:
        response = requests.post(
            url,
            json=event_data,
            headers=headers,
            params=params,
            timeout=30
        )
        
        print_info(f"Response Status: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            print_success(f"Event created successfully!")
            print_info(f"Response: {json.dumps(result, indent=2)}")
            return result
        else:
            print_error(f"Failed to create event: {response.status_code}")
            print_error(f"Response: {response.text}")
            return None
            
    except requests.exceptions.Timeout:
        print_error("Request timed out after 30 seconds")
        return None
    except requests.exceptions.ConnectionError:
        print_error(f"Could not connect to {BASE_URL}")
        print_warning("Is the backend server running?")
        return None
    except Exception as e:
        print_error(f"Unexpected error: {str(e)}")
        return None


def list_calendar_events(provider: str = "google"):
    """
    List calendar events to verify the created event appears.
    
    Args:
        provider: Calendar provider (google or outlook)
    
    Returns:
        List of events or None on failure
    """
    print_info(f"Listing events from {provider} calendar...")
    
    url = f"{BASE_URL}/api/calendar/events"
    headers = {}
    if API_KEY:
        headers["X-API-Key"] = API_KEY
    
    params = {
        "provider": provider,
        "user_id": USER_ID,
        "limit": 10
    }
    
    try:
        response = requests.get(
            url,
            headers=headers,
            params=params,
            timeout=15
        )
        
        if response.status_code == 200:
            result = response.json()
            events = result.get("events", [])
            print_success(f"Found {len(events)} events")
            
            for i, event in enumerate(events[:5], 1):
                print_info(f"  {i}. {event.get('summary', 'No title')} - {event.get('start', 'No date')}")
            
            return events
        else:
            print_warning(f"Could not list events: {response.status_code}")
            print_warning(f"Response: {response.text}")
            return None
            
    except Exception as e:
        print_warning(f"Error listing events: {str(e)}")
        return None


def main():
    """Main test execution."""
    print_header("OrganAIzer Calendar Event Creation Test")
    
    # Validate configuration
    print_info("Configuration:")
    print_info(f"  BASE_URL: {BASE_URL}")
    print_info(f"  API_KEY: {'***' if API_KEY else 'Not set'}")
    print_info(f"  USER_ID: {USER_ID}")
    print_info(f"  PROVIDER: {PROVIDER}")
    print()
    
    if not API_KEY:
        print_warning("API_KEY not set - request may fail if authentication is required")
        print_warning("Set via: export API_KEY=your_api_key")
        print()
    
    if PROVIDER not in ["google", "outlook"]:
        print_error(f"Invalid PROVIDER: {PROVIDER}")
        print_error("Valid options: google, outlook")
        sys.exit(1)
    
    # Test 1: Create event
    print_header(f"Test 1: Create Calendar Event ({PROVIDER})")
    result = create_calendar_event(PROVIDER)
    
    if not result:
        print_error("Calendar event creation FAILED")
        sys.exit(1)
    
    # Check for success indicators
    if result.get("status") == "success":
        print_success("✅ Event creation returned success status")
    elif result.get("event_id"):
        print_success("✅ Event ID received (event created)")
    else:
        print_warning("⚠️  Status unclear - check response above")
    
    # Test 2: List events (optional verification)
    print_header(f"Test 2: List Events (Verification)")
    events = list_calendar_events(PROVIDER)
    
    if events:
        # Search for our test event
        test_event_found = any(
            "OrganAIzer Test Event" in event.get("summary", "")
            for event in events
        )
        
        if test_event_found:
            print_success("✅ Test event found in calendar!")
        else:
            print_warning("⚠️  Test event not found in list (may take a moment to appear)")
    
    # Final summary
    print_header("Test Summary")
    print_success(f"Calendar event creation test PASSED for {PROVIDER}")
    print_info("The event should now appear in your calendar.")
    print_info(f"Provider: {PROVIDER.title()} Calendar")
    print_info(f"User: {USER_ID}")
    
    sys.exit(0)


if __name__ == "__main__":
    main()

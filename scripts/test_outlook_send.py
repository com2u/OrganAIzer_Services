#!/usr/bin/env python3
"""
Outlook Email Send Test Script

Tests end-to-end Outlook email sending through the Executive Agent.

Usage:
    python scripts/test_outlook_send.py

Environment Variables Required:
    BASE_URL - Backend API URL (default: http://localhost:8000)
    API_KEY - API key for authentication
    USER_ID - User identifier (default: default_user)
    TEST_RECIPIENT - Test email recipient address
"""

import os
import sys
import requests
import json

# Configuration from environment
BASE_URL = os.getenv("BASE_URL", "http://localhost:8000")
API_KEY = os.getenv("API_KEY")
USER_ID = os.getenv("USER_ID", "default_user")
TEST_RECIPIENT = os.getenv("TEST_RECIPIENT")

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


def check_outlook_status():
    """
    Check Outlook OAuth and API status.
    
    Returns:
        Status dict or None on failure
    """
    print_info("Checking Outlook connection status...")
    
    url = f"{BASE_URL}/api/outlook-health/status"
    headers = {}
    if API_KEY:
        headers["X-API-Key"] = API_KEY
    
    params = {
        "user_id": USER_ID
    }
    
    try:
        response = requests.get(
            url,
            headers=headers,
            params=params,
            timeout=15
        )
        
        if response.status_code == 200:
            status = response.json()
            
            # Display key status info
            if status.get("status") == "connected":
                print_success("Outlook is connected!")
                
                # Check capabilities
                caps = status.get("capabilities", {})
                if caps.get("can_send_email"):
                    print_success("  ✅ Can send email")
                else:
                    print_error("  ❌ Cannot send email (missing scopes or API error)")
                
                if caps.get("can_read_email"):
                    print_success("  ✅ Can read email")
                
                # Check API connectivity
                api_conn = status.get("api_connectivity", {})
                if api_conn.get("status") == "success":
                    print_success(f"  ✅ API connectivity verified (email: {api_conn.get('email')})")
                else:
                    print_warning(f"  ⚠️  API test failed: {api_conn.get('error')}")
                
                return status
            else:
                print_error("Outlook is NOT connected")
                print_warning(f"Message: {status.get('message')}")
                return None
        else:
            print_error(f"Status check failed: {response.status_code}")
            print_error(f"Response: {response.text}")
            return None
            
    except Exception as e:
        print_error(f"Error checking status: {str(e)}")
        return None


def test_outlook_send_dry_run():
    """
    Test Outlook email sending in dry-run mode (no actual send).
    
    Returns:
        Response dict or None on failure
    """
    if not TEST_RECIPIENT:
        print_warning("TEST_RECIPIENT not set - skipping dry-run test")
        print_info("Set via: export TEST_RECIPIENT=your@email.com")
        return None
    
    print_info(f"Testing Outlook send (dry-run) to {TEST_RECIPIENT}...")
    
    url = f"{BASE_URL}/api/outlook-health/test-send"
    headers = {}
    if API_KEY:
        headers["X-API-Key"] = API_KEY
    
    params = {
        "user_id": USER_ID,
        "to_email": TEST_RECIPIENT
    }
    
    try:
        response = requests.post(
            url,
            headers=headers,
            params=params,
            timeout=15
        )
        
        if response.status_code == 200:
            result = response.json()
            
            if result.get("status") == "success":
                print_success("Dry-run test PASSED")
                print_info(f"Response: {json.dumps(result, indent=2)}")
                return result
            else:
                print_error(f"Dry-run test FAILED: {result.get('message')}")
                return None
        else:
            print_error(f"Test failed: {response.status_code}")
            print_error(f"Response: {response.text}")
            return None
            
    except Exception as e:
        print_error(f"Error during dry-run test: {str(e)}")
        return None


def send_test_email_via_agent():
    """
    Send a test email using the Executive Agent (actual send).
    
    Returns:
        Response dict or None on failure
    """
    if not TEST_RECIPIENT:
        print_error("TEST_RECIPIENT not set - cannot send email")
        print_info("Set via: export TEST_RECIPIENT=your@email.com")
        return None
    
    print_info(f"Sending test email to {TEST_RECIPIENT} via Executive Agent...")
    
    # Use the Executive Agent to send email
    url = f"{BASE_URL}/api/agent/chat"
    headers = {
        "Content-Type": "application/json"
    }
    if API_KEY:
        headers["X-API-Key"] = API_KEY
    
    # Agent request to send email
    payload = {
        "message": f"Send an email to {TEST_RECIPIENT} with subject 'OrganAIzer Outlook Test' and body 'This is a test email sent through OrganAIzer to verify Outlook integration. If you received this, the integration is working!'",
        "session_id": f"test_outlook_send_{USER_ID}",
        "user_id": USER_ID,
        "provider": "outlook"
    }
    
    try:
        response = requests.post(
            url,
            json=payload,
            headers=headers,
            timeout=30
        )
        
        print_info(f"Response Status: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            
            # Check if agent processed the request
            if result.get("success"):
                agent_message = result.get("message", "")
                print_success("Agent processed request")
                print_info(f"Agent response: {agent_message}")
                
                # Check if email was actually sent
                if "sent" in agent_message.lower() or "✅" in agent_message:
                    print_success("✅ EMAIL SENT SUCCESSFULLY!")
                    return result
                elif "confirm" in agent_message.lower() or "draft" in agent_message.lower():
                    print_warning("⚠️  Agent created draft - requires confirmation")
                    print_info("The agent may be waiting for user confirmation")
                    return result
                else:
                    print_warning("⚠️  Email status unclear from agent response")
                    return result
            else:
                print_error("Agent request failed")
                print_error(f"Error: {result.get('error')}")
                return None
        else:
            print_error(f"Request failed: {response.status_code}")
            print_error(f"Response: {response.text}")
            return None
            
    except Exception as e:
        print_error(f"Error sending email: {str(e)}")
        return None


def main():
    """Main test execution."""
    print_header("OrganAIzer Outlook Email Send Test")
    
    # Validate configuration
    print_info("Configuration:")
    print_info(f"  BASE_URL: {BASE_URL}")
    print_info(f"  API_KEY: {'***' if API_KEY else 'Not set'}")
    print_info(f"  USER_ID: {USER_ID}")
    print_info(f"  TEST_RECIPIENT: {TEST_RECIPIENT or 'Not set'}")
    print()
    
    if not API_KEY:
        print_warning("API_KEY not set - requests may fail if authentication is required")
        print_warning("Set via: export API_KEY=your_api_key")
        print()
    
    if not TEST_RECIPIENT:
        print_error("TEST_RECIPIENT not set - cannot send test emails")
        print_error("Set via: export TEST_RECIPIENT=your@email.com")
        print_error("\nAborting tests.")
        sys.exit(1)
    
    # Test 1: Check Outlook status
    print_header("Test 1: Check Outlook Connection Status")
    status = check_outlook_status()
    
    if not status:
        print_error("Outlook is not connected or status check failed")
        print_error("\nPlease connect your Outlook account first:")
        print_info(f"Visit: {BASE_URL}/api/integrations/microsoft/auth/start?user_id={USER_ID}")
        sys.exit(1)
    
    # Check if can send email
    if not status.get("capabilities", {}).get("can_send_email"):
        print_error("Outlook cannot send emails (missing scopes or API error)")
        print_error("\nPlease re-authenticate with correct scopes:")
        print_info(f"Visit: {BASE_URL}/api/integrations/microsoft/auth/start?user_id={USER_ID}")
        sys.exit(1)
    
    # Test 2: Dry-run test
    print_header("Test 2: Outlook Send (Dry-Run)")
    dry_run_result = test_outlook_send_dry_run()
    
    if not dry_run_result:
        print_warning("Dry-run test failed - proceeding with caution...")
    else:
        print_success("✅ Dry-run test passed!")
    
    # Test 3: Actual send via Executive Agent
    print_header("Test 3: Send Email via Executive Agent")
    print_warning("⚠️  This will send an ACTUAL email!")
    print_info(f"Recipient: {TEST_RECIPIENT}")
    print_info("Subject: OrganAIzer Outlook Test")
    print()
    
    # Prompt for confirmation
    try:
        confirm = input("Continue? (yes/no): ").strip().lower()
        if confirm not in ["yes", "y"]:
            print_info("Test cancelled by user")
            sys.exit(0)
    except KeyboardInterrupt:
        print("\n\nTest cancelled by user")
        sys.exit(0)
    
    send_result = send_test_email_via_agent()
    
    if not send_result:
        print_error("Email send test FAILED")
        sys.exit(1)
    
    # Final summary
    print_header("Test Summary")
    print_success("Outlook email send test COMPLETED")
    print_info("Check the following:")
    print_info(f"  1. Check {TEST_RECIPIENT} inbox for test email")
    print_info("  2. Verify email was sent from Outlook account")
    print_info("  3. Check agent response for confirmation")
    print()
    print_success("If you received the email, Outlook integration is working! ✅")
    
    sys.exit(0)


if __name__ == "__main__":
    main()

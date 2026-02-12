"""
Google OAuth Reconnect Test & Diagnostic Script

This script helps diagnose and test the Google OAuth reconnect flow.
Use this after changing OAuth client credentials or scopes.

Usage:
    python test_google_oauth_reconnect.py
"""

import os
import sys
import requests
from dotenv import load_dotenv

# Load environment variables
load_dotenv("backend/.env")

BASE_URL = "http://localhost:8000"
USER_ID = "default_user"


def print_section(title):
    """Print a section header."""
    print("\n" + "="*70)
    print(f"  {title}")
    print("="*70)


def test_oauth_config():
    """Test that OAuth configuration is loaded."""
    print_section("Step 1: Verify OAuth Configuration")
    
    client_id = os.getenv("GOOGLE_CLIENT_ID")
    client_secret = os.getenv("GOOGLE_CLIENT_SECRET")
    redirect_uri = os.getenv("GOOGLE_REDIRECT_URI", "http://localhost:8000/api/integrations/google/auth/callback")
    
    print(f"✓ GOOGLE_CLIENT_ID: {'✅ SET' if client_id else '❌ MISSING'}")
    if client_id:
        print(f"  Value: {client_id[:20]}...{client_id[-10:]}")
    
    print(f"✓ GOOGLE_CLIENT_SECRET: {'✅ SET' if client_secret else '❌ MISSING'}")
    if client_secret:
        print(f"  Value: {client_secret[:10]}...***")
    
    print(f"✓ GOOGLE_REDIRECT_URI: {redirect_uri}")
    
    if not client_id or not client_secret:
        print("\n❌ ERROR: Missing OAuth credentials in .env file")
        return False
    
    return True


def test_scopes():
    """Test scope configuration."""
    print_section("Step 2: Verify Scope Configuration")
    
    try:
        # Import scopes
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))
        from config.google_scopes import GOOGLE_SCOPES, CURRENT_SCOPE_HASH
        
        print(f"✓ Scopes loaded: {len(GOOGLE_SCOPES)} scopes")
        print(f"✓ Scope hash: {CURRENT_SCOPE_HASH}")
        print(f"\nConfigured scopes:")
        for i, scope in enumerate(GOOGLE_SCOPES, 1):
            print(f"  {i}. {scope}")
        
        # Check for required scopes
        required_scopes = [
            'https://www.googleapis.com/auth/gmail.readonly',
            'https://www.googleapis.com/auth/gmail.send',
            'https://www.googleapis.com/auth/gmail.modify',
            'https://www.googleapis.com/auth/calendar.events',
            'https://www.googleapis.com/auth/userinfo.email',
            'openid'
        ]
        
        print(f"\n✓ Required scope check:")
        for scope in required_scopes:
            present = scope in GOOGLE_SCOPES
            print(f"  {scope}: {'✅' if present else '❌'}")
        
        return True
    except Exception as e:
        print(f"❌ Error loading scopes: {e}")
        return False


def test_backend_running():
    """Test if backend is running."""
    print_section("Step 3: Verify Backend is Running")
    
    try:
        response = requests.get(f"{BASE_URL}/health", timeout=5)
        if response.status_code == 200:
            print(f"✅ Backend is running at {BASE_URL}")
            print(f"  Response: {response.json()}")
            return True
        else:
            print(f"❌ Backend returned status {response.status_code}")
            return False
    except requests.exceptions.ConnectionError:
        print(f"❌ Cannot connect to backend at {BASE_URL}")
        print(f"   Make sure to start the backend first:")
        print(f"   cd backend && python main.py")
        return False
    except Exception as e:
        print(f"❌ Error: {e}")
        return False


def test_google_connection_status():
    """Check current Google connection status."""
    print_section("Step 4: Check Google Connection Status")
    
    try:
        response = requests.get(
            f"{BASE_URL}/api/integrations/status",
            params={"user_id": USER_ID},
            timeout=5
        )
        
        if response.status_code == 200:
            data = response.json()
            google = data.get("google", {})
            connected = google.get("connected", False)
            scopes = google.get("scopes", [])
            
            print(f"✓ Connection status: {'✅ CONNECTED' if connected else '❌ NOT CONNECTED'}")
            
            if connected:
                print(f"✓ Granted scopes: {len(scopes)} scopes")
                for i, scope in enumerate(scopes, 1):
                    print(f"  {i}. {scope}")
            else:
                print(f"  No active Google connection for user '{USER_ID}'")
            
            return connected
        else:
            print(f"❌ Status check failed: {response.status_code}")
            print(f"  Response: {response.text}")
            return None
    except Exception as e:
        print(f"❌ Error checking status: {e}")
        return None


def disconnect_google():
    """Disconnect Google account."""
    print_section("Step 5: Disconnect Google Account")
    
    print(f"Disconnecting Google for user '{USER_ID}'...")
    
    try:
        response = requests.delete(
            f"{BASE_URL}/api/integrations/google/disconnect",
            params={"user_id": USER_ID},
            timeout=10
        )
        
        if response.status_code == 200:
            print(f"✅ Successfully disconnected Google account")
            print(f"  Response: {response.json()}")
            return True
        elif response.status_code == 404:
            print(f"✓ No Google connection found (already disconnected)")
            return True
        else:
            print(f"❌ Disconnect failed: {response.status_code}")
            print(f"  Response: {response.text}")
            return False
    except Exception as e:
        print(f"❌ Error disconnecting: {e}")
        return False


def show_reconnect_instructions():
    """Show instructions for reconnecting."""
    print_section("Step 6: Reconnect Instructions")
    
    auth_start_url = f"{BASE_URL}/api/integrations/google/auth/start?user_id={USER_ID}"
    
    print(f"To reconnect Google with the updated scopes:")
    print(f"\n1. Open this URL in your browser:")
    print(f"   {auth_start_url}")
    print(f"\n2. Sign in with your Google account")
    print(f"\n3. Grant all requested permissions:")
    print(f"   - Gmail (read, send, modify)")
    print(f"   - Google Calendar (events)")
    print(f"   - User email info")
    print(f"\n4. After successful authorization, you'll see a success message")
    print(f"\n5. Run this script again to verify the connection")


def main():
    """Run all diagnostic tests."""
    print("\n" + "🔧 Google OAuth Reconnect Diagnostic Tool")
    print("="*70)
    
    # Step 1: Check OAuth config
    if not test_oauth_config():
        print("\n❌ FAILED: Fix .env configuration first")
        return
    
    # Step 2: Check scopes
    if not test_scopes():
        print("\n❌ FAILED: Scope configuration error")
        return
    
    # Step 3: Check backend
    if not test_backend_running():
        print("\n❌ FAILED: Start the backend first")
        return
    
    # Step 4: Check current status
    connected = test_google_connection_status()
    
    # Step 5: Offer to disconnect
    if connected:
        print_section("Disconnect Current Connection?")
        print(f"The Google account is currently connected.")
        print(f"To reconnect with updated scopes, you should disconnect first.")
        
        choice = input(f"\nDisconnect Google for user '{USER_ID}'? (y/N): ").strip().lower()
        
        if choice == 'y':
            if disconnect_google():
                show_reconnect_instructions()
            else:
                print("\n❌ Disconnect failed")
        else:
            print("\n✓ Skipping disconnect")
    else:
        # Not connected, show connect instructions
        show_reconnect_instructions()
    
    print("\n" + "="*70)
    print("✅ Diagnostic complete")
    print("="*70 + "\n")


if __name__ == "__main__":
    main()

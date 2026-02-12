"""
Comprehensive Test Script for OrganAIzer Features

Tests all features after API key change to verify functionality.
"""

import asyncio
import sys
import os
from datetime import datetime, timedelta

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))

from services.executive_agent_service import ExecutiveAgent


async def test_conversation():
    """Test basic conversational AI (uses OpenRouter)."""
    print("\n" + "="*70)
    print("TEST 1: CONVERSATIONAL AI (OpenRouter)")
    print("="*70)
    
    try:
        agent = ExecutiveAgent(session_id="test_session")
        response = await agent.process_message("Hello, what can you do?")
        
        print(f"✅ Response: {response.get('message', '')[:200]}...")
        print(f"✅ Success: {response.get('success', False)}")
        return True
    except Exception as e:
        print(f"❌ FAILED: {e}")
        return False


async def test_calendar_creation():
    """Test calendar event creation (Google Calendar or Outlook)."""
    print("\n" + "="*70)
    print("TEST 2: CALENDAR EVENT CREATION")
    print("="*70)
    
    try:
        agent = ExecutiveAgent(session_id="test_calendar")
        
        # Step 1: Request event creation
        print("\n📅 Step 1: Request event creation...")
        response1 = await agent.process_message(
            "Add meeting tomorrow at 2pm called Test Meeting"
        )
        print(f"Agent: {response1.get('message', '')[:300]}")
        
        # Step 2: Confirm
        print("\n📅 Step 2: Confirm event...")
        response2 = await agent.process_message("yes")
        print(f"Agent: {response2.get('message', '')[:300]}")
        
        # Check if event was actually created
        if response2.get('event_created'):
            print(f"✅ Event created with ID: {response2.get('event_id', 'N/A')}")
            return True
        elif "not connected" in response2.get('message', '').lower():
            print("⚠️ OAuth not connected - need to authorize Google/Microsoft first")
            print("   Visit: http://localhost:8000/api/integrations/google/auth")
            return False
        else:
            print(f"⚠️ Event creation status unclear")
            print(f"   Response: {response2}")
            return False
            
    except Exception as e:
        print(f"❌ FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_email_draft():
    """Test email drafting (Gmail or Outlook)."""
    print("\n" + "="*70)
    print("TEST 3: EMAIL DRAFTING")
    print("="*70)
    
    try:
        agent = ExecutiveAgent(session_id="test_email")
        
        # Step 1: Request draft
        print("\n📧 Step 1: Request draft...")
        response1 = await agent.process_message(
            "Draft email to test@example.com about project update"
        )
        print(f"Agent: {response1.get('message', '')[:300]}")
        
        # Step 2: Provide body
        print("\n📧 Step 2: Provide email body...")
        response2 = await agent.process_message(
            "The project is on track and we expect to complete by next week"
        )
        print(f"Agent: {response2.get('message', '')[:400]}")
        
        # Check if draft is ready
        if response2.get('draft_ready'):
            print(f"✅ Draft created successfully")
            print(f"   Pending confirmation: {response2.get('pending_confirmation', False)}")
            return True
        else:
            print(f"⚠️ Draft not ready yet")
            return False
            
    except Exception as e:
        print(f"❌ FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_image_generation():
    """Test image generation (Gemini or Vertex AI)."""
    print("\n" + "="*70)
    print("TEST 4: IMAGE GENERATION")
    print("="*70)
    
    try:
        from services.nano_banana_service import get_nano_banana_service
        
        service = get_nano_banana_service()
        print(f"✅ Nano Banana service initialized")
        print(f"   API Key configured: {service.api_key[:20]}...")
        
        # Try to generate an image
        print("\n🍌 Attempting to generate image...")
        images = await service.generate_images("sunset over mountains", num_images=1)
        
        print(f"✅ Service returned {len(images)} image(s)")
        
        # Check if actual images or placeholders
        if images and "error" in images[0]:
            print(f"⚠️ WARNING: {images[0]['error']}")
            print("\n   RECOMMENDATION:")
            print("   Gemini 2.0 Flash Exp does NOT support image generation.")
            print("   Please use Vertex AI Imagen instead:")
            print("   1. Set GOOGLE_CLOUD_PROJECT in .env")
            print("   2. Configure GCP service account credentials")
            return False
        else:
            print(f"✅ Image generated successfully: {images[0]['image_id']}")
            return True
            
    except Exception as e:
        print(f"❌ FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_oauth_status():
    """Check OAuth token status."""
    print("\n" + "="*70)
    print("TEST 5: OAUTH TOKEN STATUS")
    print("="*70)
    
    import os
    from pathlib import Path
    
    tokens_dir = Path("backend/tokens")
    
    if not tokens_dir.exists():
        print("⚠️  Tokens directory does not exist: backend/tokens")
        print("   OAuth is NOT connected")
        return False
    
    # Check for token files
    google_tokens = list(tokens_dir.glob("google_*.json"))
    microsoft_tokens = list(tokens_dir.glob("microsoft_*.json") or tokens_dir.glob("outlook_*.json"))
    
    print(f"\n📁 Token files found:")
    print(f"   Google: {len(google_tokens)} file(s)")
    for token_file in google_tokens:
        print(f"      - {token_file.name}")
    
    print(f"   Microsoft: {len(microsoft_tokens)} file(s)")
    for token_file in microsoft_tokens:
        print(f"      - {token_file.name}")
    
    if google_tokens or microsoft_tokens:
        print(f"\n✅ OAuth tokens found - calendar and email should work")
        return True
    else:
        print(f"\n⚠️  NO OAuth tokens found")
        print(f"   To connect accounts:")
        print(f"   1. Start backend: python backend/main.py")
        print(f"   2. Visit: http://localhost:8000/api/integrations/google/auth")
        print(f"   3. Visit: http://localhost:8000/api/integrations/microsoft/auth")
        return False


async def test_action_history():
    """Test action history recording."""
    print("\n" + "="*70)
    print("TEST 6: ACTION HISTORY RECORDING")
    print("="*70)
    
    try:
        agent = ExecutiveAgent(session_id="test_history")
        
        # Manually record a test action
        agent.memory.record_action(
            action_type="test_action",
            outcome="TEST_SUCCESS",
            details={"test": "This is a test action"}
        )
        
        # Verify it was recorded
        last_action = agent.memory.get_last_action()
        
        if last_action and last_action['action_type'] == 'test_action':
            print(f"✅ Action history working correctly")
            print(f"   Last action: {last_action}")
            return True
        else:
            print(f"❌ Action history not working")
            return False
            
    except Exception as e:
        print(f"❌ FAILED: {e}")
        return False


async def main():
    """Run all tests."""
    print("\n" + "="*70)
    print("ORGANIZER COMPREHENSIVE FEATURE TEST")
    print("="*70)
    print(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Purpose: Verify all features after API key change")
    print("="*70)
    
    results = {}
    
    # Test 1: Conversational AI
    results['conversation'] = await test_conversation()
    
    # Test 2: OAuth Status
    results['oauth'] = await test_oauth_status()
    
    # Test 3: Email Drafting
    results['email'] = await test_email_draft()
    
    # Test 4: Calendar Creation
    results['calendar'] = await test_calendar_creation()
    
    # Test 5: Image Generation
    results['images'] = await test_image_generation()
    
    # Test 6: Action History
    results['history'] = await test_action_history()
    
    # Summary
    print("\n" + "="*70)
    print("TEST SUMMARY")
    print("="*70)
    
    for test_name, result in results.items():
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status} - {test_name.upper()}")
    
    total = len(results)
    passed = sum(1 for r in results.values() if r)
    
    print("="*70)
    print(f"Total: {passed}/{total} tests passed ({passed/total*100:.0f}%)")
    print("="*70)
    
    # Recommendations
    print("\n📋 RECOMMENDATIONS:")
    
    if not results['oauth']:
        print("1. ⚠️  Connect OAuth accounts for email and calendar features")
        print("   - Visit: http://localhost:8000/api/integrations/google/auth")
        print("   - Visit: http://localhost:8000/api/integrations/microsoft/auth")
    
    if not results['images']:
        print("2. ⚠️  Configure Vertex AI Imagen for image generation")
        print("   - Add GOOGLE_CLOUD_PROJECT to .env")
        print("   - Set up GCP service account credentials")
    
    if results['conversation'] and results['history']:
        print("\n✅ Core AI functionality is working correctly")
    
    if results['oauth'] and (results['email'] or results['calendar']):
        print("✅ Email and Calendar integration is functional")
    
    print("\n" + "="*70)


if __name__ == "__main__":
    asyncio.run(main())

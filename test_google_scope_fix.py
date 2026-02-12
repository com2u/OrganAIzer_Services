"""
Test script for Google OAuth scope_changed error handling.

This script simulates the scope change scenario and validates the fix.
"""

import sys
import os

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))

def test_scope_hash_generation():
    """Test that scope hash is generated correctly."""
    print("=" * 60)
    print("TEST 1: Scope Hash Generation")
    print("=" * 60)
    
    try:
        from config.google_scopes import (
            GOOGLE_SCOPES, 
            CURRENT_SCOPE_HASH, 
            compute_scope_hash,
            validate_token_scopes
        )
        
        print(f"✓ Canonical scopes loaded: {len(GOOGLE_SCOPES)} scopes")
        print(f"  Scopes: {GOOGLE_SCOPES}")
        print(f"\n✓ Current scope hash: {CURRENT_SCOPE_HASH}")
        
        # Test hash consistency
        hash1 = compute_scope_hash(GOOGLE_SCOPES)
        hash2 = compute_scope_hash(GOOGLE_SCOPES)
        
        if hash1 == hash2:
            print(f"✓ Hash is consistent: {hash1}")
        else:
            print(f"✗ Hash inconsistency detected!")
            return False
        
        # Test with old scopes (simulating calendar.events only)
        old_scopes = sorted([
            'openid',
            'https://www.googleapis.com/auth/userinfo.email',
            'https://www.googleapis.com/auth/calendar.events',  # Only events, not full calendar
            'https://www.googleapis.com/auth/gmail.readonly',
            'https://www.googleapis.com/auth/gmail.modify',
            'https://www.googleapis.com/auth/gmail.send'
        ])
        
        old_hash = compute_scope_hash(old_scopes)
        print(f"\n✓ Old scope hash (events only): {old_hash}")
        
        if old_hash != CURRENT_SCOPE_HASH:
            print(f"✓ Hash mismatch detected correctly!")
            print(f"  Old: {old_hash}")
            print(f"  New: {CURRENT_SCOPE_HASH}")
        else:
            print(f"✗ Expected hash mismatch but hashes match!")
            return False
        
        # Test scope validation
        is_valid, missing = validate_token_scopes(GOOGLE_SCOPES)
        print(f"\n✓ Full scope validation: valid={is_valid}, missing={missing}")
        
        is_valid, missing = validate_token_scopes(old_scopes)
        print(f"✓ Old scope validation: valid={is_valid}, missing={missing}")
        
        if not is_valid and 'https://www.googleapis.com/auth/calendar' in missing:
            print(f"✓ Correctly detected missing 'calendar' scope")
        
        print("\n" + "=" * 60)
        print("TEST 1: PASSED ✓")
        print("=" * 60 + "\n")
        return True
        
    except Exception as e:
        print(f"✗ TEST 1 FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_scope_changed_error():
    """Test that ScopeChangedError is raised correctly."""
    print("=" * 60)
    print("TEST 2: Scope Changed Error Detection")
    print("=" * 60)
    
    try:
        from utils.token_storage import TokenStorage, ScopeChangedError
        from config.google_scopes import CURRENT_SCOPE_HASH, compute_scope_hash
        import tempfile
        import shutil
        
        # Create temporary storage directory
        temp_dir = tempfile.mkdtemp()
        print(f"✓ Created temp storage: {temp_dir}")
        
        try:
            # Create a custom TokenStorage with temp directory
            storage = TokenStorage()
            original_dir = storage.storage_dir
            storage.storage_dir = tempfile.mkdtemp()
            
            # Simulate old scopes (missing calendar scope)
            old_scopes = sorted([
                'openid',
                'https://www.googleapis.com/auth/userinfo.email',
                'https://www.googleapis.com/auth/calendar.events',
                'https://www.googleapis.com/auth/gmail.readonly',
                'https://www.googleapis.com/auth/gmail.modify',
                'https://www.googleapis.com/auth/gmail.send'
            ])
            old_hash = compute_scope_hash(old_scopes)
            
            # Save tokens with old scope hash
            test_user = "test_user_scope_change"
            old_tokens = {
                "access_token": "fake_token",
                "refresh_token": "fake_refresh",
                "scopes": old_scopes,
                "scope_hash": old_hash  # Old hash
            }
            
            storage.save_tokens(test_user, "google", old_tokens)
            print(f"✓ Saved tokens with old scope hash: {old_hash}")
            
            # Try to load tokens with validation (should raise ScopeChangedError)
            try:
                storage.load_tokens(
                    test_user, 
                    "google", 
                    validate_scope_hash=True
                )
                print(f"✗ ScopeChangedError was NOT raised!")
                return False
                
            except ScopeChangedError as e:
                print(f"✓ ScopeChangedError raised correctly!")
                print(f"  Message: {e}")
                print(f"  Old scopes: {e.old_scopes}")
                print(f"  New scopes: {e.new_scopes}")
                print(f"  Old hash: {e.old_hash}")
                print(f"  New hash: {e.new_hash}")
                
                if e.old_hash == old_hash and e.new_hash == CURRENT_SCOPE_HASH:
                    print(f"✓ Hashes match expected values")
                else:
                    print(f"✗ Hash mismatch in error")
                    return False
            
            # Load without validation should work
            tokens = storage.load_tokens(test_user, "google", validate_scope_hash=False)
            if tokens:
                print(f"✓ Loading without validation works")
            else:
                print(f"✗ Failed to load without validation")
                return False
            
            # Clean up temp directory
            shutil.rmtree(storage.storage_dir)
            print(f"✓ Cleaned up temp storage")
            
        finally:
            if os.path.exists(temp_dir):
                shutil.rmtree(temp_dir)
        
        print("\n" + "=" * 60)
        print("TEST 2: PASSED ✓")
        print("=" * 60 + "\n")
        return True
        
    except Exception as e:
        print(f"✗ TEST 2 FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_scope_import_consistency():
    """Test that all modules use the same scope source."""
    print("=" * 60)
    print("TEST 3: Scope Import Consistency")
    print("=" * 60)
    
    try:
        from config.google_scopes import GOOGLE_SCOPES, CURRENT_SCOPE_HASH
        
        # Test google_service.py imports canonical scopes
        from services.google_service import SCOPES as GOOGLE_SERVICE_SCOPES
        
        if GOOGLE_SERVICE_SCOPES == GOOGLE_SCOPES:
            print(f"✓ google_service.py uses canonical scopes")
        else:
            print(f"✗ google_service.py has different scopes!")
            print(f"  Expected: {GOOGLE_SCOPES}")
            print(f"  Got: {GOOGLE_SERVICE_SCOPES}")
            return False
        
        # Test integrations.py imports canonical scopes
        from api.integrations import GOOGLE_SCOPES as INTEGRATIONS_SCOPES
        
        if INTEGRATIONS_SCOPES == GOOGLE_SCOPES:
            print(f"✓ api/integrations.py uses canonical scopes")
        else:
            print(f"✗ api/integrations.py has different scopes!")
            return False
        
        print("\n" + "=" * 60)
        print("TEST 3: PASSED ✓")
        print("=" * 60 + "\n")
        return True
        
    except Exception as e:
        print(f"✗ TEST 3 FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Run all tests."""
    print("\n" + "=" * 60)
    print("GOOGLE OAUTH SCOPE FIX - TEST SUITE")
    print("=" * 60 + "\n")
    
    results = []
    
    # Run tests
    results.append(("Scope Hash Generation", test_scope_hash_generation()))
    results.append(("Scope Changed Error Detection", test_scope_changed_error()))
    results.append(("Scope Import Consistency", test_scope_import_consistency()))
    
    # Summary
    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "PASSED ✓" if result else "FAILED ✗"
        print(f"  {test_name}: {status}")
    
    print(f"\nTotal: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n🎉 ALL TESTS PASSED! The scope fix is working correctly.")
        return 0
    else:
        print(f"\n⚠️  {total - passed} test(s) failed. Please review the errors above.")
        return 1


if __name__ == "__main__":
    sys.exit(main())

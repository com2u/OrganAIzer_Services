"""
Test script for YouTube download functionality.
Tests the fixed yt-dlp implementation with JS runtime support (Node.js/Bun/Deno).
"""
import sys
import os

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))

from services.youtube_service import download_youtube_video, _find_js_runtime

def test_js_runtime_detection():
    """Test if a JS runtime is detected on the system."""
    print("=" * 60)
    print("Test 1: JS Runtime Detection (Node.js/Bun/Deno)")
    print("=" * 60)
    
    runtime_name, runtime_path = _find_js_runtime()
    if runtime_name:
        print(f"✅ JS runtime found: {runtime_name}")
        print(f"   Path: {runtime_path}")
        
        # Try to get runtime version
        try:
            import subprocess
            result = subprocess.run([runtime_path, '--version'], capture_output=True, text=True, timeout=5)
            print(f"✅ Version: {result.stdout.strip()}")
        except Exception as e:
            print(f"⚠️  Could not get version: {e}")
        return runtime_name, runtime_path
    else:
        print("❌ No JS runtime found (Node.js/Bun/Deno)")
        print("   Install Node.js LTS from: https://nodejs.org/")
        return None, None

def test_youtube_download(test_url):
    """Test downloading a YouTube video."""
    print("\n" + "=" * 60)
    print("Test 2: YouTube Download")
    print("=" * 60)
    
    print(f"Testing download of: {test_url}")
    
    try:
        file_path = download_youtube_video(test_url)
        
        if os.path.exists(file_path):
            file_size = os.path.getsize(file_path)
            file_name = os.path.basename(file_path)
            print(f"✅ Download successful!")
            print(f"   File: {file_name}")
            print(f"   Path: {file_path}")
            print(f"   Size: {file_size:,} bytes ({file_size / 1024 / 1024:.2f} MB)")
            
            # Clean up
            try:
                os.remove(file_path)
                # Try to remove the temp directory
                temp_dir = os.path.dirname(file_path)
                if os.path.exists(temp_dir) and not os.listdir(temp_dir):
                    os.rmdir(temp_dir)
                print(f"✅ Cleanup successful")
            except Exception as e:
                print(f"⚠️  Cleanup warning: {e}")
            
            return True
        else:
            print(f"❌ File not found after download: {file_path}")
            return False
            
    except Exception as e:
        error_msg = str(e)
        print(f"❌ Download failed: {error_msg}")
        
        # Provide helpful diagnostics
        if "JS runtime" in error_msg or "Node.js" in error_msg or "Bun" in error_msg or "Deno" in error_msg:
            print("\n💡 Diagnosis: JS runtime required but not found")
            print("   Solution: Install Node.js LTS from https://nodejs.org/")
            print("   After installing, restart your terminal/IDE")
        elif "empty" in error_msg.lower() and "file" in error_msg.lower():
            print("\n💡 Diagnosis: Downloaded file is empty")
            print("   Solution: SABR/HLS fragment issues - try updating yt-dlp:")
            print("   pip install -U yt-dlp")
        elif "404" in error_msg or "not found" in error_msg.lower():
            print("\n💡 Diagnosis: Video not found or unavailable")
            print("   The video may have been deleted or made private")
        elif "private" in error_msg.lower() or "members-only" in error_msg.lower():
            print("\n💡 Diagnosis: Video is private or members-only")
        elif "age" in error_msg.lower() and "restricted" in error_msg.lower():
            print("\n💡 Diagnosis: Video is age-restricted")
        
        return False

def main():
    print("\n" + "=" * 60)
    print("YouTube Download Test Suite - OrganAIzer")
    print("=" * 60)
    
    # Test 1: Check for JS runtime
    runtime_name, runtime_path = test_js_runtime_detection()
    
    if not runtime_name:
        print("\n" + "=" * 60)
        print("⚠️  PREREQUISITE MISSING")
        print("=" * 60)
        print("A JavaScript runtime is required for YouTube downloads.")
        print("Please install Node.js LTS and run this test again.")
        print("\nDownload from: https://nodejs.org/")
        return
    
    # Test 2: Try to download videos
    test_urls = [
        "https://www.youtube.com/watch?v=XdFgShvwluE",  # Requested test video
        "https://www.youtube.com/watch?v=jNQXAC9IVRw",  # "Me at the zoo" - first YouTube video (fallback)
    ]
    
    downloads_passed = 0
    for idx, url in enumerate(test_urls, 1):
        if idx > 1:
            print("\n" + "-" * 60)
            print(f"Testing alternate URL {idx}...")
            print("-" * 60)
        
        if test_youtube_download(url):
            downloads_passed += 1
            break  # Stop after first successful download
    
    # Summary
    print("\n" + "=" * 60)
    print("Test Summary")
    print("=" * 60)
    print(f"JS Runtime Detection: ✅ PASS ({runtime_name})")
    print(f"YouTube Download:     {'✅ PASS' if downloads_passed > 0 else '❌ FAIL'}")
    
    if runtime_name and downloads_passed > 0:
        print("\n🎉 All tests passed! YouTube download is working correctly.")
    elif runtime_name and downloads_passed == 0:
        print("\n⚠️  JS runtime is available but all downloads failed.")
        print("   This could be due to network issues or YouTube restrictions.")
        print("   Try updating yt-dlp: pip install -U yt-dlp")
    else:
        print("\n❌ Tests failed. Please install a JS runtime (Node.js/Bun/Deno).")

if __name__ == "__main__":
    main()

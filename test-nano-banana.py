"""
Test script for Nano Banana image generation
"""

import asyncio
import sys
sys.path.insert(0, 'backend')

from services.nano_banana_service import get_nano_banana_service

async def test_nano_banana():
    """Test nano banana image generation."""
    print("🍌 Testing Nano Banana Image Generation...")
    print("-" * 50)
    
    try:
        # Get service
        service = get_nano_banana_service()
        
        # Test prompt
        prompt = "a cute robot holding a banana"
        num_images = 2
        
        print(f"Prompt: {prompt}")
        print(f"Number of images: {num_images}")
        print("\nGenerating images...")
        
        # Generate images
        images = await service.generate_images(prompt=prompt, num_images=num_images)
        
        print(f"\n✅ SUCCESS! Generated {len(images)} images:")
        for i, img in enumerate(images, 1):
            print(f"  {i}. Image ID: {img['image_id']}")
            print(f"     File: {img['filename']}")
            print(f"     Path: {img['filepath']}")
        
        print("\n🎉 Nano Banana test completed successfully!")
        return True
        
    except Exception as e:
        print(f"\n❌ ERROR: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = asyncio.run(test_nano_banana())
    sys.exit(0 if success else 1)

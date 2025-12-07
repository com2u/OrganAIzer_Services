"""
Test script for OpenRouter image generation.
Tests the new image generation service using OpenRouter API.
"""

import asyncio
import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent / "backend"))

from services.image_gen_service import get_image_gen_service


async def test_image_generation():
    """Test basic image generation."""
    print("=" * 60)
    print("Testing OpenRouter Image Generation")
    print("=" * 60)
    print()
    
    # Get service instance
    service = get_image_gen_service()
    
    # Test prompt
    prompt = "A beautiful sunset over mountains with vibrant orange and purple colors"
    aspect_ratio = "16:9"
    
    print(f"Prompt: {prompt}")
    print(f"Aspect Ratio: {aspect_ratio}")
    print()
    
    try:
        # Generate image
        print("Generating image...")
        image_ids = await service.generate_images(
            prompt=prompt,
            num_images=1,
            aspect_ratio=aspect_ratio
        )
        
        print(f"✓ Successfully generated {len(image_ids)} image(s)")
        print()
        
        # Display image paths
        for idx, image_id in enumerate(image_ids, 1):
            image_path = service.get_image_path(image_id)
            print(f"Image {idx}:")
            print(f"  ID: {image_id}")
            print(f"  Path: {image_path}")
            print(f"  Exists: {image_path.exists()}")
            print(f"  Size: {image_path.stat().st_size if image_path.exists() else 0} bytes")
            print()
        
        print("=" * 60)
        print("Test completed successfully!")
        print("=" * 60)
        
    except Exception as e:
        print(f"✗ Error: {str(e)}")
        print()
        print("=" * 60)
        print("Test failed!")
        print("=" * 60)
        raise


if __name__ == "__main__":
    asyncio.run(test_image_generation())

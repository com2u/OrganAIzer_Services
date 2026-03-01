"""
Nano Banana Image Generation Service
Uses Gemini 2.5 Flash Image via Node.js script
"""

import logging
import json
import subprocess
import base64
import uuid
from pathlib import Path
from typing import List, Dict
from core.error_handling import AppError

logger = logging.getLogger(__name__)


class NanoBananaService:
    """Service for generating images using Gemini 2.5 Flash Image (nano banana)."""
    
    def __init__(self):
        """Initialize the nano banana service."""
        self.script_path = Path(__file__).parent.parent / "generate-nano-banana.js"
        self.output_dir = Path("./data/images")
        self.output_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"NanoBananaService initialized with script: {self.script_path}")
    
    async def generate_images(
        self,
        prompt: str,
        num_images: int = 1
    ) -> List[Dict[str, str]]:
        """
        Generate images from a text prompt using nano banana.
        
        Args:
            prompt: Text description of the image to generate
            num_images: Number of images to generate (1-4)
        
        Returns:
            List of dictionaries with image data
        
        Raises:
            AppError: If image generation fails
        """
        try:
            logger.info(f"🍌 Generating {num_images} image(s) with nano banana...")
            logger.info(f"Prompt: {prompt[:100]}...")
            
            # Call the Node.js script
            result = subprocess.run(
                ["node", str(self.script_path), prompt, str(num_images)],
                capture_output=True,
                text=True,
                timeout=60,
                cwd=self.script_path.parent
            )
            
            if result.returncode != 0:
                error_msg = result.stderr or result.stdout or "Unknown error"
                logger.error(f"Node.js script failed: {error_msg}")
                raise AppError(
                    code="NANO_BANANA_FAILED",
                    message="Failed to generate images with nano banana",
                    details={"error": error_msg}
                )
            
            # Parse JSON output from script
            output_lines = result.stdout.strip().split('\n')
            json_output = None
            
            # Find the JSON output (after "JSON Output:" line)
            for i, line in enumerate(output_lines):
                if "JSON Output:" in line and i + 1 < len(output_lines):
                    json_start = i + 1
                    json_text = '\n'.join(output_lines[json_start:])
                    try:
                        json_output = json.loads(json_text)
                        break
                    except json.JSONDecodeError:
                        continue
            
            if not json_output or not json_output.get('success'):
                logger.error(f"Invalid JSON output from script")
                raise AppError(
                    code="NANO_BANANA_PARSE_ERROR",
                    message="Failed to parse nano banana output",
                    details={"output": result.stdout[:500]}
                )
            
            # Extract image data
            images = []
            for img_data in json_output.get('images', []):
                # Save image with unique ID
                image_id = str(uuid.uuid4())
                filename = f"nano_banana_{image_id}.png"
                filepath = self.output_dir / filename
                
                # Extract base64 data from data URL
                data_url = img_data.get('dataUrl', '')
                if data_url.startswith('data:image/png;base64,'):
                    base64_data = data_url.split(',', 1)[1]
                    
                    # Save to file
                    with open(filepath, 'wb') as f:
                        f.write(base64.b64decode(base64_data))
                    
                    logger.info(f"Saved image to {filepath}")
                    
                    images.append({
                        'image_id': image_id,
                        'filename': filename,
                        'filepath': str(filepath),
                        'dataUrl': data_url
                    })
            
            logger.info(f"✅ Successfully generated {len(images)} image(s)")
            return images
            
        except subprocess.TimeoutExpired:
            logger.error("Nano banana script timed out")
            raise AppError(
                code="NANO_BANANA_TIMEOUT",
                message="Image generation timed out",
                details={"timeout": 60}
            )
        except Exception as e:
            logger.error(f"Nano banana generation failed: {str(e)}", exc_info=True)
            raise AppError(
                code="NANO_BANANA_ERROR",
                message="Failed to generate images with nano banana",
                details={"error": str(e)}
            )
    
    def get_image_path(self, image_id: str) -> Path:
        """
        Get the file path for a generated image.
        
        Args:
            image_id: UUID of the generated image
        
        Returns:
            Path to the image file
        
        Raises:
            AppError: If image file not found
        """
        filepath = self.output_dir / f"nano_banana_{image_id}.png"
        
        if not filepath.exists():
            raise AppError(
                code="IMAGE_NOT_FOUND",
                message="Generated image not found",
                details={"image_id": image_id}
            )
        
        return filepath


# Global service instance
_nano_banana_service = None


def get_nano_banana_service() -> NanoBananaService:
    """Get or create the global NanoBananaService instance."""
    global _nano_banana_service
    if _nano_banana_service is None:
        _nano_banana_service = NanoBananaService()
    return _nano_banana_service

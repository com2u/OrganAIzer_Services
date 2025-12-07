"""
Image Generation Service using OpenRouter (Google Gemini 2.5 Flash Image Preview).
Handles text-to-image generation requests.
"""

import logging
import base64
import uuid
import requests
from pathlib import Path
from typing import List
from core.config import config
from core.error_handling import AppError

logger = logging.getLogger(__name__)


class ImageGenerationService:
    """Service for generating images from text prompts using OpenRouter."""
    
    def __init__(self):
        """Initialize the image generation service."""
        self.model_name = "google/gemini-2.5-flash-image-preview"
        self.api_url = "https://openrouter.ai/api/v1/chat/completions"
        self.output_dir = Path(config.IMAGE_GEN_TEMP_DIR)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"ImageGenerationService initialized with output dir: {self.output_dir}")
    
    async def generate_images(
        self,
        prompt: str,
        num_images: int = 1,
        aspect_ratio: str = "1:1"
    ) -> List[str]:
        """
        Generate images from a text prompt.
        
        Args:
            prompt: Text description of the image to generate
            num_images: Number of images to generate (1-4)
            aspect_ratio: Aspect ratio for images (1:1, 2:3, 3:2, 3:4, 4:3, 4:5, 5:4, 9:16, 16:9, 21:9)
        
        Returns:
            List of file paths to generated images (image IDs)
        
        Raises:
            AppError: If image generation fails
        """
        try:
            logger.info(f"Generating {num_images} image(s) with prompt: {prompt[:50]}...")
            
            # Check if API key is configured
            if not config.OPENROUTER_API_KEY:
                raise AppError(
                    code="API_KEY_MISSING",
                    message="OpenRouter API key not configured",
                    details={"hint": "Set OPENROUTER_API_KEY in .env file"}
                )
            
            # Prepare headers
            headers = {
                "Authorization": f"Bearer {config.OPENROUTER_API_KEY}",
                "Content-Type": "application/json"
            }
            
            # Generate images (OpenRouter currently generates one image per request)
            image_paths = []
            for i in range(num_images):
                # Prepare payload
                payload = {
                    "model": self.model_name,
                    "messages": [
                        {
                            "role": "user",
                            "content": prompt
                        }
                    ],
                    "modalities": ["image", "text"],
                    "image_config": {
                        "aspect_ratio": aspect_ratio
                    }
                }
                
                logger.info(f"Generating image {i + 1}/{num_images}...")
                
                # Make API request
                response = requests.post(self.api_url, headers=headers, json=payload)
                response.raise_for_status()
                
                result = response.json()
                
                # Extract image from response
                if result.get("choices"):
                    message = result["choices"][0]["message"]
                    if message.get("images"):
                        for image_data in message["images"]:
                            image_url = image_data["image_url"]["url"]
                            
                            # Decode base64 image data
                            # Format: data:image/png;base64,<base64_data>
                            if image_url.startswith("data:image"):
                                # Extract base64 data
                                base64_data = image_url.split(",", 1)[1]
                                image_bytes = base64.b64decode(base64_data)
                                
                                # Generate unique filename
                                image_id = str(uuid.uuid4())
                                filename = f"image_{image_id}.png"
                                filepath = self.output_dir / filename
                                
                                # Save image
                                with open(filepath, "wb") as f:
                                    f.write(image_bytes)
                                
                                logger.info(f"Saved image {i + 1}/{num_images} to {filepath}")
                                image_paths.append(image_id)
                    else:
                        logger.warning(f"No images in response for request {i + 1}")
                else:
                    logger.warning(f"No choices in response for request {i + 1}")
            
            if not image_paths:
                raise AppError(
                    code="NO_IMAGES_GENERATED",
                    message="No images were generated from the API response",
                    details={"response": result}
                )
            
            logger.info(f"Successfully generated {len(image_paths)} images")
            return image_paths
            
        except requests.exceptions.RequestException as e:
            logger.error(f"API request failed: {str(e)}", exc_info=True)
            raise AppError(
                code="API_REQUEST_FAILED",
                message="Failed to communicate with OpenRouter API",
                details={"error": str(e)}
            )
        except Exception as e:
            logger.error(f"Image generation failed: {str(e)}", exc_info=True)
            raise AppError(
                code="IMAGE_GENERATION_FAILED",
                message="Failed to generate images",
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
        filepath = self.output_dir / f"image_{image_id}.png"
        
        if not filepath.exists():
            raise AppError(
                code="IMAGE_NOT_FOUND",
                message="Generated image not found",
                details={"image_id": image_id}
            )
        
        return filepath
    
    def cleanup_old_images(self, max_age_hours: int = 24):
        """
        Clean up old generated images.
        
        Args:
            max_age_hours: Maximum age of images to keep in hours
        """
        import time
        
        try:
            current_time = time.time()
            max_age_seconds = max_age_hours * 3600
            
            for filepath in self.output_dir.glob("image_*.png"):
                if current_time - filepath.stat().st_mtime > max_age_seconds:
                    filepath.unlink()
                    logger.info(f"Deleted old image: {filepath}")
        
        except Exception as e:
            logger.error(f"Error cleaning up old images: {str(e)}")


# Global service instance
_image_gen_service = None


def get_image_gen_service() -> ImageGenerationService:
    """Get or create the global ImageGenerationService instance."""
    global _image_gen_service
    if _image_gen_service is None:
        _image_gen_service = ImageGenerationService()
    return _image_gen_service

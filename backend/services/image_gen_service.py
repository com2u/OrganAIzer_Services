"""
Image Generation Service using Google Vertex AI Imagen.
Handles text-to-image generation requests.
"""

import logging
import base64
import uuid
from pathlib import Path
from typing import List
from vertexai.preview.vision_models import ImageGenerationModel
from core.config import config
from core.error_handling import AppError

logger = logging.getLogger(__name__)


class ImageGenerationService:
    """Service for generating images from text prompts using Vertex AI Imagen."""
    
    def __init__(self):
        """Initialize the image generation service."""
        self.model_name = "imagegeneration@006"
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
            aspect_ratio: Aspect ratio for images (1:1, 16:9, 9:16, 4:3, 3:4)
        
        Returns:
            List of file paths to generated images
        
        Raises:
            AppError: If image generation fails
        """
        try:
            logger.info(f"Generating {num_images} image(s) with prompt: {prompt[:50]}...")
            
            # Load the model
            model = ImageGenerationModel.from_pretrained(self.model_name)
            
            # Generate images
            response = model.generate_images(
                prompt=prompt,
                number_of_images=num_images,
                aspect_ratio=aspect_ratio,
                safety_filter_level="block_some",
                person_generation="allow_adult"
            )
            
            # Save images and collect file paths
            image_paths = []
            for idx, image in enumerate(response.images):
                # Generate unique filename
                image_id = str(uuid.uuid4())
                filename = f"image_{image_id}.png"
                filepath = self.output_dir / filename
                
                # Save image
                image._pil_image.save(filepath, "PNG")
                logger.info(f"Saved image {idx + 1}/{num_images} to {filepath}")
                
                image_paths.append(image_id)
            
            logger.info(f"Successfully generated {len(image_paths)} images")
            return image_paths
            
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

"""
Image Generation API endpoints.
Handles text-to-image generation requests.
"""

import logging
from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from models.image_gen import ImageGenerateRequest, ImageGenerateResponse
from services.image_gen_service import get_image_gen_service
from core.error_handling import AppError

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Image Generation"])


@router.post("/image-gen/generate", response_model=ImageGenerateResponse)
async def generate_images(request: ImageGenerateRequest):
    """
    Generate images from a text prompt using Vertex AI Imagen.
    
    Args:
        request: Image generation request containing prompt and parameters
    
    Returns:
        ImageGenerateResponse with generated image URLs
    
    Raises:
        HTTPException: If image generation fails
    """
    try:
        logger.info(f"Received image generation request for prompt: {request.prompt[:50]}...")
        
        # Get the image generation service
        service = get_image_gen_service()
        
        # Generate images
        image_ids = await service.generate_images(
            prompt=request.prompt,
            num_images=request.num_images,
            aspect_ratio=request.aspect_ratio
        )
        
        # Build image URLs
        image_urls = [f"/api/image-gen/image/{image_id}" for image_id in image_ids]
        
        logger.info(f"Successfully generated {len(image_urls)} images")
        
        return ImageGenerateResponse(
            prompt=request.prompt,
            images=image_urls,
            num_images=len(image_urls)
        )
    
    except AppError as e:
        logger.error(f"Image generation failed: {e.message}")
        raise HTTPException(status_code=400, detail=e.to_dict())
    
    except Exception as e:
        logger.error(f"Unexpected error in image generation: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={
                "error": {
                    "code": "INTERNAL_ERROR",
                    "message": "An unexpected error occurred during image generation",
                    "details": {"error": str(e)}
                }
            }
        )


@router.get("/image-gen/image/{image_id}")
async def get_image(image_id: str):
    """
    Retrieve a generated image by its ID.
    
    Args:
        image_id: UUID of the generated image
    
    Returns:
        FileResponse with the image file
    
    Raises:
        HTTPException: If image not found
    """
    try:
        logger.info(f"Retrieving image: {image_id}")
        
        # Get the image generation service
        service = get_image_gen_service()
        
        # Get image path
        image_path = service.get_image_path(image_id)
        
        logger.info(f"Serving image: {image_path}")
        
        # Return image file
        return FileResponse(
            path=str(image_path),
            media_type="image/png",
            filename=f"generated_{image_id}.png"
        )
    
    except AppError as e:
        logger.error(f"Image retrieval failed: {e.message}")
        raise HTTPException(status_code=404, detail=e.to_dict())
    
    except Exception as e:
        logger.error(f"Unexpected error retrieving image: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={
                "error": {
                    "code": "INTERNAL_ERROR",
                    "message": "An unexpected error occurred while retrieving the image",
                    "details": {"error": str(e)}
                }
            }
        )

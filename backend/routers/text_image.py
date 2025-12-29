from fastapi import APIRouter, HTTPException
import logging
from services.text_image_service import generate_images
from starlette.requests import Request

logger = logging.getLogger(__name__)

router = APIRouter()

@router.api_route("/generate", methods=["POST"])
async def generate(request: Request):
    try:
        # Parse form data manually
        form = await request.form()

        prompt = form.get("prompt")
        if not prompt:
            raise HTTPException(status_code=400, detail="Prompt is required")

        # Get aspect ratio (default to square)
        aspect_ratio = form.get("aspect_ratio", "square")
        logger.info(f"Requested aspect ratio: {aspect_ratio}")

        # Process uploaded images if any
        uploaded_images = []
        for field_name, field_value in form.items():
            if hasattr(field_value, 'filename') and field_value.filename:
                # Read file content
                content = await field_value.read()
                logger.info(f"Received uploaded image: {field_value.filename}")
                uploaded_images.append({
                    'filename': field_value.filename,
                    'content': content
                })

        # Generate images using the prompt (and potentially uploaded images)
        images_result = generate_images(prompt, {
            "uploaded_images": uploaded_images,
            "aspect_ratio": aspect_ratio
        })

        logger.info("Image generation successful")

        return {"images": images_result}
    except Exception as e:
        logger.error(f"Image generation failed: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))

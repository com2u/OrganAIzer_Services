"""
Data models for Image Generation API.
Defines request/response schemas for text-to-image generation.
"""

from pydantic import BaseModel, Field
from typing import Optional


class ImageGenerateRequest(BaseModel):
    """
    Request model for generating images from text prompts.
    
    Attributes:
        prompt (str): The text description of the image to generate
        num_images (int): Number of images to generate (1-4)
        aspect_ratio (str): Aspect ratio for the generated image
    """
    prompt: str = Field(
        ...,
        min_length=1,
        max_length=1000,
        description="Text description of the image to generate"
    )
    num_images: Optional[int] = Field(
        default=1,
        ge=1,
        le=4,
        description="Number of images to generate (1-4)"
    )
    aspect_ratio: Optional[str] = Field(
        default="1:1",
        description="Aspect ratio (1:1, 16:9, 9:16, 4:3, 3:4)"
    )


class ImageGenerateResponse(BaseModel):
    """
    Response model for image generation.
    
    Attributes:
        prompt (str): The original prompt used
        images (list): List of generated image URLs
        num_images (int): Number of images generated
    """
    prompt: str
    images: list[str]
    num_images: int

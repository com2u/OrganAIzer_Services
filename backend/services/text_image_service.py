import logging
import os
import base64
from typing import List, Dict
from dotenv import load_dotenv
from PIL import Image, ImageDraw, ImageFont
import io

# Load environment variables
load_dotenv()

logger = logging.getLogger(__name__)

import requests
import json

# Aspect ratio configurations
ASPECT_RATIOS = {
    "square": {"width": 1024, "height": 1024, "description": "square 1:1 aspect ratio"},
    "landscape": {"width": 1536, "height": 1024, "description": "landscape 3:2 aspect ratio, wider than tall"},
    "portrait": {"width": 1024, "height": 1536, "description": "portrait 2:3 aspect ratio, taller than wide"},
    "wide": {"width": 1792, "height": 1024, "description": "wide 16:9 aspect ratio, cinematic"},
    "tall": {"width": 1024, "height": 1792, "description": "tall 9:16 aspect ratio, mobile/story format"}
}

def generate_images(prompt: str, options: dict = None) -> List[Dict[str, str]]:
    """
    Generates images from text prompt (and optional image) using OpenRouter API with fallback.
    Returns list of image dicts with url and id.
    """
    try:
        logger.info(f"Generating images for prompt: {prompt}")
        
        # Extract options
        uploaded_images = options.get("uploaded_images") if options else None
        aspect_ratio = options.get("aspect_ratio", "square") if options else "square"
        
        # Get aspect ratio config
        ratio_config = ASPECT_RATIOS.get(aspect_ratio, ASPECT_RATIOS["square"])
        logger.info(f"Using aspect ratio: {aspect_ratio} ({ratio_config['description']})")
        
        # Enhance prompt with aspect ratio instruction
        enhanced_prompt = f"{prompt}\n\nIMPORTANT: Generate this image in {ratio_config['description']}. The image dimensions should be approximately {ratio_config['width']}x{ratio_config['height']} pixels."
        
        # Try OpenRouter first
        result = generate_with_openrouter(enhanced_prompt, uploaded_images, ratio_config)
        if result:
            return result

        # Fallback: programmatic images
        logger.warning("OpenRouter API failed, using programmatic fallback")
        return create_fallback_images(prompt, ratio_config)

    except Exception as e:
        logger.error(f"Image generation failed: {str(e)}")
        return create_fallback_images(prompt, ASPECT_RATIOS.get("square"))

def generate_with_openrouter(prompt: str, uploaded_images: List[Dict] = None, ratio_config: dict = None) -> List[Dict[str, str]]:
    """
    Generate images using OpenRouter API with Gemini 2.5 Flash Image Preview.
    Supports text-to-image and image-to-image editing.
    Returns list of image dicts or None if failed.
    """
    try:
        api_key = os.getenv('OPENROUTER_API_KEY')
        if not api_key:
            logger.warning("OPENROUTER_API_KEY not found")
            return None

        logger.info("Attempting image generation with OpenRouter (Gemini 2.5 Flash Image Preview)...")
        
        url = "https://openrouter.ai/api/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://organaizer.service",
            "X-Title": "OrganAIzer Service"
        }
        
        # Construct messages payload
        content = [{"type": "text", "text": prompt}]
        
        # Add images if provided (image-to-image)
        if uploaded_images:
            for img in uploaded_images:
                # uploaded_images contains dicts with 'filename' and 'content' (bytes)
                if 'content' in img:
                    img_content = img['content']
                    # Convert bytes to base64 string
                    encoded_image = base64.b64encode(img_content).decode('utf-8')
                    
                    # Determine mime type based on extension or default to image/jpeg
                    filename = img.get('filename', 'image.jpg')
                    mime_type = "image/jpeg"
                    if filename.lower().endswith('.png'):
                        mime_type = "image/png"
                    elif filename.lower().endswith('.webp'):
                        mime_type = "image/webp"
                        
                    content.append({
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:{mime_type};base64,{encoded_image}"
                        }
                    })
            logger.info(f"Included {len(uploaded_images)} uploaded images in request")

        payload = {
            "model": "google/gemini-2.5-flash-image-preview",
            "messages": [
                {
                    "role": "user",
                    "content": content
                }
            ],
            "modalities": ["image", "text"],
            "stream": True
        }
        
        # Make the streaming request
        response = requests.post(url, headers=headers, json=payload, stream=True)
        response.raise_for_status()
        
        images = []
        
        # Process the streaming response
        for line in response.iter_lines():
            if line:
                line = line.decode('utf-8')
                if line.startswith('data: '):
                    data_str = line[6:]
                    if data_str != '[DONE]':
                        try:
                            chunk = json.loads(data_str)
                            if chunk.get("choices"):
                                delta = chunk["choices"][0].get("delta", {})
                                if delta.get("images"):
                                    for image_item in delta["images"]:
                                        if "image_url" in image_item and "url" in image_item["image_url"]:
                                            img_url = image_item["image_url"]["url"]
                                            
                                            # Process the image URL (download and convert to base64)
                                            try:
                                                img_response = requests.get(img_url, timeout=30)
                                                if img_response.status_code == 200:
                                                    # Resize/crop to desired aspect ratio
                                                    processed_img = process_image_aspect_ratio(img_response.content, ratio_config)
                                                    images.append({
                                                        "url": processed_img,
                                                        "id": f"openrouter_img_{len(images)}_{hash(prompt)}",
                                                        "description": prompt
                                                    })
                                                    logger.info(f"Successfully extracted and processed image from stream")
                                            except Exception as fetch_error:
                                                logger.error(f"Failed to fetch generated image: {fetch_error}")
                                                # Fallback: use the URL directly
                                                images.append({
                                                    "url": img_url,
                                                    "id": f"openrouter_img_{len(images)}_{hash(prompt)}",
                                                    "description": prompt
                                                })
                        except json.JSONDecodeError:
                            continue
        
        if images:
            logger.info(f"Successfully generated {len(images)} images using OpenRouter")
            return images
            
        logger.warning("No images found in the OpenRouter response stream")
        return None

    except Exception as e:
        logger.error(f"OpenRouter generation error: {str(e)}")
        return None


def process_image_aspect_ratio(image_bytes: bytes, ratio_config: dict) -> str:
    """
    Process an image to match the desired aspect ratio.
    Uses center crop to maintain the most important parts of the image.
    Returns base64 data URL.
    """
    try:
        if ratio_config is None:
            ratio_config = ASPECT_RATIOS["square"]
            
        # Open the image
        img = Image.open(io.BytesIO(image_bytes))
        original_width, original_height = img.size
        
        # Calculate target dimensions
        target_width = ratio_config["width"]
        target_height = ratio_config["height"]
        target_ratio = target_width / target_height
        original_ratio = original_width / original_height
        
        logger.info(f"Processing image: {original_width}x{original_height} -> {target_width}x{target_height}")
        
        # Determine crop dimensions to match target aspect ratio
        if original_ratio > target_ratio:
            # Image is wider than target - crop width
            new_width = int(original_height * target_ratio)
            new_height = original_height
            left = (original_width - new_width) // 2
            top = 0
        else:
            # Image is taller than target - crop height
            new_width = original_width
            new_height = int(original_width / target_ratio)
            left = 0
            top = (original_height - new_height) // 2
        
        # Crop to aspect ratio
        right = left + new_width
        bottom = top + new_height
        img_cropped = img.crop((left, top, right, bottom))
        
        # Resize to target dimensions
        img_resized = img_cropped.resize((target_width, target_height), Image.Resampling.LANCZOS)
        
        # Convert to base64
        buffer = io.BytesIO()
        img_resized.save(buffer, format='PNG', optimize=True)
        img_b64 = base64.b64encode(buffer.getvalue()).decode()
        
        logger.info(f"Image processed successfully to {target_width}x{target_height}")
        return f"data:image/png;base64,{img_b64}"
        
    except Exception as e:
        logger.error(f"Failed to process image aspect ratio: {str(e)}")
        # Return original image as fallback
        img_b64 = base64.b64encode(image_bytes).decode()
        return f"data:image/png;base64,{img_b64}"


def create_fallback_images(prompt: str, ratio_config: dict = None) -> List[Dict[str, str]]:
    """Creates fallback images when API fails"""
    if ratio_config is None:
        ratio_config = ASPECT_RATIOS["square"]
    images = []
    for i in range(2):
        image_url = create_simple_fallback_image(i + 1, prompt, ratio_config)
        images.append({
            "url": image_url,
            "id": f"fallback_img_{i + 1}",
            "description": f"Fallback image generated for prompt: {prompt}"
        })
    return images


def create_simple_fallback_image(image_number: int, prompt: str, ratio_config: dict = None) -> str:
    """Creates a simple colored image as fallback"""
    try:
        if ratio_config is None:
            ratio_config = ASPECT_RATIOS["square"]
        # Scale down to reasonable size while maintaining aspect ratio
        base_size = 512
        scale_factor = base_size / max(ratio_config["width"], ratio_config["height"])
        width = int(ratio_config["width"] * scale_factor)
        height = int(ratio_config["height"] * scale_factor)
        
        # Create a base image with a gradient background
        image = Image.new('RGB', (width, height), color='#f0f8ff')
        draw = ImageDraw.Draw(image)

        # Create a gradient effect
        for y in range(height):
            r = int(240 + (135 - 240) * (y / height))
            g = int(248 + (206 - 248) * (y / height))
            b = int(255 + (250 - 255) * (y / height))
            draw.line([(0, y), (width, y)], fill=(r, g, b))

        # Add some geometric shapes
        colors = ['#FF6B6B', '#4ECDC4', '#45B7D1', '#96CEB4', '#FFEAA7', '#DDA0DD']

        import random
        random.seed(hash(prompt) + image_number)

        for _ in range(15):
            x = random.randint(50, width - 50)
            y = random.randint(50, height - 50)
            radius = random.randint(20, 60)
            color = random.choice(colors)
            draw.ellipse([x-radius, y-radius, x+radius, y+radius], fill=color, outline=color)

        # Add text overlay
        try:
            font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 24)
        except:
            font = ImageFont.load_default()

        # Add title text
        title = f"AI Image Generation"
        bbox = draw.textbbox((0, 0), title, font=font)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]
        x = (width - text_width) // 2
        y = 30

        draw.rectangle([x-10, y-5, x+text_width+10, y+text_height+5], fill='white')
        draw.text((x, y), title, fill='black', font=font)

        # Add subtitle
        subtitle = "(API Fallback Mode)"
        bbox = draw.textbbox((0, 0), subtitle, font=font)
        text_width = bbox[2] - bbox[0]
        x = (width - text_width) // 2
        y = 70
        draw.rectangle([x-10, y-5, x+text_width+10, y+text_height+5], fill='white')
        draw.text((x, y), subtitle, fill='#666666', font=font)

        # Add prompt text at bottom
        prompt_text = prompt[:50] + "..." if len(prompt) > 50 else prompt
        bbox = draw.textbbox((0, 0), prompt_text, font=font)
        text_width = bbox[2] - bbox[0]
        x = (width - text_width) // 2
        y = height - 60

        draw.rectangle([x-10, y-5, x+text_width+10, y+text_height+5], fill='white')
        draw.text((x, y), prompt_text, fill='black', font=font)

        # Convert to base64 data URL
        buffer = io.BytesIO()
        image.save(buffer, format='PNG')
        image_data = base64.b64encode(buffer.getvalue()).decode()

        return f"data:image/png;base64,{image_data}"

    except Exception as e:
        logger.error(f"Failed to create fallback image: {str(e)}")
        # Return a data URL for a 1x1 transparent pixel as last resort
        return "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg=="

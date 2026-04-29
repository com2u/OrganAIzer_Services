"""
OpenClaw client for OrganAIzer Services.
This module provides a safe interface to communicate with the OpenClaw assistant gateway.
"""

import aiohttp
import asyncio
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

class OpenClawClient:
    """Client for interacting with the OpenClaw assistant gateway."""
    
    def __init__(self, base_url: str, token: str):
        """
        Initialize the OpenClaw client.
        
        Args:
            base_url: The base URL of the OpenClaw service
            token: Authentication token for OpenClaw
        """
        self.base_url = base_url.rstrip('/')
        self.token = token
        self.timeout = aiohttp.ClientTimeout(total=30)  # 30 second timeout
        
    async def cleanup_request(self, request_text: str) -> Dict[str, Any]:
        """
        Clean up and standardize a request text using OpenAI-compatible endpoint.
        
        Args:
            request_text: Raw request text to clean up
            
        Returns:
            Dictionary containing cleaned request data
        """
        try:
            async with aiohttp.ClientSession(timeout=self.timeout) as session:
                headers = {
                    "Authorization": f"Bearer {self.token}",
                    "Content-Type": "application/json"
                }
                
                payload = {
                    "model": "gpt-4",
                    "messages": [
                        {
                            "role": "system",
                            "content": "You are a helpful assistant that cleans up and standardizes user requests. Remove any unnecessary formatting, normalize whitespace, and make the request clearer while preserving the original intent."
                        },
                        {
                            "role": "user",
                            "content": f"Clean up this request: {request_text}"
                        }
                    ],
                    "temperature": 0.3
                }
                
                async with session.post(
                    f"{self.base_url}/v1/chat/completions",
                    json=payload,
                    headers=headers
                ) as response:
                    if response.status == 200:
                        result = await response.json()
                        logger.info("Request cleanup successful")
                        # Extract the cleaned text from the response
                        cleaned_text = result['choices'][0]['message']['content']
                        return {"cleaned_text": cleaned_text}
                    else:
                        error_text = await response.text()
                        logger.error(f"Request cleanup failed with status {response.status}: {error_text}")
                        raise Exception(f"OpenClaw cleanup failed: {response.status}")
                        
        except asyncio.TimeoutError:
            logger.error("OpenClaw cleanup request timed out")
            raise Exception("OpenClaw cleanup request timed out")
        except Exception as e:
            logger.error(f"Error during OpenClaw cleanup: {str(e)}")
            raise
    
    async def summarize_text(self, text: str) -> Dict[str, Any]:
        """
        Summarize text using OpenAI-compatible endpoint.
        
        Args:
            text: Text to summarize
            
        Returns:
            Dictionary containing summary data
        """
        try:
            async with aiohttp.ClientSession(timeout=self.timeout) as session:
                headers = {
                    "Authorization": f"Bearer {self.token}",
                    "Content-Type": "application/json"
                }
                
                payload = {
                    "model": "gpt-4",
                    "messages": [
                        {
                            "role": "system",
                            "content": "You are a helpful assistant that summarizes text concisely while preserving key information."
                        },
                        {
                            "role": "user",
                            "content": f"Summarize this text in 2-3 sentences: {text}"
                        }
                    ],
                    "temperature": 0.3
                }
                
                async with session.post(
                    f"{self.base_url}/v1/chat/completions",
                    json=payload,
                    headers=headers
                ) as response:
                    if response.status == 200:
                        result = await response.json()
                        logger.info("Text summarization successful")
                        # Extract the summary from the response
                        summary = result['choices'][0]['message']['content']
                        return {"summary": summary}
                    else:
                        error_text = await response.text()
                        logger.error(f"Text summarization failed with status {response.status}: {error_text}")
                        raise Exception(f"OpenClaw summarization failed: {response.status}")
                        
        except asyncio.TimeoutError:
            logger.error("OpenClaw summarization request timed out")
            raise Exception("OpenClaw summarization request timed out")
        except Exception as e:
            logger.error(f"Error during OpenClaw summarization: {str(e)}")
            raise


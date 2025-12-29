#!/usr/bin/env python3
"""
Script to authenticate with Microsoft Graph using Device Code Flow.
Run this script first to authenticate before using the web interface.
"""

import os
import asyncio
from dotenv import load_dotenv
from services.outlook_service import get_graph_client

load_dotenv()

async def authenticate():
    """Authenticate with Microsoft Graph."""
    try:
        print("Authenticating with Microsoft Graph...")
        client = get_graph_client()
        # This will prompt for device code authentication
        # Try to make a simple call to trigger authentication
        result = await client.me.get()
        print(f"Authentication successful! User: {result.display_name}")
    except Exception as e:
        print(f"Authentication failed: {e}")

if __name__ == "__main__":
    asyncio.run(authenticate())
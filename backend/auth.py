from fastapi import Security, HTTPException, status
from fastapi.security import APIKeyHeader
import pandas as pd
import logging

import os

script_dir = os.path.dirname(__file__)
file_path = os.path.join(script_dir, 'keys.csv')
API_KEYS = pd.read_csv(file_path, header=None).iloc[:, 0].tolist()

api_key_header = APIKeyHeader(name="X-API-Key")

async def get_api_key(api_key: str = Security(api_key_header)):
    if api_key in API_KEYS:
        logging.info(f"API key validation successful for key: {api_key}")
        return api_key
    else:
        logging.warning(f"Invalid API key: {api_key}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API Key",
        )

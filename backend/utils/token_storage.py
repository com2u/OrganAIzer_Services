"""
Secure token storage for OAuth credentials.

Stores refresh tokens and access tokens encrypted at rest.
Supports scope versioning to detect permission changes.
"""

import os
import json
import logging
from pathlib import Path
from typing import Optional, Dict, Any
from cryptography.fernet import Fernet
import base64

logger = logging.getLogger(__name__)


class ScopeChangedError(Exception):
    """Raised when stored token scopes don't match current requirements."""
    
    def __init__(self, message: str, old_scopes: list, new_scopes: list, old_hash: str = None, new_hash: str = None):
        super().__init__(message)
        self.old_scopes = old_scopes
        self.new_scopes = new_scopes
        self.old_hash = old_hash
        self.new_hash = new_hash


class TokenStorage:
    """Encrypted token storage for OAuth credentials."""
    
    def __init__(self):
        """Initialize token storage with encryption."""
        # Get encryption key from environment
        key = os.getenv("TOKEN_ENCRYPTION_KEY")
        if not key:
            # Generate a key if not set WARNING: NOT FOR PRODUCTION
            logger.warning("TOKEN_ENCRYPTION_KEY not set - generating temporary key")
            key = Fernet.generate_key().decode()
            logger.warning(f"Generated key (save this in .env): TOKEN_ENCRYPTION_KEY={key}")
        
        # Ensure key is bytes
        if isinstance(key, str):
            key = key.encode()
        
        self.cipher = Fernet(key)
        self.storage_dir = Path("data/tokens")
        self.storage_dir.mkdir(parents=True, exist_ok=True)
    
    def _get_token_path(self, user_id: str, provider: str) -> Path:
        """Get path for user's provider tokens."""
        return self.storage_dir / f"{user_id}_{provider}.enc"
    
    def save_tokens(
        self,
        user_id: str,
        provider: str,
        tokens: Dict[str, Any]
    ) -> None:
        """
        Save encrypted tokens for a user and provider.
        
        Args:
            user_id: User identifier
            provider: Provider name (google, microsoft)
            tokens: Token data (access_token, refresh_token, expires_at, etc.)
        """
        try:
            # Serialize tokens
            token_json = json.dumps(tokens)
            
            # Encrypt
            encrypted = self.cipher.encrypt(token_json.encode())
            
            # Save to file
            token_path = self._get_token_path(user_id, provider)
            token_path.write_bytes(encrypted)
            
            logger.info(f"Saved encrypted tokens for {user_id}/{provider}")
        except Exception as e:
            logger.error(f"Failed to save tokens: {e}")
            raise
    
    def load_tokens(
        self,
        user_id: str,
        provider: str,
        validate_scope_hash: bool = False,
        expected_scope_hash: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Load encrypted tokens for a user and provider.
        
        Args:
            user_id: User identifier
            provider: Provider name (google, microsoft)
            validate_scope_hash: If True, raise ScopeChangedError if hash mismatch
            expected_scope_hash: Expected scope hash. If None and validate=True, 
                                 imports from config.google_scopes
        
        Returns:
            Token data dict or None if not found
            
        Raises:
            ScopeChangedError: If validate_scope_hash=True and hash doesn't match
        """
        token_path = self._get_token_path(user_id, provider)
        
        try:
            if not token_path.exists():
                logger.warning(f"No tokens found for {user_id}/{provider} at path: {token_path}")
                return None
            
            logger.debug(f"Loading tokens from: {token_path}")
            
            # Read encrypted data
            encrypted = token_path.read_bytes()
            
            # Decrypt
            decrypted = self.cipher.decrypt(encrypted)
            
            # Deserialize
            tokens = json.loads(decrypted.decode())
            
            # Validate scope hash if requested
            if validate_scope_hash and provider == "google":
                stored_hash = tokens.get("scope_hash")
                
                # Get expected hash
                if expected_scope_hash is None:
                    try:
                        from config.google_scopes import CURRENT_SCOPE_HASH
                        expected_scope_hash = CURRENT_SCOPE_HASH
                    except ImportError:
                        logger.warning("Could not import google_scopes config for validation")
                        expected_scope_hash = None
                
                # Compare hashes
                if expected_scope_hash and stored_hash != expected_scope_hash:
                    old_scopes = tokens.get("scopes", [])
                    logger.warning(
                        f"Scope hash mismatch for {user_id}/{provider}: "
                        f"stored={stored_hash}, expected={expected_scope_hash}"
                    )
                    
                    # Import to get new scopes
                    try:
                        from config.google_scopes import GOOGLE_SCOPES
                        new_scopes = GOOGLE_SCOPES
                    except ImportError:
                        new_scopes = []
                    
                    raise ScopeChangedError(
                        "OAuth scopes have changed. Please reconnect your Google account.",
                        old_scopes=old_scopes,
                        new_scopes=new_scopes,
                        old_hash=stored_hash,
                        new_hash=expected_scope_hash
                    )
            
            logger.info(f"Successfully loaded tokens for {user_id}/{provider}")
            return tokens
            
        except ScopeChangedError:
            # Re-raise scope errors
            raise
        except FileNotFoundError as e:
            logger.error(f"FileNotFoundError loading tokens for {user_id}/{provider}: {e} | Path: {token_path}")
            return None
        except json.JSONDecodeError as e:
            logger.error(f"JSONDecodeError loading tokens for {user_id}/{provider}: {e} | Path: {token_path}")
            return None
        except Exception as e:
            logger.error(f"Failed to load tokens for {user_id}/{provider}: {type(e).__name__}: {e} | Path: {token_path}", exc_info=True)
            return None
    
    def delete_tokens(
        self,
        user_id: str,
        provider: str
    ) -> bool:
        """
        Delete tokens for a user and provider.
        
        Args:
            user_id: User identifier
            provider: Provider name
        
        Returns:
            True if deleted, False if not found
        """
        try:
            token_path = self._get_token_path(user_id, provider)
            
            if not token_path.exists():
                return False
            
            token_path.unlink()
            logger.info(f"Deleted tokens for {user_id}/{provider}")
            return True
        except Exception as e:
            logger.error(f"Failed to delete tokens: {e}")
            return False
    
    def list_connections(self, user_id: str) -> Dict[str, bool]:
        """
        List which providers the user has connected.
        
        Args:
            user_id: User identifier
        
        Returns:
            Dict of provider -> connected status
        """
        connections = {}
        for provider in ["google", "microsoft"]:
            token_path = self._get_token_path(user_id, provider)
            connections[provider] = token_path.exists()
        return connections


# Singleton instance
_token_storage = None


def get_token_storage() -> TokenStorage:
    """Get the singleton token storage instance."""
    global _token_storage
    if _token_storage is None:
        _token_storage = TokenStorage()
    return _token_storage

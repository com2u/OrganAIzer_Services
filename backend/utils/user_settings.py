"""
User settings storage for OrganAIzer.

Stores user preferences including default email sender account.
"""

import os
import json
import logging
from pathlib import Path
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)


class UserSettings:
    """User settings storage."""
    
    def __init__(self):
        """Initialize user settings storage."""
        self.storage_dir = Path("data/user_settings")
        self.storage_dir.mkdir(parents=True, exist_ok=True)
    
    def _get_settings_path(self, user_id: str) -> Path:
        """Get path for user's settings file."""
        return self.storage_dir / f"{user_id}_settings.json"
    
    def load_settings(self, user_id: str) -> Dict[str, Any]:
        """
        Load user settings.
        
        Args:
            user_id: User identifier
        
        Returns:
            User settings dict (empty dict if not found)
        """
        settings_path = self._get_settings_path(user_id)
        
        try:
            if not settings_path.exists():
                return {}
            
            with open(settings_path, 'r') as f:
                settings = json.load(f)
            
            logger.debug(f"Loaded settings for user {user_id}")
            return settings
            
        except Exception as e:
            logger.error(f"Failed to load settings for {user_id}: {e}")
            return {}
    
    def save_settings(self, user_id: str, settings: Dict[str, Any]) -> bool:
        """
        Save user settings.
        
        Args:
            user_id: User identifier
            settings: Settings dict to save
        
        Returns:
            True if successful, False otherwise
        """
        settings_path = self._get_settings_path(user_id)
        
        try:
            with open(settings_path, 'w') as f:
                json.dump(settings, f, indent=2)
            
            logger.info(f"Saved settings for user {user_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to save settings for {user_id}: {e}")
            return False
    
    def get_default_sender_account(self, user_id: str) -> Optional[Dict[str, str]]:
        """
        Get default sender account for user.
        
        Returns:
            Dict with provider and account_id, or None if not set
        """
        settings = self.load_settings(user_id)
        default_sender = settings.get("default_sender_account")
        
        if default_sender and isinstance(default_sender, dict):
            return default_sender
        
        return None
    
    def set_default_sender_account(
        self,
        user_id: str,
        provider: str,
        account_id: str
    ) -> bool:
        """
        Set default sender account for user.
        
        Args:
            user_id: User identifier
            provider: Email provider (gmail/outlook)
            account_id: Account identifier
        
        Returns:
            True if successful
        """
        settings = self.load_settings(user_id)
        settings["default_sender_account"] = {
            "provider": provider,
            "account_id": account_id
        }
        return self.save_settings(user_id, settings)


# Singleton instance
_user_settings = None


def get_user_settings() -> UserSettings:
    """Get the singleton user settings instance."""
    global _user_settings
    if _user_settings is None:
        _user_settings = UserSettings()
    return _user_settings

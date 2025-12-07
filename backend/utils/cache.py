"""
Caching utility for storing and retrieving transcripts.
"""

import logging
import json
import hashlib
from pathlib import Path
from typing import Optional, Dict, Any
from datetime import datetime
import os

logger = logging.getLogger(__name__)


class TranscriptCache:
    """
    Manages caching of transcripts to avoid re-processing.
    """
    
    def __init__(self, cache_dir: str = None):
        """
        Initialize the transcript cache.
        
        Args:
            cache_dir: Directory to store cached transcripts (default: ./cache/transcripts)
        """
        if cache_dir is None:
            # Use cache directory in project root
            cache_dir = os.path.join(os.getcwd(), 'cache', 'transcripts')
        
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"Transcript cache initialized at: {self.cache_dir}")
    
    def _get_cache_key(self, identifier: str) -> str:
        """
        Generate a cache key from an identifier (e.g., YouTube video ID or file hash).
        
        Args:
            identifier: Unique identifier for the content
            
        Returns:
            Cache key (hashed)
        """
        # Use SHA256 hash for consistent key generation
        return hashlib.sha256(identifier.encode()).hexdigest()
    
    def _get_cache_path(self, cache_key: str) -> Path:
        """
        Get the file path for a cached transcript.
        
        Args:
            cache_key: The cache key
            
        Returns:
            Path to the cache file
        """
        return self.cache_dir / f"{cache_key}.json"
    
    def get(self, identifier: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve a cached transcript.
        
        Args:
            identifier: Unique identifier (YouTube video ID, file hash, etc.)
            
        Returns:
            Cached transcript data or None if not found
        """
        try:
            cache_key = self._get_cache_key(identifier)
            cache_path = self._get_cache_path(cache_key)
            
            if not cache_path.exists():
                logger.debug(f"Cache miss for identifier: {identifier}")
                return None
            
            with open(cache_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            logger.info(f"Cache hit for identifier: {identifier}")
            return data
            
        except Exception as e:
            logger.error(f"Error reading cache for {identifier}: {e}")
            return None
    
    def set(
        self,
        identifier: str,
        transcript: str,
        metadata: Dict[str, Any] = None
    ) -> bool:
        """
        Store a transcript in the cache.
        
        Args:
            identifier: Unique identifier (YouTube video ID, file hash, etc.)
            transcript: The transcript text
            metadata: Additional metadata (language, duration, etc.)
            
        Returns:
            True if successfully cached, False otherwise
        """
        try:
            cache_key = self._get_cache_key(identifier)
            cache_path = self._get_cache_path(cache_key)
            
            data = {
                'identifier': identifier,
                'transcript': transcript,
                'cached_at': datetime.utcnow().isoformat(),
                'metadata': metadata or {}
            }
            
            with open(cache_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            
            logger.info(f"Cached transcript for identifier: {identifier}")
            return True
            
        except Exception as e:
            logger.error(f"Error caching transcript for {identifier}: {e}")
            return False
    
    def delete(self, identifier: str) -> bool:
        """
        Delete a cached transcript.
        
        Args:
            identifier: Unique identifier
            
        Returns:
            True if successfully deleted, False otherwise
        """
        try:
            cache_key = self._get_cache_key(identifier)
            cache_path = self._get_cache_path(cache_key)
            
            if cache_path.exists():
                cache_path.unlink()
                logger.info(f"Deleted cache for identifier: {identifier}")
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"Error deleting cache for {identifier}: {e}")
            return False
    
    def clear_all(self) -> int:
        """
        Clear all cached transcripts.
        
        Returns:
            Number of cache files deleted
        """
        try:
            count = 0
            for cache_file in self.cache_dir.glob("*.json"):
                cache_file.unlink()
                count += 1
            
            logger.info(f"Cleared {count} cached transcripts")
            return count
            
        except Exception as e:
            logger.error(f"Error clearing cache: {e}")
            return 0
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """
        Get cache statistics.
        
        Returns:
            Dictionary with cache statistics
        """
        try:
            cache_files = list(self.cache_dir.glob("*.json"))
            total_size = sum(f.stat().st_size for f in cache_files)
            
            return {
                'num_cached': len(cache_files),
                'total_size_bytes': total_size,
                'total_size_mb': round(total_size / (1024 * 1024), 2),
                'cache_dir': str(self.cache_dir)
            }
            
        except Exception as e:
            logger.error(f"Error getting cache stats: {e}")
            return {}


def compute_file_hash(filepath: str, chunk_size: int = 8192) -> str:
    """
    Compute SHA256 hash of a file for caching purposes.
    
    Args:
        filepath: Path to the file
        chunk_size: Size of chunks to read (default: 8KB)
        
    Returns:
        Hexadecimal hash string
    """
    sha256_hash = hashlib.sha256()
    
    with open(filepath, 'rb') as f:
        for chunk in iter(lambda: f.read(chunk_size), b''):
            sha256_hash.update(chunk)
    
    return sha256_hash.hexdigest()


# Global cache instance
_cache_instance = None


def get_cache() -> TranscriptCache:
    """
    Get the global transcript cache instance (singleton).
    
    Returns:
        TranscriptCache instance
    """
    global _cache_instance
    if _cache_instance is None:
        _cache_instance = TranscriptCache()
    return _cache_instance

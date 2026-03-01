"""
Text processing utilities for document chunking, language detection, and text extraction.
Shared across document analysis, translation, and knowledge base features.
"""

import logging
import re
from typing import List, Tuple, Optional
from langdetect import detect, LangDetectException

logger = logging.getLogger(__name__)


def detect_language(text: str) -> Optional[str]:
    """
    Detect the language of given text using langdetect.
    
    Args:
        text: Text to analyze
        
    Returns:
        Language code (e.g., 'en', 'de', 'fr') or None if detection fails
    """
    try:
        # Need at least some text to detect language
        if not text or len(text.strip()) < 10:
            logger.warning("Text too short for reliable language detection")
            return None
        
        language = detect(text)
        logger.info(f"Detected language: {language}")
        return language
        
    except LangDetectException as e:
        logger.warning(f"Language detection failed: {e}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error in language detection: {e}")
        return None


def chunk_text(
    text: str,
    max_chunk_chars: int = 12000,  # ~3000 tokens
    overlap_chars: int = 800,       # ~200 tokens
    preserve_paragraphs: bool = True
) -> List[str]:
    """
    Split text into overlapping chunks for processing.
    
    This is critical for:
    - Document summarization (avoid token limits)
    - RAG embeddings (optimal chunk size)
    - Translation (maintain context)
    
    Args:
        text: Text to chunk
        max_chunk_chars: Maximum characters per chunk
        overlap_chars: Overlap between chunks for context
        preserve_paragraphs: Try to split on paragraph boundaries
        
    Returns:
        List of text chunks
    """
    if not text:
        return []
    
    # If text is shorter than max chunk, return as single chunk
    if len(text) <= max_chunk_chars:
        return [text]
    
    chunks = []
    
    if preserve_paragraphs:
        # Split on paragraph boundaries (double newline or single newline)
        paragraphs = re.split(r'\n\s*\n|\n', text)
        
        current_chunk = ""
        for para in paragraphs:
            # If adding this paragraph would exceed max, save current chunk
            if len(current_chunk) + len(para) + 1 > max_chunk_chars and current_chunk:
                chunks.append(current_chunk.strip())
                # Start new chunk with overlap from previous
                overlap_text = current_chunk[-overlap_chars:] if len(current_chunk) > overlap_chars else current_chunk
                current_chunk = overlap_text + "\n" + para
            else:
                current_chunk += ("\n" if current_chunk else "") + para
        
        # Add the last chunk
        if current_chunk:
            chunks.append(current_chunk.strip())
    
    else:
        # Simple character-based chunking with overlap
        start = 0
        while start < len(text):
            end = start + max_chunk_chars
            chunk = text[start:end]
            chunks.append(chunk)
            start = end - overlap_chars
    
    logger.info(f"Split text into {len(chunks)} chunks (max_chars={max_chunk_chars}, overlap={overlap_chars})")
    return chunks


def extract_keywords(text: str, num_keywords: int = 10) -> List[str]:
    """
    Extract simple keywords from text using frequency analysis.
    
    Args:
        text: Text to analyze
        num_keywords: Number of keywords to extract
        
    Returns:
        List of keywords
    """
    # Simple implementation: word frequency
    # Remove common words (basic stop words)
    stop_words = {
        'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for',
        'of', 'with', 'by', 'from', 'as', 'is', 'was', 'are', 'were', 'been',
        'be', 'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would',
        'should', 'could', 'may', 'might', 'can', 'this', 'that', 'these',
        'those', 'i', 'you', 'he', 'she', 'it', 'we', 'they', 'what', 'which',
        'who', 'when', 'where', 'why', 'how', 'all', 'each', 'every', 'both',
        'few', 'more', 'most', 'other', 'some', 'such', 'no', 'nor', 'not',
        'only', 'own', 'same', 'so', 'than', 'too', 'very'
    }
    
    # Extract words (alphanumeric sequences)
    words = re.findall(r'\b[a-zA-Z]{3,}\b', text.lower())
    
    # Count frequencies, excluding stop words
    word_freq = {}
    for word in words:
        if word not in stop_words:
            word_freq[word] = word_freq.get(word, 0) + 1
    
    # Sort by frequency and return top N
    sorted_words = sorted(word_freq.items(), key=lambda x: x[1], reverse=True)
    keywords = [word for word, freq in sorted_words[:num_keywords]]
    
    logger.info(f"Extracted {len(keywords)} keywords")
    return keywords


def clean_text(text: str) -> str:
    """
    Clean and normalize text.
    
    Args:
        text: Text to clean
        
    Returns:
        Cleaned text
    """
    if not text:
        return ""
    
    # Remove extra whitespace
    text = re.sub(r'\s+', ' ', text)
    
    # Remove control characters
    text = re.sub(r'[\x00-\x1f\x7f-\x9f]', '', text)
    
    # Strip leading/trailing whitespace
    text = text.strip()
    
    return text


def estimate_tokens(text: str) -> int:
    """
    Estimate token count for text (rough approximation).
    OpenAI uses ~4 chars per token on average.
    
    Args:
        text: Text to estimate
        
    Returns:
        Estimated token count
    """
    return len(text) // 4


def truncate_text(text: str, max_tokens: int = 1000) -> str:
    """
    Truncate text to approximate token limit.
    
    Args:
        text: Text to truncate
        max_tokens: Maximum tokens
        
    Returns:
        Truncated text
    """
    max_chars = max_tokens * 4
    if len(text) <= max_chars:
        return text
    
    # Truncate and add ellipsis
    return text[:max_chars - 3] + "..."


def merge_text_chunks(chunks: List[Tuple[int, str]]) -> str:
    """
    Merge text chunks that may be out of order.
    
    Args:
        chunks: List of (index, text) tuples
        
    Returns:
        Merged text
    """
    # Sort by index
    sorted_chunks = sorted(chunks, key=lambda x: x[0])
    
    # Join with newlines
    merged = "\n\n".join(text for _, text in sorted_chunks)
    
    return merged

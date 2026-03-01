"""
Data models for Knowledge Base (RAG) feature.
"""

from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from datetime import datetime


class KBAddRequest(BaseModel):
    """Request to add content to knowledge base."""
    content: str = Field(..., description="Text content to add")
    title: Optional[str] = Field(None, description="Content title")
    source_type: str = Field(
        default="note",
        description="Type of content: note, document, transcript, etc."
    )
    source_id: Optional[str] = Field(None, description="ID of source (if from document/transcript)")
    metadata: Optional[Dict[str, Any]] = Field(default={}, description="Additional metadata")


class KBAddResponse(BaseModel):
    """Response after adding content."""
    content_id: str = Field(..., description="Unique content ID")
    num_chunks: int = Field(..., description="Number of chunks created")
    message: str = Field(default="Content added to knowledge base")


class KBSearchRequest(BaseModel):
    """Request to search knowledge base."""
    query: str = Field(..., description="Search query")
    top_k: int = Field(default=5, ge=1, le=20, description="Number of results to return")
    min_score: float = Field(
        default=0.1,
        ge=0.0,
        le=1.0,
        description="Minimum similarity score (0-1)"
    )
    source_type_filter: Optional[str] = Field(
        None,
        description="Filter by source type"
    )


class KBSearchResult(BaseModel):
    """Single search result."""
    content_id: str = Field(..., description="Content ID")
    chunk_text: str = Field(..., description="Relevant text chunk")
    score: float = Field(..., description="Similarity score (0-1)")
    title: Optional[str] = Field(None, description="Content title")
    source_type: str = Field(..., description="Source type")
    metadata: Dict[str, Any] = Field(default={}, description="Content metadata")


class KBSearchResponse(BaseModel):
    """Response from search."""
    query: str = Field(..., description="Original query")
    results: List[KBSearchResult] = Field(..., description="Search results")
    total_results: int = Field(..., description="Total number of results")


class KBChatRequest(BaseModel):
    """Request for RAG-based chat."""
    question: str = Field(..., description="User's question")
    conversation_history: Optional[List[Dict[str, str]]] = Field(
        default=[],
        description="Previous conversation messages"
    )
    top_k: int = Field(default=3, ge=1, le=10, description="Number of context chunks to use")


class KBChatResponse(BaseModel):
    """Response from RAG chat."""
    question: str = Field(..., description="User's question")
    answer: str = Field(..., description="AI's answer")
    sources: List[KBSearchResult] = Field(..., description="Source chunks used for answer")


class KBContentInfo(BaseModel):
    """Information about a knowledge base content item."""
    content_id: str = Field(..., description="Content ID")
    title: Optional[str] = Field(None, description="Content title")
    content_preview: str = Field(..., description="Content preview")
    source_type: str = Field(..., description="Source type")
    num_chunks: int = Field(..., description="Number of chunks")
    added_at: str = Field(..., description="Timestamp when added")
    metadata: Dict[str, Any] = Field(default={}, description="Metadata")


class KBListResponse(BaseModel):
    """Response with list of KB content."""
    contents: List[KBContentInfo] = Field(..., description="List of content items")
    total: int = Field(..., description="Total number of items")


class KBDeleteResponse(BaseModel):
    """Response after deleting content."""
    content_id: str = Field(..., description="Deleted content ID")
    message: str = Field(default="Content removed from knowledge base")


class KBStats(BaseModel):
    """Knowledge base statistics."""
    total_contents: int = Field(..., description="Total number of content items")
    total_chunks: int = Field(..., description="Total number of chunks")
    index_size_mb: float = Field(..., description="Index size in MB")
    last_updated: Optional[str] = Field(None, description="Last update timestamp")
    by_source_type: Dict[str, int] = Field(
        default={},
        description="Content count by source type"
    )


class KBReindexResponse(BaseModel):
    """Response from reindex operation."""
    message: str = Field(..., description="Reindex result message")
    total_chunks: int = Field(..., description="Total chunks reindexed")
    duration_seconds: float = Field(..., description="Reindex duration")

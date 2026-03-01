"""
Data models for Document Summarization & Analysis feature.
"""

from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from datetime import datetime


class DocumentMetadata(BaseModel):
    """Metadata for a document."""
    uploaded_at: str = Field(..., description="Upload timestamp (ISO format)")
    file_size: int = Field(..., description="File size in bytes")
    language: Optional[str] = Field(None, description="Detected language code")
    num_pages: Optional[int] = Field(None, description="Number of pages (for PDFs)")
    num_chunks: int = Field(..., description="Number of text chunks")


class DocumentUploadResponse(BaseModel):
    """Response after uploading a document."""
    document_id: str = Field(..., description="Unique document ID")
    filename: str = Field(..., description="Original filename")
    text_length: int = Field(..., description="Length of extracted text")
    metadata: DocumentMetadata = Field(..., description="Document metadata")
    message: str = Field(default="Document uploaded successfully")


class DocumentSummaryRequest(BaseModel):
    """Request for document summarization."""
    document_id: str = Field(..., description="Document ID to summarize")
    summary_length: Optional[str] = Field(
        default="medium",
        description="Summary length: short, medium, or long"
    )
    include_key_points: bool = Field(
        default=True,
        description="Whether to include key points"
    )


class DocumentSummaryResponse(BaseModel):
    """Response with document summary."""
    document_id: str = Field(..., description="Document ID")
    summary: str = Field(..., description="Generated summary")
    key_points: Optional[List[str]] = Field(None, description="Key points extracted")
    language: Optional[str] = Field(None, description="Document language")


class DocumentChatRequest(BaseModel):
    """Request for chatting with a document."""
    document_id: str = Field(..., description="Document ID")
    question: str = Field(..., description="Question about the document")
    conversation_history: Optional[List[Dict[str, str]]] = Field(
        default=[],
        description="Previous conversation messages"
    )


class DocumentChatResponse(BaseModel):
    """Response from document chat."""
    document_id: str = Field(..., description="Document ID")
    question: str = Field(..., description="User's question")
    answer: str = Field(..., description="AI's answer")
    relevant_chunks: Optional[List[str]] = Field(
        None,
        description="Relevant text chunks used for answering"
    )


class DocumentInfo(BaseModel):
    """Full document information."""
    document_id: str = Field(..., description="Unique document ID")
    filename: str = Field(..., description="Original filename")
    text_preview: str = Field(..., description="Preview of document text")
    metadata: DocumentMetadata = Field(..., description="Document metadata")
    summary: Optional[str] = Field(None, description="Cached summary if available")
    key_points: Optional[List[str]] = Field(None, description="Cached key points")


class DocumentListResponse(BaseModel):
    """Response with list of documents."""
    documents: List[DocumentInfo] = Field(..., description="List of documents")
    total: int = Field(..., description="Total number of documents")


class DocumentDeleteResponse(BaseModel):
    """Response after deleting a document."""
    document_id: str = Field(..., description="Deleted document ID")
    message: str = Field(default="Document deleted successfully")

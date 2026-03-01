"""
API endpoints for Document Summarization & Analysis.
"""

import logging
from fastapi import APIRouter, UploadFile, File, HTTPException, status
from typing import List
from models.document import (
    DocumentUploadResponse,
    DocumentSummaryRequest,
    DocumentSummaryResponse,
    DocumentChatRequest,
    DocumentChatResponse,
    DocumentInfo,
    DocumentListResponse,
    DocumentDeleteResponse,
    DocumentMetadata
)
from services.document_service import get_document_service
from core.error_handling import AppError

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/documents", tags=["documents"])


@router.post("/upload", response_model=DocumentUploadResponse)
async def upload_document(
    file: UploadFile = File(..., description="Document file (PDF, DOCX, TXT, MD)")
):
    """
    Upload and process a document.
    
    Supports:
    - PDF files
    - DOCX files
    - TXT files
    - MD (Markdown) files
    
    The document will be:
    1. Text extracted
    2. Chunked for processing
    3. Language detected
    4. Stored with unique ID
    
    Returns document ID and metadata for further operations.
    """
    try:
        logger.info(f"Document upload request: {file.filename}")
        
        service = get_document_service()
        doc_data = await service.upload_document(file)
        
        return DocumentUploadResponse(
            document_id=doc_data["id"],
            filename=doc_data["filename"],
            text_length=len(doc_data["text"]),
            metadata=DocumentMetadata(**doc_data["metadata"])
        )
        
    except AppError as e:
        logger.error(f"Document upload failed: {e.message}", exc_info=True)
        raise HTTPException(
            status_code=e.http_status,
            detail={
                "code": e.code,
                "message": e.message,
                "details": e.details
            }
        )
    except Exception as e:
        logger.error(f"Unexpected error in document upload: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={
                "code": "INTERNAL_ERROR",
                "message": "An unexpected error occurred",
                "details": {"error": str(e)}
            }
        )


@router.post("/summarize", response_model=DocumentSummaryResponse)
async def summarize_document(request: DocumentSummaryRequest):
    """
    Generate summary and key points for a document.
    
    Uses LLM to create:
    - Concise summary (adjustable length)
    - Key points/highlights as bullet list
    
    Results are cached for faster subsequent access.
    """
    try:
        logger.info(f"Document summarization request: {request.document_id}")
        
        service = get_document_service()
        result = await service.summarize_document(
            document_id=request.document_id,
            summary_length=request.summary_length,
            include_key_points=request.include_key_points
        )
        
        return DocumentSummaryResponse(
            document_id=request.document_id,
            summary=result["summary"],
            key_points=result.get("key_points"),
            language=result.get("language")
        )
        
    except AppError as e:
        logger.error(f"Document summarization failed: {e.message}", exc_info=True)
        raise HTTPException(
            status_code=e.http_status,
            detail={
                "code": e.code,
                "message": e.message,
                "details": e.details
            }
        )
    except Exception as e:
        logger.error(f"Unexpected error in document summarization: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={
                "code": "INTERNAL_ERROR",
                "message": "An unexpected error occurred",
                "details": {"error": str(e)}
            }
        )


@router.post("/chat", response_model=DocumentChatResponse)
async def chat_with_document(request: DocumentChatRequest):
    """
    Ask questions about a document (Q&A mode).
    
    Uses RAG (Retrieval-Augmented Generation):
    1. Finds relevant document sections
    2. Uses them as context for LLM
    3. Generates accurate, document-based answer
    
    Supports conversation history for follow-up questions.
    """
    try:
        logger.info(f"Document chat request: {request.document_id}")
        
        service = get_document_service()
        result = await service.chat_with_document(
            document_id=request.document_id,
            question=request.question,
            conversation_history=request.conversation_history
        )
        
        return DocumentChatResponse(
            document_id=request.document_id,
            question=request.question,
            answer=result["answer"],
            relevant_chunks=result.get("relevant_chunks")
        )
        
    except AppError as e:
        logger.error(f"Document chat failed: {e.message}", exc_info=True)
        raise HTTPException(
            status_code=e.http_status,
            detail={
                "code": e.code,
                "message": e.message,
                "details": e.details
            }
        )
    except Exception as e:
        logger.error(f"Unexpected error in document chat: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={
                "code": "INTERNAL_ERROR",
                "message": "An unexpected error occurred",
                "details": {"error": str(e)}
            }
        )


@router.get("/list", response_model=DocumentListResponse)
async def list_documents():
    """
    List all uploaded documents.
    
    Returns basic info for each document including:
    - Document ID
    - Filename
    - Text preview
    - Metadata
    - Cached summary (if available)
    """
    try:
        logger.info("Document list request")
        
        service = get_document_service()
        documents = service.list_documents()
        
        doc_infos = [
            DocumentInfo(
                document_id=doc["document_id"],
                filename=doc["filename"],
                text_preview=doc["text_preview"],
                metadata=DocumentMetadata(**doc["metadata"]),
                summary=doc.get("summary"),
                key_points=doc.get("key_points")
            )
            for doc in documents
        ]
        
        return DocumentListResponse(
            documents=doc_infos,
            total=len(doc_infos)
        )
        
    except Exception as e:
        logger.error(f"Unexpected error listing documents: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={
                "code": "INTERNAL_ERROR",
                "message": "An unexpected error occurred",
                "details": {"error": str(e)}
            }
        )


@router.get("/{document_id}", response_model=DocumentInfo)
async def get_document(document_id: str):
    """
    Get document information by ID.
    
    Returns full document metadata and cached analysis results.
    """
    try:
        logger.info(f"Document info request: {document_id}")
        
        service = get_document_service()
        doc_data = service.get_document(document_id)
        
        return DocumentInfo(
            document_id=doc_data["id"],
            filename=doc_data["filename"],
            text_preview=doc_data["text"][:500] + "...",
            metadata=DocumentMetadata(**doc_data["metadata"]),
            summary=doc_data.get("summary"),
            key_points=doc_data.get("key_points")
        )
        
    except AppError as e:
        logger.error(f"Get document failed: {e.message}", exc_info=True)
        raise HTTPException(
            status_code=e.http_status,
            detail={
                "code": e.code,
                "message": e.message,
                "details": e.details
            }
        )
    except Exception as e:
        logger.error(f"Unexpected error getting document: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={
                "code": "INTERNAL_ERROR",
                "message": "An unexpected error occurred",
                "details": {"error": str(e)}
            }
        )


@router.delete("/{document_id}", response_model=DocumentDeleteResponse)
async def delete_document(document_id: str):
    """
    Delete a document by ID.
    
    Removes document and all associated data.
    """
    try:
        logger.info(f"Document delete request: {document_id}")
        
        service = get_document_service()
        service.delete_document(document_id)
        
        return DocumentDeleteResponse(
            document_id=document_id,
            message="Document deleted successfully"
        )
        
    except AppError as e:
        logger.error(f"Delete document failed: {e.message}", exc_info=True)
        raise HTTPException(
            status_code=e.http_status,
            detail={
                "code": e.code,
                "message": e.message,
                "details": e.details
            }
        )
    except Exception as e:
        logger.error(f"Unexpected error deleting document: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={
                "code": "INTERNAL_ERROR",
                "message": "An unexpected error occurred",
                "details": {"error": str(e)}
            }
        )

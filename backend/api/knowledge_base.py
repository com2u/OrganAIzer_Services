"""
API endpoints for Knowledge Base (RAG) feature.
"""

import logging
from fastapi import APIRouter, HTTPException
from models.knowledge_base import (
    KBAddRequest,
    KBAddResponse,
    KBSearchRequest,
    KBSearchResponse,
    KBSearchResult,
    KBChatRequest,
    KBChatResponse,
    KBListResponse,
    KBContentInfo,
    KBDeleteResponse,
    KBStats,
    KBReindexResponse
)
from services.knowledge_base_service import get_kb_service
from core.error_handling import AppError

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/kb", tags=["knowledge-base"])


@router.post("/add", response_model=KBAddResponse)
async def add_content(request: KBAddRequest):
    """
    Add content to the knowledge base.
    
    Content can be:
    - Notes
    - Document summaries
    - Transcriptions
    - Any text you want to remember
    
    The content will be:
    1. Chunked for optimal search
    2. Indexed for semantic search
    3. Available for RAG chat
    """
    try:
        logger.info(f"KB add content request: type={request.source_type}")
        
        service = get_kb_service()
        result = service.add_content(
            content=request.content,
            title=request.title,
            source_type=request.source_type,
            source_id=request.source_id,
            metadata=request.metadata
        )
        
        return KBAddResponse(
            content_id=result["content_id"],
            num_chunks=result["num_chunks"]
        )
        
    except AppError as e:
        logger.error(f"KB add content failed: {e.message}", exc_info=True)
        raise HTTPException(
            status_code=e.http_status,
            detail={
                "code": e.code,
                "message": e.message,
                "details": e.details
            }
        )
    except Exception as e:
        logger.error(f"Unexpected error adding content to KB: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={
                "code": "INTERNAL_ERROR",
                "message": "An unexpected error occurred",
                "details": {"error": str(e)}
            }
        )


@router.post("/search", response_model=KBSearchResponse)
async def search_knowledge_base(request: KBSearchRequest):
    """
    Search the knowledge base.
    
    Uses semantic search (TF-IDF + cosine similarity) to find
    relevant content chunks.
    
    Features:
    - Semantic similarity matching
    - Adjustable result count
    - Minimum score filtering
    - Source type filtering
    """
    try:
        logger.info(f"KB search request: query='{request.query[:50]}...'")
        
        service = get_kb_service()
        results = service.search(
            query=request.query,
            top_k=request.top_k,
            min_score=request.min_score,
            source_type_filter=request.source_type_filter
        )
        
        search_results = [
            KBSearchResult(
                content_id=r["content_id"],
                chunk_text=r["chunk_text"],
                score=r["score"],
                title=r.get("title"),
                source_type=r["source_type"],
                metadata=r.get("metadata", {})
            )
            for r in results
        ]
        
        return KBSearchResponse(
            query=request.query,
            results=search_results,
            total_results=len(search_results)
        )
        
    except Exception as e:
        logger.error(f"KB search failed: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={
                "code": "SEARCH_FAILED",
                "message": "Failed to search knowledge base",
                "details": {"error": str(e)}
            }
        )


@router.post("/chat", response_model=KBChatResponse)
async def chat_with_knowledge_base(request: KBChatRequest):
    """
    Chat with your knowledge base using RAG.
    
    This is OrganAIzer's memory - ask questions and get answers
    based on everything you've stored.
    
    Process:
    1. Search for relevant content
    2. Use as context for LLM
    3. Generate accurate, sourced answer
    
    Supports conversation history for follow-up questions.
    """
    try:
        logger.info(f"KB chat request: question='{request.question[:50]}...'")
        
        service = get_kb_service()
        result = await service.chat(
            question=request.question,
            conversation_history=request.conversation_history,
            top_k=request.top_k
        )
        
        sources = [
            KBSearchResult(
                content_id=s["content_id"],
                chunk_text=s["chunk_text"],
                score=s["score"],
                title=s.get("title"),
                source_type=s["source_type"],
                metadata=s.get("metadata", {})
            )
            for s in result["sources"]
        ]
        
        return KBChatResponse(
            question=request.question,
            answer=result["answer"],
            sources=sources
        )
        
    except Exception as e:
        logger.error(f"KB chat failed: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={
                "code": "CHAT_FAILED",
                "message": "Failed to chat with knowledge base",
                "details": {"error": str(e)}
            }
        )


@router.get("/list", response_model=KBListResponse)
async def list_knowledge_base_contents():
    """
    List all content in the knowledge base.
    
    Returns summary information for each content item including:
    - Content ID and title
    - Content preview
    - Source type
    - Number of chunks
    - Metadata
    """
    try:
        logger.info("KB list request")
        
        service = get_kb_service()
        contents = service.list_contents()
        
        content_infos = [
            KBContentInfo(
                content_id=c["content_id"],
                title=c.get("title"),
                content_preview=c["content_preview"],
                source_type=c["source_type"],
                num_chunks=c["num_chunks"],
                added_at=c.get("added_at", ""),
                metadata=c.get("metadata", {})
            )
            for c in contents
        ]
        
        return KBListResponse(
            contents=content_infos,
            total=len(content_infos)
        )
        
    except Exception as e:
        logger.error(f"KB list failed: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={
                "code": "LIST_FAILED",
                "message": "Failed to list knowledge base contents",
                "details": {"error": str(e)}
            }
        )


@router.delete("/{content_id}", response_model=KBDeleteResponse)
async def delete_knowledge_base_content(content_id: str):
    """
    Delete content from the knowledge base.
    
    This will:
    1. Remove the content
    2. Rebuild the search index
    """
    try:
        logger.info(f"KB delete request: {content_id}")
        
        service = get_kb_service()
        service.delete_content(content_id)
        
        return KBDeleteResponse(
            content_id=content_id,
            message="Content removed from knowledge base"
        )
        
    except AppError as e:
        logger.error(f"KB delete failed: {e.message}", exc_info=True)
        raise HTTPException(
            status_code=e.http_status,
            detail={
                "code": e.code,
                "message": e.message,
                "details": e.details
            }
        )
    except Exception as e:
        logger.error(f"Unexpected error deleting KB content: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={
                "code": "INTERNAL_ERROR",
                "message": "An unexpected error occurred",
                "details": {"error": str(e)}
            }
        )


@router.post("/reindex", response_model=KBReindexResponse)
async def reindex_knowledge_base():
    """
    Rebuild the knowledge base search index.
    
    Use this to:
    - Recover from index corruption
    - Optimize search performance
    - Apply index updates
    
    This may take a while for large knowledge bases.
    """
    try:
        logger.info("KB reindex request")
        
        service = get_kb_service()
        total_chunks, duration = service.reindex()
        
        return KBReindexResponse(
            message="Knowledge base reindexed successfully",
            total_chunks=total_chunks,
            duration_seconds=duration
        )
        
    except Exception as e:
        logger.error(f"KB reindex failed: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={
                "code": "REINDEX_FAILED",
                "message": "Failed to reindex knowledge base",
                "details": {"error": str(e)}
            }
        )


@router.get("/stats", response_model=KBStats)
async def get_knowledge_base_stats():
    """
    Get knowledge base statistics.
    
    Returns:
    - Total content items
    - Total chunks indexed
    - Index size
    - Breakdown by source type
    - Last update timestamp
    """
    try:
        logger.info("KB stats request")
        
        service = get_kb_service()
        stats = service.get_stats()
        
        return KBStats(
            total_contents=stats["total_contents"],
            total_chunks=stats["total_chunks"],
            index_size_mb=stats["index_size_mb"],
            last_updated=stats.get("last_updated"),
            by_source_type=stats.get("by_source_type", {})
        )
        
    except Exception as e:
        logger.error(f"KB stats failed: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={
                "code": "STATS_FAILED",
                "message": "Failed to get knowledge base statistics",
                "details": {"error": str(e)}
            }
        )

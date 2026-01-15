"""
Knowledge Base Service with RAG (Retrieval-Augmented Generation).
Provides persistent memory for OrganAIzer with semantic search and chat capabilities.
"""

import logging
import os
import json
import uuid
import time
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple

# Internal utilities and services
from utils.text_processing import chunk_text, clean_text, truncate_text
from utils.embeddings import SimpleEmbedder, build_index
from services.chat_service import get_chat_service
from core.error_handling import AppError
from core.config import config
from models.chat import ChatRequest

logger = logging.getLogger(__name__)


class KnowledgeBaseService:
    """
    Knowledge Base service with RAG capabilities.
    
    Architecture:
    - Content Storage: JSON files for each content item
    - Chunking: Text split into searchable chunks
    - Embeddings: TF-IDF based (simple, no API costs)
    - Retrieval: Cosine similarity search
    - Generation: LLM with retrieved context
    
    Design Decisions:
    1. TF-IDF embeddings instead of neural - simpler, faster, no API costs
    2. File-based storage - consistent with OrganAIzer patterns
    3. Separate chunk and content storage - optimize for search
    4. Incremental indexing - add without full rebuild
    """
    
    def __init__(self):
        """Initialize the knowledge base service."""
        # Storage directory
        self.storage_dir = Path(config.IMAGE_GEN_TEMP_DIR).parent / "knowledge_base"
        self.content_dir = self.storage_dir / "content"
        self.content_dir.mkdir(parents=True, exist_ok=True)
        
        # Index file
        self.index_file = self.storage_dir / "index.json"
        
        # In-memory index
        self.embedder: Optional[SimpleEmbedder] = None
        self.chunk_map: Dict[int, Dict[str, Any]] = {}  # chunk_index -> {content_id, chunk_index, text}
        
        # Load existing index
        self._load_index()
        
        logger.info(f"KnowledgeBaseService initialized, storage: {self.storage_dir}")
    
    def add_content(
        self,
        content: str,
        title: Optional[str] = None,
        source_type: str = "note",
        source_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Add content to the knowledge base.
        
        Process:
        1. Clean and validate content
        2. Chunk content
        3. Generate unique ID
        4. Store content
        5. Update search index
        
        Args:
            content: Text content to add
            title: Optional title
            source_type: Type of content (note, document, transcript, etc.)
            source_id: ID of source if applicable
            metadata: Additional metadata
            
        Returns:
            Dict with content_id and num_chunks
        """
        logger.info(f"Adding content to KB: type={source_type}")
        
        # Clean content
        content = clean_text(content)
        
        if not content or len(content) < 10:
            raise AppError(
                code="INVALID_CONTENT",
                message="Content is too short or empty",
                http_status=400
            )
        
        # Chunk content
        chunks = chunk_text(content, max_chunk_chars=8000, overlap_chars=400)
        logger.info(f"Content chunked into {len(chunks)} chunks")
        
        # Generate unique content ID
        content_id = str(uuid.uuid4())
        
        # Create content data
        content_data = {
            "id": content_id,
            "title": title,
            "content": content,
            "chunks": chunks,
            "source_type": source_type,
            "source_id": source_id,
            "added_at": datetime.utcnow().isoformat(),
            "metadata": metadata or {}
        }
        
        # Save content
        content_path = self.content_dir / f"{content_id}.json"
        with open(content_path, 'w', encoding='utf-8') as f:
            json.dump(content_data, f, indent=2, ensure_ascii=False)
        
        # Update search index
        self._add_to_index(content_id, chunks, title, source_type, metadata or {})
        
        logger.info(f"Content added to KB: {content_id}")
        return {
            "content_id": content_id,
            "num_chunks": len(chunks)
        }
    
    def search(
        self,
        query: str,
        top_k: int = 5,
        min_score: float = 0.1,
        source_type_filter: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Search the knowledge base.
        
        Args:
            query: Search query
            top_k: Number of results
            min_score: Minimum similarity score
            source_type_filter: Filter by source type
            
        Returns:
            List of search results with scores
        """
        logger.info(f"Searching KB: query='{query[:50]}...', top_k={top_k}")
        
        if not self.embedder or not self.embedder.is_fitted:
            logger.warning("Knowledge base is empty")
            return []
        
        # Search using embedder
        results = self.embedder.search(query, top_k=top_k * 2, min_score=min_score)
        
        # Map results to content info
        search_results = []
        for chunk_idx, score in results:
            if chunk_idx not in self.chunk_map:
                continue
            
            chunk_info = self.chunk_map[chunk_idx]
            
            # Apply source type filter if specified
            if source_type_filter and chunk_info.get("source_type") != source_type_filter:
                continue
            
            search_results.append({
                "content_id": chunk_info["content_id"],
                "chunk_text": chunk_info["text"],
                "score": score,
                "title": chunk_info.get("title"),
                "source_type": chunk_info.get("source_type", "unknown"),
                "metadata": chunk_info.get("metadata", {})
            })
            
            # Stop if we have enough results
            if len(search_results) >= top_k:
                break
        
        logger.info(f"Search returned {len(search_results)} results")
        return search_results
    
    async def chat(
        self,
        question: str,
        conversation_history: Optional[List[Dict[str, str]]] = None,
        top_k: int = 3
    ) -> Dict[str, Any]:
        """
        Chat with the knowledge base using RAG.
        
        Process:
        1. Search for relevant content chunks
        2. Build context from top results
        3. Generate answer using LLM with context
        
        Args:
            question: User's question
            conversation_history: Previous conversation
            top_k: Number of context chunks to use
            
        Returns:
            Dict with answer and sources
        """
        logger.info(f"KB chat: question='{question[:50]}...'")
        
        # Search for relevant content
        search_results = self.search(question, top_k=top_k, min_score=0.15)
        
        if not search_results:
            # No relevant content found
            logger.warning("No relevant content found in KB")
            return {
                "answer": "I don't have any relevant information in my knowledge base to answer that question.",
                "sources": []
            }
        
        # Build context from search results
        context_parts = []
        for i, result in enumerate(search_results[:top_k]):
            title_prefix = f"[{result.get('title', 'Untitled')}] " if result.get('title') else ""
            context_parts.append(f"{title_prefix}{result['chunk_text']}")
        
        context = "\n\n---\n\n".join(context_parts)
        
        # Build RAG prompt
        prompt = f"""Answer the question based on the following context from my knowledge base.
If the answer is not in the context, say so.

Context:
{truncate_text(context, max_tokens=2500)}

Question: {question}

Answer:"""
        
        # Get answer from LLM
        chat_service = get_chat_service()
        request = ChatRequest(
            prompt=prompt,
            conversation_history=conversation_history or [],
            temperature=0.4,
            max_tokens=1000
        )
        
        response = await chat_service.chat_completion(request)
        answer = response.response
        
        logger.info("KB chat response generated")
        return {
            "answer": answer,
            "sources": search_results[:top_k]
        }
    
    def get_content(self, content_id: str) -> Dict[str, Any]:
        """
        Get content by ID.
        
        Args:
            content_id: Content ID
            
        Returns:
            Content data
        """
        content_path = self.content_dir / f"{content_id}.json"
        if not content_path.exists():
            raise AppError(
                code="CONTENT_NOT_FOUND",
                message=f"Content not found: {content_id}",
                http_status=404
            )
        
        with open(content_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    
    def list_contents(self) -> List[Dict[str, Any]]:
        """
        List all content in knowledge base.
        
        Returns:
            List of content info
        """
        contents = []
        for content_path in self.content_dir.glob("*.json"):
            try:
                with open(content_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    contents.append({
                        "content_id": data["id"],
                        "title": data.get("title"),
                        "content_preview": data["content"][:200] + "...",
                        "source_type": data.get("source_type", "unknown"),
                        "num_chunks": len(data.get("chunks", [])),
                        "added_at": data.get("added_at"),
                        "metadata": data.get("metadata", {})
                    })
            except Exception as e:
                logger.error(f"Failed to load content {content_path}: {e}")
                continue
        
        return contents
    
    def delete_content(self, content_id: str) -> bool:
        """
        Delete content from knowledge base.
        
        Args:
            content_id: Content ID
            
        Returns:
            True if deleted
        """
        content_path = self.content_dir / f"{content_id}.json"
        if not content_path.exists():
            raise AppError(
                code="CONTENT_NOT_FOUND",
                message=f"Content not found: {content_id}",
                http_status=404
            )
        
        content_path.unlink()
        logger.info(f"Content deleted from KB: {content_id}")
        
        # Trigger reindex (simple approach - rebuild entire index)
        self.reindex()
        
        return True
    
    def reindex(self) -> Tuple[int, float]:
        """
        Rebuild the search index.
        
        Returns:
            Tuple of (total_chunks, duration_seconds)
        """
        logger.info("Reindexing knowledge base...")
        start_time = time.time()
        
        # Clear current index
        self.embedder = None
        self.chunk_map = {}
        
        # Reload all content and rebuild index
        all_chunks = []
        chunk_metadata = []
        
        for content_path in self.content_dir.glob("*.json"):
            try:
                with open(content_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                content_id = data["id"]
                chunks = data.get("chunks", [])
                title = data.get("title")
                source_type = data.get("source_type", "unknown")
                metadata = data.get("metadata", {})
                
                for chunk_idx, chunk_text in enumerate(chunks):
                    all_chunks.append(chunk_text)
                    chunk_metadata.append({
                        "content_id": content_id,
                        "chunk_index": chunk_idx,
                        "text": chunk_text,
                        "title": title,
                        "source_type": source_type,
                        "metadata": metadata
                    })
            
            except Exception as e:
                logger.error(f"Failed to load content {content_path}: {e}")
                continue
        
        if all_chunks:
            # Build new index
            self.embedder = build_index(all_chunks)
            
            # Update chunk map
            for i, meta in enumerate(chunk_metadata):
                self.chunk_map[i] = meta
            
            # Save index
            self._save_index()
        
        duration = time.time() - start_time
        logger.info(f"Reindexing complete: {len(all_chunks)} chunks in {duration:.2f}s")
        
        return len(all_chunks), duration
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Get knowledge base statistics.
        
        Returns:
            Statistics dictionary
        """
        total_contents = len(list(self.content_dir.glob("*.json")))
        total_chunks = len(self.chunk_map)
        
        # Calculate index size
        index_size = 0
        if self.index_file.exists():
            index_size = self.index_file.stat().st_size / (1024 * 1024)  # MB
        
        # Count by source type
        by_source_type = {}
        for meta in self.chunk_map.values():
            source_type = meta.get("source_type", "unknown")
            by_source_type[source_type] = by_source_type.get(source_type, 0) + 1
        
        # Get last updated timestamp
        last_updated = None
        if self.index_file.exists():
            last_updated = datetime.fromtimestamp(
                self.index_file.stat().st_mtime
            ).isoformat()
        
        return {
            "total_contents": total_contents,
            "total_chunks": total_chunks,
            "index_size_mb": round(index_size, 2),
            "last_updated": last_updated,
            "by_source_type": by_source_type
        }
    
    # Private helper methods
    
    def _add_to_index(
        self,
        content_id: str,
        chunks: List[str],
        title: Optional[str],
        source_type: str,
        metadata: Dict[str, Any]
    ) -> None:
        """Add chunks to search index."""
        if not self.embedder:
            # First content - create new index
            self.embedder = build_index(chunks)
            for i, chunk in enumerate(chunks):
                self.chunk_map[i] = {
                    "content_id": content_id,
                    "chunk_index": i,
                    "text": chunk,
                    "title": title,
                    "source_type": source_type,
                    "metadata": metadata
                }
        else:
            # Add to existing index
            start_idx = len(self.chunk_map)
            self.embedder.add_documents(chunks)
            
            for i, chunk in enumerate(chunks):
                self.chunk_map[start_idx + i] = {
                    "content_id": content_id,
                    "chunk_index": i,
                    "text": chunk,
                    "title": title,
                    "source_type": source_type,
                    "metadata": metadata
                }
        
        # Save updated index
        self._save_index()
    
    def _save_index(self) -> None:
        """Save index to disk."""
        if not self.embedder or not self.embedder.is_fitted:
            return
        
        index_data = {
            "embedder": self.embedder.to_dict(),
            "chunk_map": self.chunk_map,
            "updated_at": datetime.utcnow().isoformat()
        }
        
        with open(self.index_file, 'w', encoding='utf-8') as f:
            json.dump(index_data, f, indent=2)
        
        logger.debug("Index saved to disk")
    
    def _load_index(self) -> None:
        """Load index from disk."""
        if not self.index_file.exists():
            logger.info("No existing index found")
            return
        
        try:
            with open(self.index_file, 'r', encoding='utf-8') as f:
                index_data = json.load(f)
            
            # Rebuild embedder from saved data
            embedder_data = index_data.get("embedder", {})
            if embedder_data.get("is_fitted"):
                self.embedder = SimpleEmbedder.from_dict(embedder_data)
            
            # Load chunk map (convert string keys back to int)
            chunk_map_data = index_data.get("chunk_map", {})
            self.chunk_map = {int(k): v for k, v in chunk_map_data.items()}
            
            logger.info(f"Index loaded: {len(self.chunk_map)} chunks")
            
        except Exception as e:
            logger.error(f"Failed to load index: {e}", exc_info=True)
            logger.info("Will rebuild index on first use")


# Global service instance
_kb_service = None


def get_kb_service() -> KnowledgeBaseService:
    """Get or create the global KnowledgeBaseService instance."""
    global _kb_service
    if _kb_service is None:
        _kb_service = KnowledgeBaseService()
    return _kb_service

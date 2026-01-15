"""
Embedding utilities for RAG (Retrieval-Augmented Generation).
Uses TF-IDF for simple, dependency-light similarity search.
"""

import logging
import numpy as np
from typing import List, Tuple, Dict, Any
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

logger = logging.getLogger(__name__)


class SimpleEmbedder:
    """
    Simple embedding and similarity search using TF-IDF.
    No external API calls needed - fully local.
    
    Design Decision: Using TF-IDF instead of neural embeddings because:
    1. No API costs or rate limits
    2. Fast and deterministic
    3. Works well for keyword-based search
    4. Easy to understand and debug
    """
    
    def __init__(self, max_features: int = 5000):
        """
        Initialize the embedder.
        
        Args:
            max_features: Maximum number of features for TF-IDF
        """
        self.vectorizer = TfidfVectorizer(
            max_features=max_features,
            stop_words='english',
            ngram_range=(1, 2),  # Unigrams and bigrams
            min_df=1,
            max_df=0.9
        )
        self.documents: List[str] = []
        self.document_vectors = None
        self.is_fitted = False
        logger.info(f"SimpleEmbedder initialized with max_features={max_features}")
    
    def fit(self, documents: List[str]) -> None:
        """
        Fit the embedder on a collection of documents.
        
        Args:
            documents: List of text documents
        """
        if not documents:
            logger.warning("No documents provided to fit")
            return
        
        self.documents = documents
        self.document_vectors = self.vectorizer.fit_transform(documents)
        self.is_fitted = True
        logger.info(f"Embedder fitted on {len(documents)} documents")
    
    def add_documents(self, new_documents: List[str]) -> None:
        """
        Add new documents to the index (requires refitting).
        
        Args:
            new_documents: List of new text documents
        """
        all_documents = self.documents + new_documents
        self.fit(all_documents)
        logger.info(f"Added {len(new_documents)} documents, total: {len(all_documents)}")
    
    def embed_query(self, query: str) -> np.ndarray:
        """
        Embed a query string.
        
        Args:
            query: Query text
            
        Returns:
            Query vector
        """
        if not self.is_fitted:
            raise ValueError("Embedder not fitted. Call fit() first.")
        
        query_vector = self.vectorizer.transform([query])
        return query_vector
    
    def search(
        self,
        query: str,
        top_k: int = 5,
        min_score: float = 0.1
    ) -> List[Tuple[int, float]]:
        """
        Search for most similar documents to query.
        
        Args:
            query: Query text
            top_k: Number of results to return
            min_score: Minimum similarity score (0-1)
            
        Returns:
            List of (document_index, similarity_score) tuples
        """
        if not self.is_fitted:
            logger.warning("Embedder not fitted, returning empty results")
            return []
        
        # Embed query
        query_vector = self.embed_query(query)
        
        # Compute similarities
        similarities = cosine_similarity(query_vector, self.document_vectors)[0]
        
        # Get top K indices
        top_indices = np.argsort(similarities)[::-1][:top_k]
        
        # Filter by min_score and return results
        results = [
            (int(idx), float(similarities[idx]))
            for idx in top_indices
            if similarities[idx] >= min_score
        ]
        
        logger.info(f"Search returned {len(results)} results (top_k={top_k}, min_score={min_score})")
        return results
    
    def get_document(self, index: int) -> str:
        """
        Get document by index.
        
        Args:
            index: Document index
            
        Returns:
            Document text
        """
        if 0 <= index < len(self.documents):
            return self.documents[index]
        raise IndexError(f"Document index {index} out of range")
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Serialize embedder state to dictionary.
        
        Returns:
            Dictionary with embedder state
        """
        if not self.is_fitted:
            return {"is_fitted": False}
        
        return {
            "is_fitted": True,
            "documents": self.documents,
            "vocabulary": self.vectorizer.vocabulary_,
            "idf": self.vectorizer.idf_.tolist(),
            "max_features": self.vectorizer.max_features
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'SimpleEmbedder':
        """
        Deserialize embedder from dictionary.
        
        Args:
            data: Dictionary with embedder state
            
        Returns:
            SimpleEmbedder instance
        """
        if not data.get("is_fitted"):
            return cls()
        
        embedder = cls(max_features=data.get("max_features", 5000))
        embedder.fit(data["documents"])
        return embedder


def compute_similarity(vec1: np.ndarray, vec2: np.ndarray) -> float:
    """
    Compute cosine similarity between two vectors.
    
    Args:
        vec1: First vector
        vec2: Second vector
        
    Returns:
        Cosine similarity (0-1)
    """
    similarity = cosine_similarity(vec1.reshape(1, -1), vec2.reshape(1, -1))[0][0]
    return float(similarity)


def build_index(chunks: List[str]) -> SimpleEmbedder:
    """
    Build a searchable index from text chunks.
    
    Args:
        chunks: List of text chunks
        
    Returns:
        Fitted SimpleEmbedder
    """
    logger.info(f"Building index for {len(chunks)} chunks")
    embedder = SimpleEmbedder()
    embedder.fit(chunks)
    logger.info("Index built successfully")
    return embedder


def merge_search_results(
    results1: List[Tuple[int, float]],
    results2: List[Tuple[int, float]],
    alpha: float = 0.5
) -> List[Tuple[int, float]]:
    """
    Merge two sets of search results with weighted scoring.
    
    Args:
        results1: First result set
        results2: Second result set
        alpha: Weight for first result set (1-alpha for second)
        
    Returns:
        Merged and re-ranked results
    """
    # Combine scores
    scores: Dict[int, float] = {}
    
    for idx, score in results1:
        scores[idx] = scores.get(idx, 0.0) + alpha * score
    
    for idx, score in results2:
        scores[idx] = scores.get(idx, 0.0) + (1 - alpha) * score
    
    # Sort by combined score
    merged = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    
    return merged

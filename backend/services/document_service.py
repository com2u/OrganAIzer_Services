"""
Document Summarization & Analysis Service.
Handles document upload, text extraction, summarization, and Q&A.
"""

import logging
import os
import json
import uuid
from pathlib import Path
from datetime import datetime
from typing import Tuple, List, Optional, Dict, Any
from fastapi import UploadFile
import tempfile

# PDF extraction
import PyPDF2

# DOCX extraction
from docx import Document

# Internal utilities
from utils.text_processing import chunk_text, detect_language, clean_text, truncate_text
from services.chat_service import get_chat_service
from core.error_handling import AppError
from core.config import config

logger = logging.getLogger(__name__)


class DocumentService:
    """
    Service for document analysis and Q&A.
    
    Architecture:
    - Extract text from various formats (PDF, DOCX, TXT, MD)
    - Chunk large documents for processing
    - Use LLM for summarization and key point extraction
    - Enable conversational Q&A with document context
    """
    
    def __init__(self):
        """Initialize the document service."""
        # Storage directory for documents
        self.storage_dir = Path(config.IMAGE_GEN_TEMP_DIR).parent / "documents"
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"DocumentService initialized, storage: {self.storage_dir}")
    
    def extract_text_from_pdf(self, filepath: str) -> Tuple[str, int]:
        """
        Extract text from PDF file.
        
        Args:
            filepath: Path to PDF file
            
        Returns:
            Tuple of (extracted_text, num_pages)
        """
        try:
            text_parts = []
            with open(filepath, 'rb') as file:
                pdf_reader = PyPDF2.PdfReader(file)
                num_pages = len(pdf_reader.pages)
                
                for page_num, page in enumerate(pdf_reader.pages):
                    try:
                        page_text = page.extract_text()
                        if page_text:
                            text_parts.append(page_text)
                    except Exception as e:
                        logger.warning(f"Failed to extract page {page_num}: {e}")
                        continue
            
            full_text = "\n\n".join(text_parts)
            logger.info(f"Extracted {len(full_text)} chars from {num_pages} pages")
            return clean_text(full_text), num_pages
            
        except Exception as e:
            logger.error(f"PDF extraction failed: {e}", exc_info=True)
            raise AppError(
                code="PDF_EXTRACTION_FAILED",
                message=f"Failed to extract text from PDF: {str(e)}",
                http_status=500
            )
    
    def extract_text_from_docx(self, filepath: str) -> str:
        """
        Extract text from DOCX file.
        
        Args:
            filepath: Path to DOCX file
            
        Returns:
            Extracted text
        """
        try:
            doc = Document(filepath)
            paragraphs = [para.text for para in doc.paragraphs if para.text.strip()]
            full_text = "\n\n".join(paragraphs)
            logger.info(f"Extracted {len(full_text)} chars from DOCX")
            return clean_text(full_text)
            
        except Exception as e:
            logger.error(f"DOCX extraction failed: {e}", exc_info=True)
            raise AppError(
                code="DOCX_EXTRACTION_FAILED",
                message=f"Failed to extract text from DOCX: {str(e)}",
                http_status=500
            )
    
    def extract_text_from_txt(self, filepath: str) -> str:
        """
        Extract text from TXT/MD file.
        
        Args:
            filepath: Path to text file
            
        Returns:
            File content
        """
        try:
            with open(filepath, 'r', encoding='utf-8') as file:
                text = file.read()
            logger.info(f"Read {len(text)} chars from text file")
            return clean_text(text)
            
        except UnicodeDecodeError:
            # Try with different encoding
            try:
                with open(filepath, 'r', encoding='latin-1') as file:
                    text = file.read()
                logger.info(f"Read {len(text)} chars from text file (latin-1)")
                return clean_text(text)
            except Exception as e:
                raise AppError(
                    code="TEXT_EXTRACTION_FAILED",
                    message=f"Failed to read text file: {str(e)}",
                    http_status=500
                )
        except Exception as e:
            logger.error(f"Text extraction failed: {e}", exc_info=True)
            raise AppError(
                code="TEXT_EXTRACTION_FAILED",
                message=f"Failed to read text file: {str(e)}",
                http_status=500
            )
    
    async def upload_document(
        self,
        file: UploadFile
    ) -> Dict[str, Any]:
        """
        Upload and process a document.
        
        Process:
        1. Validate file type
        2. Save temporary file
        3. Extract text based on type
        4. Chunk text
        5. Detect language
        6. Store document data
        
        Args:
            file: Uploaded file
            
        Returns:
            Document data with ID and metadata
        """
        logger.info(f"Processing document upload: {file.filename}")
        
        # Validate file type
        if not file.filename:
            raise AppError(
                code="INVALID_FILE",
                message="No filename provided",
                http_status=400
            )
        
        file_ext = Path(file.filename).suffix.lower()
        allowed_extensions = {'.pdf', '.docx', '.txt', '.md'}
        
        if file_ext not in allowed_extensions:
            raise AppError(
                code="INVALID_FILE_FORMAT",
                message=f"Unsupported file format: {file_ext}. Allowed: {', '.join(allowed_extensions)}",
                http_status=400
            )
        
        # Read file contents
        file_contents = await file.read()
        if not file_contents:
            raise AppError(
                code="EMPTY_FILE",
                message="Uploaded file is empty",
                http_status=400
            )
        
        file_size = len(file_contents)
        logger.info(f"File size: {file_size / 1024:.2f} KB")
        
        # Save to temporary file
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=file_ext)
        try:
            temp_file.write(file_contents)
            temp_file.close()
            
            # Extract text based on file type
            num_pages = None
            if file_ext == '.pdf':
                text, num_pages = self.extract_text_from_pdf(temp_file.name)
            elif file_ext == '.docx':
                text = self.extract_text_from_docx(temp_file.name)
            else:  # .txt or .md
                text = self.extract_text_from_txt(temp_file.name)
            
            if not text or len(text.strip()) < 10:
                raise AppError(
                    code="NO_TEXT_EXTRACTED",
                    message="Could not extract meaningful text from document",
                    http_status=400
                )
            
            # Chunk the text
            chunks = chunk_text(text)
            
            # Detect language
            language = detect_language(text[:1000])  # Use first 1000 chars
            
            # Generate unique document ID
            doc_id = str(uuid.uuid4())
            
            # Create document data
            doc_data = {
                "id": doc_id,
                "filename": file.filename,
                "text": text,
                "chunks": chunks,
                "metadata": {
                    "uploaded_at": datetime.utcnow().isoformat(),
                    "file_size": file_size,
                    "language": language,
                    "num_pages": num_pages,
                    "num_chunks": len(chunks)
                },
                "summary": None,
                "key_points": None
            }
            
            # Save document data
            doc_path = self.storage_dir / f"{doc_id}.json"
            with open(doc_path, 'w', encoding='utf-8') as f:
                json.dump(doc_data, f, indent=2, ensure_ascii=False)
            
            logger.info(f"Document saved: {doc_id}")
            return doc_data
            
        finally:
            # Clean up temporary file
            if os.path.exists(temp_file.name):
                os.unlink(temp_file.name)
    
    async def summarize_document(
        self,
        document_id: str,
        summary_length: str = "medium",
        include_key_points: bool = True
    ) -> Dict[str, Any]:
        """
        Generate summary and key points for a document.
        
        Uses LLM to:
        1. Create a summary (length-adjustable)
        2. Extract key points as bullet list
        
        Args:
            document_id: Document ID
            summary_length: "short", "medium", or "long"
            include_key_points: Whether to extract key points
            
        Returns:
            Summary and key points
        """
        logger.info(f"Summarizing document: {document_id} (length={summary_length})")
        
        # Load document
        doc_data = self._load_document(document_id)
        
        # Check if summary is already cached
        if doc_data.get("summary") and not include_key_points:
            logger.info("Returning cached summary")
            return {
                "summary": doc_data["summary"],
                "key_points": doc_data.get("key_points"),
                "language": doc_data["metadata"].get("language")
            }
        
        # Prepare text for summarization
        text = doc_data["text"]
        chunks = doc_data["chunks"]
        
        # If document is small, summarize directly
        if len(chunks) == 1:
            summary_prompt = self._build_summary_prompt(text, summary_length, include_key_points)
            summary_result = await self._call_llm(summary_prompt)
        else:
            # For large documents: summarize each chunk, then combine
            chunk_summaries = []
            for i, chunk in enumerate(chunks):
                logger.info(f"Summarizing chunk {i+1}/{len(chunks)}")
                chunk_prompt = f"Summarize this section briefly:\n\n{chunk}"
                chunk_summary = await self._call_llm(chunk_prompt)
                chunk_summaries.append(chunk_summary)
            
            # Combine chunk summaries into final summary
            combined = "\n\n".join(chunk_summaries)
            final_prompt = self._build_summary_prompt(combined, summary_length, include_key_points)
            summary_result = await self._call_llm(final_prompt)
        
        # Parse summary and key points
        summary, key_points = self._parse_summary_response(summary_result, include_key_points)
        
        # Cache the results
        doc_data["summary"] = summary
        doc_data["key_points"] = key_points
        self._save_document(doc_data)
        
        logger.info("Document summarization complete")
        return {
            "summary": summary,
            "key_points": key_points,
            "language": doc_data["metadata"].get("language")
        }
    
    async def chat_with_document(
        self,
        document_id: str,
        question: str,
        conversation_history: List[Dict[str, str]] = None
    ) -> Dict[str, Any]:
        """
        Answer questions about a document using RAG.
        
        Process:
        1. Load document chunks
        2. Find relevant chunks (simple keyword matching)
        3. Build context from relevant chunks
        4. Generate answer using LLM
        
        Args:
            document_id: Document ID
            question: User's question
            conversation_history: Previous conversation
            
        Returns:
            Answer and relevant chunks
        """
        logger.info(f"Document Q&A: {document_id}")
        
        # Load document
        doc_data = self._load_document(document_id)
        chunks = doc_data["chunks"]
        
        # Simple relevance scoring (keyword overlap)
        relevant_chunks = self._find_relevant_chunks(question, chunks, top_k=3)
        
        # Build context from relevant chunks
        context = "\n\n".join(relevant_chunks)
        
        # Build Q&A prompt
        prompt = f"""Based on the following document excerpts, answer the question.
        
Document context:
{truncate_text(context, max_tokens=2000)}

Question: {question}

Provide a clear, concise answer based on the document content. If the answer is not in the document, say so."""
        
        # Get answer from LLM
        answer = await self._call_llm(prompt, conversation_history)
        
        logger.info("Document Q&A complete")
        return {
            "answer": answer,
            "relevant_chunks": relevant_chunks[:2]  # Return top 2 for reference
        }
    
    def get_document(self, document_id: str) -> Dict[str, Any]:
        """
        Get document information.
        
        Args:
            document_id: Document ID
            
        Returns:
            Document data
        """
        return self._load_document(document_id)
    
    def list_documents(self) -> List[Dict[str, Any]]:
        """
        List all documents.
        
        Returns:
            List of document info
        """
        documents = []
        for doc_path in self.storage_dir.glob("*.json"):
            try:
                with open(doc_path, 'r', encoding='utf-8') as f:
                    doc_data = json.load(f)
                    # Return minimal info for listing
                    documents.append({
                        "document_id": doc_data["id"],
                        "filename": doc_data["filename"],
                        "text_preview": doc_data["text"][:200] + "...",
                        "metadata": doc_data["metadata"],
                        "summary": doc_data.get("summary"),
                        "key_points": doc_data.get("key_points")
                    })
            except Exception as e:
                logger.error(f"Failed to load document {doc_path}: {e}")
                continue
        
        return documents
    
    def delete_document(self, document_id: str) -> bool:
        """
        Delete a document.
        
        Args:
            document_id: Document ID
            
        Returns:
            True if deleted
        """
        doc_path = self.storage_dir / f"{document_id}.json"
        if doc_path.exists():
            doc_path.unlink()
            logger.info(f"Document deleted: {document_id}")
            return True
        
        raise AppError(
            code="DOCUMENT_NOT_FOUND",
            message=f"Document not found: {document_id}",
            http_status=404
        )
    
    # Private helper methods
    
    def _load_document(self, document_id: str) -> Dict[str, Any]:
        """Load document data from storage."""
        doc_path = self.storage_dir / f"{document_id}.json"
        if not doc_path.exists():
            raise AppError(
                code="DOCUMENT_NOT_FOUND",
                message=f"Document not found: {document_id}",
                http_status=404
            )
        
        with open(doc_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    
    def _save_document(self, doc_data: Dict[str, Any]) -> None:
        """Save document data to storage."""
        doc_path = self.storage_dir / f"{doc_data['id']}.json"
        with open(doc_path, 'w', encoding='utf-8') as f:
            json.dump(doc_data, f, indent=2, ensure_ascii=False)
    
    def _build_summary_prompt(
        self,
        text: str,
        length: str,
        include_key_points: bool
    ) -> str:
        """Build prompt for summarization."""
        length_instructions = {
            "short": "in 2-3 sentences",
            "medium": "in 1-2 paragraphs",
            "long": "in 3-4 paragraphs with details"
        }
        
        instruction = length_instructions.get(length, length_instructions["medium"])
        
        prompt = f"Summarize the following text {instruction}:\n\n{truncate_text(text, max_tokens=3000)}"
        
        if include_key_points:
            prompt += "\n\nAlso provide 5-7 key points as a bullet list after the summary."
        
        return prompt
    
    async def _call_llm(
        self,
        prompt: str,
        conversation_history: List[Dict[str, str]] = None
    ) -> str:
        """Call LLM for text generation."""
        from models.chat import ChatRequest
        
        chat_service = get_chat_service()
        
        request = ChatRequest(
            prompt=prompt,
            conversation_history=conversation_history or [],
            temperature=0.3,  # Lower temperature for more factual responses
            max_tokens=1500
        )
        
        response = await chat_service.chat_completion(request)
        return response.response
    
    def _parse_summary_response(
        self,
        response: str,
        has_key_points: bool
    ) -> Tuple[str, Optional[List[str]]]:
        """Parse summary and key points from LLM response."""
        if not has_key_points:
            return response.strip(), None
        
        # Try to split summary from key points
        # Look for bullet points or numbered lists
        lines = response.split('\n')
        summary_lines = []
        key_point_lines = []
        in_key_points = False
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            # Detect start of key points section
            if any(marker in line.lower() for marker in ['key points:', 'key takeaways:', 'main points:']):
                in_key_points = True
                continue
            
            # Detect bullet points or numbered items
            if line.startswith(('-', '•', '*')) or (len(line) > 2 and line[0].isdigit() and line[1] in '.):'):
                in_key_points = True
                # Clean bullet/number
                cleaned = line.lstrip('-•*').strip()
                if cleaned and cleaned[0].isdigit():
                    cleaned = cleaned[cleaned.find(' ')+1:].strip() if ' ' in cleaned else cleaned
                key_point_lines.append(cleaned)
            elif in_key_points:
                # Continue key point from previous line
                if key_point_lines:
                    key_point_lines[-1] += " " + line
            else:
                summary_lines.append(line)
        
        summary = '\n'.join(summary_lines).strip()
        key_points = key_point_lines if key_point_lines else None
        
        return summary, key_points
    
    def _find_relevant_chunks(
        self,
        query: str,
        chunks: List[str],
        top_k: int = 3
    ) -> List[str]:
        """Find most relevant chunks using simple keyword matching."""
        # Extract keywords from query
        query_words = set(query.lower().split())
        
        # Score each chunk
        chunk_scores = []
        for i, chunk in enumerate(chunks):
            chunk_words = set(chunk.lower().split())
            # Simple overlap score
            overlap = len(query_words & chunk_words)
            chunk_scores.append((i, overlap, chunk))
        
        # Sort by score and return top K
        chunk_scores.sort(key=lambda x: x[1], reverse=True)
        relevant = [chunk for _, score, chunk in chunk_scores[:top_k] if score > 0]
        
        # If no matches, return first chunk
        if not relevant:
            relevant = [chunks[0]]
        
        return relevant


# Global service instance
_document_service = None


def get_document_service() -> DocumentService:
    """Get or create the global DocumentService instance."""
    global _document_service
    if _document_service is None:
        _document_service = DocumentService()
    return _document_service

# OrganAIzer - Three New Features Architecture

## Current Architecture Analysis

### Text Ingestion Flows
- **STT (Speech-to-Text)**: Audio files → Whisper API → transcript with language detection
  - Supports chunking for large files (>15MB)
  - Uses TranscriptCache for efficiency
  - Languages detected automatically via Whisper
- **Clipboard**: Handled by Chrome Extension (not backend)
- **File Support**: Currently only audio files (MP3, WAV, M4A, OGG, FLAC)

### Language Detection
- **STT**: Built-in Whisper language detection
- **Available**: langdetect library in requirements.txt
- **Current Usage**: Detects language in transcriptions

### Chat/LLM Infrastructure
- **Provider**: OpenRouter API
- **Service**: `ChatService` in `services/chat_service.py`
- **Features**: 
  - Conversation history support
  - Multiple model selection
  - Temperature and max_tokens configuration
- **Models**: ChatRequest, ChatResponse, ChatMessage (Pydantic)
- **Endpoint**: `/api/chat/completion`

### Storage System
- **Cache**: TranscriptCache (JSON-based) with SHA256 hashing
- **Location**: `./cache/transcripts/` for cached transcripts
- **Data**: `./data/tts/` and `./data/images/` for generated files
- **Pattern**: File-based storage with metadata

---

## New Features Architecture

### Design Principles
1. **Modularity**: Each feature is self-contained with its own service, models, and API
2. **Interoperability**: Features can call each other's services (e.g., Translator uses STT)
3. **Reusability**: Shared utilities for language detection, text extraction, chunking
4. **Simplicity**: No heavy dependencies; use existing LLM for embeddings via OpenRouter
5. **Consistency**: Follow existing patterns (services, models, cache, API structure)

---

## Feature 1: Document Summarization & Analysis

### Purpose
Transform documents → text → insights, complementing audio → text workflow

### Architecture

```
Document Upload → Text Extraction → Chunking → LLM Processing → Storage
                                           ↓
                                    Summarization
                                    Key Points
                                    Q&A Mode
```

### Components

**Service**: `backend/services/document_service.py`
- `extract_text_from_pdf()`: PDF → text using PyPDF2
- `extract_text_from_docx()`: DOCX → text using python-docx
- `extract_text_from_txt()`: TXT/MD → text (direct read)
- `chunk_document()`: Split large documents safely (token-aware)
- `summarize_document()`: Generate summary via LLM
- `extract_key_points()`: Bullet highlights via LLM
- `chat_with_document()`: Q&A with document context

**Models**: `backend/models/document.py`
- `DocumentUploadResponse`: Upload metadata
- `DocumentSummaryRequest/Response`: Summarization
- `DocumentChatRequest/Response`: Q&A mode
- `DocumentMetadata`: Stored document info

**API**: `backend/api/document.py`
- `POST /api/documents/upload`: Upload and extract text
- `POST /api/documents/summarize`: Get summary and key points
- `POST /api/documents/chat`: Ask questions about document
- `GET /api/documents/{id}`: Retrieve document metadata
- `DELETE /api/documents/{id}`: Remove document

**Storage**: `./data/documents/`
- Document text and metadata stored as JSON
- Format: `{doc_id}.json` with text, metadata, chunks

### Chunking Strategy
- Max chunk size: 3000 tokens (~12,000 chars)
- Overlap: 200 tokens for context continuity
- Preserves paragraph boundaries when possible

---

## Feature 2: Universal Translator

### Purpose
Unified translation hub leveraging STT, TTS, and LLM capabilities

### Architecture

```
Text Input → Language Detection → LLM Translation → Output
Audio Input → STT → Language Detection → LLM Translation → Optional TTS
File Input → Text Extraction → Language Detection → LLM Translation → Output
```

### Components

**Service**: `backend/services/translation_service.py`
- `detect_language()`: Detect source language using langdetect
- `translate_text()`: Text translation via LLM (most accurate)
- `translate_audio()`: Audio → STT → Translation → Optional TTS
- `translate_file()`: File → Text → Translation
- `get_supported_languages()`: Return language list

**Models**: `backend/models/translation.py`
- `TranslationRequest`: Source text/audio, target language
- `TranslationResponse`: Translated text, detected source lang
- `LanguageDetectionResponse`: Detected language info
- `AudioTranslationRequest`: Audio-specific translation

**API**: `backend/api/translation.py`
- `POST /api/translate/text`: Translate text
- `POST /api/translate/audio`: Translate audio file
- `POST /api/translate/file`: Translate text file
- `POST /api/translate/detect`: Detect language only
- `GET /api/translate/languages`: Supported languages

**Translation Flow**
1. Detect source language (langdetect for text, Whisper for audio)
2. Use LLM with specialized prompt: "Translate from {source} to {target}: {text}"
3. Return translation with confidence and detected language

### Reusability
- `translation_service.translate_text()` can be called by other features
- Exposed as shared utility for document translation, etc.

---

## Feature 3: Knowledge Base (RAG)

### Purpose
Persistent memory for OrganAIzer - searchable repository of all user content

### Architecture

```
Content Ingestion → Chunking → Embedding → Vector Store
                                                ↓
User Query → Embedding → Similarity Search → Context Retrieval → LLM Response
```

### Components

**Service**: `backend/services/knowledge_base_service.py`
- `add_content()`: Ingest new content (docs, notes, transcriptions)
- `remove_content()`: Delete content by ID
- `search()`: Query the knowledge base
- `chat_with_kb()`: Conversational RAG
- `reindex()`: Rebuild embeddings
- `get_stats()`: KB statistics

**Embedding Strategy** (Simple, No Heavy Dependencies)
- Use OpenRouter LLM to generate text embeddings
- Alternative: Simple TF-IDF with cosine similarity (no external service needed)
- Store embeddings as JSON vectors
- Cosine similarity for retrieval

**Models**: `backend/models/knowledge_base.py`
- `KBContent`: Content item with metadata
- `KBAddRequest/Response`: Add content
- `KBSearchRequest/Response`: Search query
- `KBChatRequest/Response`: RAG chat
- `KBStats`: Knowledge base statistics

**API**: `backend/api/knowledge_base.py`
- `POST /api/kb/add`: Add content
- `DELETE /api/kb/{id}`: Remove content
- `POST /api/kb/search`: Search content
- `POST /api/kb/chat`: Chat with knowledge base
- `POST /api/kb/reindex`: Rebuild index
- `GET /api/kb/stats`: Get statistics

**Storage**: `./data/knowledge_base/`
- `content/`: Individual content JSON files
- `index.json`: Vector index with embeddings
- `metadata.json`: KB-wide metadata

### RAG Pipeline
1. **Ingestion**: Text → Chunks → Embeddings → Store
2. **Retrieval**: Query → Embedding → Top-K similar chunks
3. **Generation**: Context + Query → LLM → Response

### Simple Embedding Method (No External Dependencies)
- Use sklearn's TfidfVectorizer (already available)
- OR use simple character n-grams + cosine similarity
- Store as numpy arrays serialized to JSON

---

## Integration Points

### Feature Interoperability

1. **Document → Knowledge Base**: Auto-add summarized documents to KB
2. **Translation → Documents**: Translate document summaries
3. **STT → Knowledge Base**: Store transcriptions in KB
4. **Knowledge Base → Chat**: Enhanced chat with memory

### Shared Utilities

**New**: `backend/utils/text_processing.py`
- `chunk_text()`: Smart text chunking
- `detect_language()`: Wrapper for langdetect
- `extract_keywords()`: Simple keyword extraction

**New**: `backend/utils/embeddings.py`
- `generate_embedding()`: Text → vector
- `compute_similarity()`: Cosine similarity
- `build_index()`: Create searchable index

---

## Frontend Components

### New Pages

1. **DocumentsPage.tsx**: Upload, summarize, chat with documents
2. **TranslatorPage.tsx**: Universal translation interface
3. **KnowledgeBasePage.tsx**: Search and chat with KB

### Navigation Updates
- Add new routes to `App.tsx`
- Update `TopNav.tsx` with new menu items

---

## Dependencies (Minimal Additions)

```
# Document processing
PyPDF2==3.0.1           # PDF text extraction
python-docx==1.1.0      # DOCX text extraction

# Embedding/similarity (use existing)
# langdetect is already installed
# Can use simple TF-IDF without scikit-learn if needed
# OR add: scikit-learn==1.3.2 for better embeddings
```

---

## Database Schema (File-Based)

### Documents
```json
{
  "id": "unique-id",
  "filename": "document.pdf",
  "text": "extracted text...",
  "chunks": ["chunk1...", "chunk2..."],
  "summary": "summary text...",
  "key_points": ["point1", "point2"],
  "metadata": {
    "uploaded_at": "timestamp",
    "file_size": 12345,
    "language": "en",
    "num_pages": 10
  }
}
```

### Knowledge Base Content
```json
{
  "id": "unique-id",
  "content": "text content...",
  "chunks": [
    {
      "text": "chunk text...",
      "embedding": [0.1, 0.2, ...],
      "metadata": {}
    }
  ],
  "source_type": "document|transcript|note",
  "source_id": "original-doc-id",
  "added_at": "timestamp",
  "metadata": {}
}
```

### Vector Index
```json
{
  "version": 1,
  "total_chunks": 150,
  "embeddings": [
    {
      "chunk_id": "content_id:chunk_index",
      "vector": [0.1, 0.2, ...],
      "content_id": "content-id"
    }
  ],
  "updated_at": "timestamp"
}
```

---

## Implementation Plan

1. ✅ Architecture design
2. Add new dependencies to requirements.txt
3. Implement shared utilities (text_processing, embeddings)
4. Implement Feature 1: Document Service
5. Implement Feature 2: Translation Service
6. Implement Feature 3: Knowledge Base Service
7. Create API endpoints for all features
8. Create data models for all features
9. Update main.py with new routers
10. Update config.py with new directories
11. Create frontend components
12. Integration testing
13. Documentation

---

## State Management

Each feature maintains state via:
- **File storage**: Persistent data in `./data/`
- **In-memory cache**: Fast access to frequently used items
- **Request context**: Current document, translation, or KB query

### State Tracking
- Document ID: Unique UUID per document
- Translation jobs: Request ID for async processing (if needed)
- KB content ID: Unique ID per content item

---

## Error Handling

Following existing pattern:
- Use `AppError` for consistent error responses
- Validation in service layer
- HTTP status codes: 400 (validation), 404 (not found), 500 (server)
- Detailed error messages with codes

---

## Performance Considerations

1. **Document Processing**: Chunk large docs, process in parallel if needed
2. **Translation**: Batch requests when possible, cache translations
3. **Knowledge Base**: Build index once, update incrementally
4. **Embeddings**: Cache computed embeddings, reuse when possible

---

## Security Considerations

1. **File Upload**: Validate file types, size limits, sanitize names
2. **Content Storage**: Isolate user content, use UUIDs
3. **API Access**: Same CORS policy as existing endpoints
4. **Resource Limits**: Max file size, max KB size, rate limiting

---

This architecture ensures the three features are:
- **Tightly integrated**: Share services and utilities
- **Modular**: Can be developed and tested independently  
- **Scalable**: Clear paths for enhancement
- **Consistent**: Follow OrganAIzer patterns and conventions

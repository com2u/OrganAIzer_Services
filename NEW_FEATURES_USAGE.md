# OrganAIzer - New Features Usage Guide

This guide explains how to use the three new integrated features added to OrganAIzer:
1. Document Summarization & Analysis
2. Universal Translator
3. Knowledge Base (RAG)

## Installation

### 1. Install New Dependencies

```bash
cd backend
pip install PyPDF2==3.0.1 python-docx==1.1.0 scikit-learn==1.3.2 numpy==1.24.3
```

### 2. Start the Backend

```bash
# From the project root
.\start_backend.bat
```

The API will be available at `http://localhost:8000`

### 3. Access API Documentation

Visit `http://localhost:8000/docs` for interactive API documentation.

---

## Feature 1: Document Summarization & Analysis

Transform documents into insights with AI-powered analysis.

### Supported Formats
- PDF (.pdf)
- Word (.docx)
- Text (.txt)
- Markdown (.md)

### API Endpoints

#### 1. Upload Document
```http
POST /api/documents/upload
Content-Type: multipart/form-data

file: [document file]
```

**Response:**
```json
{
  "document_id": "uuid",
  "filename": "sample.pdf",
  "text_length": 5000,
  "metadata": {
    "uploaded_at": "2026-01-04T22:00:00",
    "file_size": 102400,
    "language": "en",
    "num_pages": 10,
    "num_chunks": 2
  }
}
```

#### 2. Summarize Document
```http
POST /api/documents/summarize
Content-Type: application/json

{
  "document_id": "uuid",
  "summary_length": "medium",
  "include_key_points": true
}
```

**Summary Lengths:**
- `short`: 2-3 sentences
- `medium`: 1-2 paragraphs
- `long`: 3-4 paragraphs with details

**Response:**
```json
{
  "document_id": "uuid",
  "summary": "This document discusses...",
  "key_points": [
    "Main finding about...",
    "Important consideration...",
    "Key recommendation..."
  ],
  "language": "en"
}
```

#### 3. Chat with Document
```http
POST /api/documents/chat
Content-Type: application/json

{
  "document_id": "uuid",
  "question": "What are the main conclusions?",
  "conversation_history": []
}
```

**Response:**
```json
{
  "document_id": "uuid",
  "question": "What are the main conclusions?",
  "answer": "The main conclusions are...",
  "relevant_chunks": ["chunk1...", "chunk2..."]
}
```

#### 4. List Documents
```http
GET /api/documents/list
```

#### 5. Get Document Info
```http
GET /api/documents/{document_id}
```

#### 6. Delete Document
```http
DELETE /api/documents/{document_id}
```

### Usage Example (Python)

```python
import requests

# 1. Upload document
with open('report.pdf', 'rb') as f:
    response = requests.post(
        'http://localhost:8000/api/documents/upload',
        files={'file': f}
    )
doc_id = response.json()['document_id']

# 2. Get summary
summary_response = requests.post(
    'http://localhost:8000/api/documents/summarize',
    json={
        'document_id': doc_id,
        'summary_length': 'medium',
        'include_key_points': True
    }
)
print(summary_response.json()['summary'])

# 3. Ask questions
chat_response = requests.post(
    'http://localhost:8000/api/documents/chat',
    json={
        'document_id': doc_id,
        'question': 'What are the key findings?'
    }
)
print(chat_response.json()['answer'])
```

### Usage Example (cURL)

```bash
# Upload document
curl -X POST http://localhost:8000/api/documents/upload \
  -F "file=@document.pdf"

# Summarize
curl -X POST http://localhost:8000/api/documents/summarize \
  -H "Content-Type: application/json" \
  -d '{"document_id":"uuid","summary_length":"medium","include_key_points":true}'
```

---

## Feature 2: Universal Translator

Translate text, audio, and files using AI-powered translation.

### Supported Languages

30+ languages including:
- English (en), Spanish (es), French (fr), German (de)
- Italian (it), Portuguese (pt), Russian (ru)
- Japanese (ja), Korean (ko), Chinese (zh)
- Arabic (ar), Hindi (hi), and more

### API Endpoints

#### 1. Translate Text
```http
POST /api/translate/text
Content-Type: application/json

{
  "text": "Hello, how are you?",
  "target_language": "es",
  "source_language": null
}
```

**Response:**
```json
{
  "translated_text": "Hola, ¿cómo estás?",
  "source_language": "en",
  "target_language": "es",
  "original_text": null
}
```

#### 2. Translate Audio
```http
POST /api/translate/audio
Content-Type: multipart/form-data

file: [audio file]
target_language: es
generate_audio: false
```

**Process:**
1. Transcribes audio (STT)
2. Detects source language
3. Translates to target language
4. Optionally generates TTS audio

**Response:**
```json
{
  "transcript": "Hello, how are you?",
  "translated_text": "Hola, ¿cómo estás?",
  "source_language": "en",
  "target_language": "es",
  "audio_url": "/api/tts/audio_file.mp3"
}
```

#### 3. Translate File
```http
POST /api/translate/file
Content-Type: multipart/form-data

file: [text file .txt or .md]
target_language: de
```

#### 4. Detect Language
```http
POST /api/translate/detect
Content-Type: application/json

{
  "text": "Bonjour le monde",
  "target_language": ""
}
```

**Response:**
```json
{
  "detected_language": "fr",
  "confidence": 0.9,
  "text_preview": "Bonjour le monde"
}
```

#### 5. Get Supported Languages
```http
GET /api/translate/languages
```

### Usage Example (Python)

```python
import requests

# Translate text
response = requests.post(
    'http://localhost:8000/api/translate/text',
    json={
        'text': 'Hello world',
        'target_language': 'fr'
    }
)
print(response.json()['translated_text'])
# Output: "Bonjour le monde"

# Translate audio
with open('audio.mp3', 'rb') as f:
    response = requests.post(
        'http://localhost:8000/api/translate/audio',
        files={'file': f},
        data={
            'target_language': 'de',
            'generate_audio': 'true'
        }
    )
result = response.json()
print(f"Original: {result['transcript']}")
print(f"Translation: {result['translated_text']}")
```

### Usage Example (JavaScript)

```javascript
// Translate text
const translateText = async (text, targetLang) => {
  const response = await fetch('http://localhost:8000/api/translate/text', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      text: text,
      target_language: targetLang
    })
  });
  const data = await response.json();
  return data.translated_text;
};

// Usage
const translation = await translateText('Good morning', 'es');
console.log(translation); // "Buenos días"
```

---

## Feature 3: Knowledge Base (RAG)

Build a persistent memory system with semantic search and chat capabilities.

### What is RAG?

RAG (Retrieval-Augmented Generation) combines:
- **Retrieval**: Finding relevant information from your knowledge base
- **Generation**: Using AI to generate answers based on retrieved context

### API Endpoints

#### 1. Add Content
```http
POST /api/kb/add
Content-Type: application/json

{
  "content": "Long text content to store...",
  "title": "Meeting Notes - Jan 2026",
  "source_type": "note",
  "source_id": null,
  "metadata": {"author": "John", "tags": ["meeting", "planning"]}
}
```

**Source Types:**
- `note`: Personal notes
- `document`: Document summaries
- `transcript`: Audio/video transcriptions
- `custom`: Custom type

**Response:**
```json
{
  "content_id": "uuid",
  "num_chunks": 3,
  "message": "Content added to knowledge base"
}
```

#### 2. Search Knowledge Base
```http
POST /api/kb/search
Content-Type: application/json

{
  "query": "What did we discuss about the project timeline?",
  "top_k": 5,
  "min_score": 0.1,
  "source_type_filter": null
}
```

**Response:**
```json
{
  "query": "What did we discuss about the project timeline?",
  "results": [
    {
      "content_id": "uuid",
      "chunk_text": "We discussed that the project timeline...",
      "score": 0.85,
      "title": "Meeting Notes - Jan 2026",
      "source_type": "note",
      "metadata": {}
    }
  ],
  "total_results": 5
}
```

#### 3. Chat with Knowledge Base
```http
POST /api/kb/chat
Content-Type: application/json

{
  "question": "What were the key decisions from last month?",
  "conversation_history": [],
  "top_k": 3
}
```

**Process:**
1. Searches KB for relevant content
2. Uses top results as context
3. Generates AI answer based on context
4. Returns answer with sources

**Response:**
```json
{
  "question": "What were the key decisions from last month?",
  "answer": "Based on your notes, the key decisions were...",
  "sources": [
    {
      "content_id": "uuid",
      "chunk_text": "Relevant context...",
      "score": 0.92,
      "title": "Strategy Meeting",
      "source_type": "note"
    }
  ]
}
```

#### 4. List All Content
```http
GET /api/kb/list
```

#### 5. Delete Content
```http
DELETE /api/kb/{content_id}
```

#### 6. Reindex Knowledge Base
```http
POST /api/kb/reindex
```

Use this to rebuild the search index after deletions or corruption.

#### 7. Get Statistics
```http
GET /api/kb/stats
```

**Response:**
```json
{
  "total_contents": 25,
  "total_chunks": 150,
  "index_size_mb": 2.5,
  "last_updated": "2026-01-04T22:00:00",
  "by_source_type": {
    "note": 15,
    "document": 8,
    "transcript": 2
  }
}
```

### Usage Example (Python)

```python
import requests

BASE_URL = 'http://localhost:8000/api/kb'

# 1. Add content
add_response = requests.post(
    f'{BASE_URL}/add',
    json={
        'content': 'Today we decided to launch the new feature in Q2...',
        'title': 'Q1 Planning Meeting',
        'source_type': 'note',
        'metadata': {'date': '2026-01-04', 'attendees': ['Alice', 'Bob']}
    }
)
print(f"Added content: {add_response.json()['content_id']}")

# 2. Search
search_response = requests.post(
    f'{BASE_URL}/search',
    json={
        'query': 'When are we launching?',
        'top_k': 3
    }
)
for result in search_response.json()['results']:
    print(f"Score: {result['score']:.2f} - {result['chunk_text'][:100]}...")

# 3. Chat with KB
chat_response = requests.post(
    f'{BASE_URL}/chat',
    json={
        'question': 'What decisions were made in Q1 planning?'
    }
)
print(chat_response.json()['answer'])

# 4. Get stats
stats = requests.get(f'{BASE_URL}/stats').json()
print(f"KB contains {stats['total_contents']} items")
```

---

## Integration Workflows

### Workflow 1: Document → Knowledge Base
```python
# 1. Upload document
doc_response = requests.post(
    'http://localhost:8000/api/documents/upload',
    files={'file': open('report.pdf', 'rb')}
)
doc_id = doc_response.json()['document_id']

# 2. Summarize document
summary_response = requests.post(
    'http://localhost:8000/api/documents/summarize',
    json={'document_id': doc_id, 'summary_length': 'long'}
)
summary = summary_response.json()['summary']

# 3. Add summary to knowledge base
kb_response = requests.post(
    'http://localhost:8000/api/kb/add',
    json={
        'content': summary,
        'title': doc_response.json()['filename'],
        'source_type': 'document',
        'source_id': doc_id
    }
)
```

### Workflow 2: Audio → Translate → Knowledge Base
```python
# 1. Translate audio
with open('meeting.mp3', 'rb') as f:
    translate_response = requests.post(
        'http://localhost:8000/api/translate/audio',
        files={'file': f},
        data={'target_language': 'en'}
    )

transcript = translate_response.json()['translated_text']

# 2. Add to knowledge base
requests.post(
    'http://localhost:8000/api/kb/add',
    json={
        'content': transcript,
        'title': 'Translated Meeting Recording',
        'source_type': 'transcript'
    }
)
```

### Workflow 3: Multi-language Knowledge Base
```python
# Store content in multiple languages
languages = ['en', 'es', 'fr', 'de']

original_text = "Important announcement: Product launch scheduled for March..."

for lang in languages:
    # Translate
    translation = requests.post(
        'http://localhost:8000/api/translate/text',
        json={'text': original_text, 'target_language': lang}
    ).json()['translated_text']
    
    # Add to KB
    requests.post(
        'http://localhost:8000/api/kb/add',
        json={
            'content': translation,
            'title': f'Product Announcement ({lang})',
            'source_type': 'note',
            'metadata': {'language': lang}
        }
    )

# Now you can search in any language!
```

---

## Tips & Best Practices

### Document Analysis
- **Use appropriate summary length**: Short for quick previews, long for detailed analysis
- **Ask specific questions**: Document chat works best with focused queries
- **Check language detection**: Verify detected language is correct for best results

### Translation
- **Audio quality matters**: Clean audio produces better transcriptions and translations
- **Verify critical translations**: AI translation is very good but verify important content
- **Use language codes**: Always use standard codes (en, es, fr, de, etc.)

### Knowledge Base
- **Add titles**: Always provide descriptive titles for better organization
- **Use metadata**: Add tags, dates, authors for better filtering
- **Regular maintenance**: Periodically review and clean old content
- **Chunking is automatic**: Large content is automatically split for optimal search
- **Search tips**: Use specific keywords and phrases for best results

---

## Troubleshooting

### Document Upload Fails
- Check file size (large files may timeout)
- Verify file format is supported
- Ensure file is not corrupted

### Translation Errors
- Verify language codes are valid
- Check audio file format for audio translation
- Ensure text is long enough for language detection

### Knowledge Base Search Returns No Results
- Try different search terms
- Lower `min_score` parameter
- Check if content was actually added (use /api/kb/list)
- Try reindexing (/api/kb/reindex)

### Performance Issues
- Large documents may take time to process
- Knowledge base search is fast but depends on index size
- Consider chunking very large content manually

---

## API Rate Limits & Costs

All features use the OpenRouter API for LLM operations:
- No additional costs beyond existing OpenRouter usage
- Translation and summarization count as LLM API calls
- Local operations (STT, TTS, embeddings) have no API costs

---

## Next Steps

1. **Install dependencies**: Run pip install for new packages
2. **Start backend**: Launch the API server
3. **Try the examples**: Use the code examples above
4. **Explore the API docs**: Visit http://localhost:8000/docs
5. **Build integrations**: Use these features in your applications

For frontend integration, see the frontend development section (coming soon).

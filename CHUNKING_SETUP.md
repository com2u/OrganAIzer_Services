# Audio Chunking & Caching Setup

## Overview

The OrganAIzer Services now includes advanced features for handling large audio files and long videos:

- ✅ **Automatic Chunking** - Files >15MB are automatically split into 5-minute chunks
- ✅ **Retry Logic** - 3 automatic retries for failed downloads and transcriptions
- ✅ **Caching** - Transcripts are cached to avoid re-processing
- ✅ **Large File Support** - Supports files up to 500MB (with chunking)

## Features

### 1. Audio Chunking (15MB+ Files)

When an audio file exceeds 15MB, it's automatically:
1. Split into 5-minute chunks using ffmpeg
2. Each chunk is transcribed separately with retry logic
3. Transcripts are merged in the correct order
4. Failed chunks are skipped (with logging) to allow partial transcription

**Benefits:**
- No more "file too large" errors
- More reliable for multi-hour videos
- Better error recovery (failed chunks don't stop entire transcription)

### 2. Caching System

Transcripts are cached locally to avoid re-processing:

**Location:** `cache/transcripts/` (created automatically)

**Cache Keys:**
- For uploaded files: SHA256 hash of file content
- For YouTube videos: Video URL

**Cache Structure:**
```json
{
  "identifier": "video_url_or_hash",
  "transcript": "The transcribed text...",
  "cached_at": "2025-01-05T23:00:00",
  "metadata": {
    "language": "en",
    "duration": 3600.5,
    "file_size": 25000000,
    "chunked": true
  }
}
```

**Benefits:**
- Instant results for repeated transcriptions
- Saves processing time and API costs
- Persists across server restarts

### 3. Retry Logic

**YouTube Downloads:** 3 retries with exponential backoff
- Retry delays: 1s, 2s, 4s
- File size validation after each attempt
- Descriptive errors if all retries fail

**Transcription Chunks:** 3 retries per chunk
- Retry delays: 1s, 2s, 4s
- Skips failed chunks (allows partial transcription)
- Logs all retry attempts

### 4. Hybrid Transcription Strategy

**Small Files (<15MB):**
- Direct transcription (STT) or OpenRouter (YouTube)
- Single API call
- Fastest processing

**Large Files (≥15MB):**
- Automatic chunking into 5-minute segments
- Uses local Whisper model (more reliable, no size limits)
- Parallel-ready architecture (future enhancement)

## How It Works

### Speech-to-Text Upload Flow

```
1. User uploads audio file
2. Check cache (by file hash) → Return if found
3. Check file size:
   - < 15MB: Standard Whisper transcription
   - ≥ 15MB: 
     a. Split audio into 5-min chunks (ffmpeg)
     b. Transcribe each chunk (with retry)
     c. Merge transcripts
     d. Clean up chunks
4. Cache result
5. Return transcript
```

### YouTube Video Flow

```
1. User provides YouTube URL
2. Check cache (by URL) → Return if found
3. Download audio with retry logic:
   - Attempt 1: Download
   - If fails → Wait 1s → Attempt 2
   - If fails → Wait 2s → Attempt 3
   - If fails → Return error
4. Validate file size (must be > 0 bytes)
5. Check file size:
   - < 15MB: OpenRouter transcription
   - ≥ 15MB: Local Whisper with chunking
6. Cache result
7. Clean up temporary files
8. Return transcript
```

## API Responses

### Success Response (STT)

```json
{
  "transcript": "The full transcribed text...",
  "language": "en",
  "duration_seconds": 3600.5
}
```

### Success Response (YouTube)

```json
{
  "url": "https://youtube.com/watch?v=...",
  "transcript": "The full transcribed text..."
}
```

### Error Response

```json
{
  "error": {
    "code": "DOWNLOAD_FAILED",
    "message": "Failed to download YouTube audio after 3 attempts: ...",
    "details": {}
  }
}
```

## Error Codes

| Code | Description | Solution |
|------|-------------|----------|
| `DOWNLOAD_FAILED` | YouTube download failed after retries | Check URL, video may be restricted |
| `EMPTY_FILE` | Downloaded file is 0 bytes | Video unavailable or network issue |
| `ALL_CHUNKS_FAILED` | All audio chunks failed to transcribe | Audio may be corrupted |
| `CHUNKED_TRANSCRIPTION_FAILED` | Chunking process failed | Check ffmpeg installation |
| `FILE_TOO_LARGE` | File exceeds 500MB limit | Split file manually |

## Configuration

### Environment Variables

No new environment variables required. Existing variables still apply:
- `OPENROUTER_API_KEY` - For YouTube transcription (small files)

### File Limits

```python
# In backend/services/stt_service.py
CHUNK_THRESHOLD_BYTES = 15 * 1024 * 1024  # 15MB

# In backend/services/youtube_service.py
MAX_DOWNLOAD_RETRIES = 3
CHUNK_THRESHOLD_BYTES = 15 * 1024 * 1024  # 15MB
```

### Chunk Duration

```python
# In backend/utils/audio.py
chunk_duration_minutes = 5  # 5-minute chunks
```

## Cache Management

### View Cache Stats

```python
from utils.cache import get_cache

cache = get_cache()
stats = cache.get_cache_stats()
# Returns: {'num_cached': 10, 'total_size_mb': 5.2, ...}
```

### Clear Cache

```python
from utils.cache import get_cache

cache = get_cache()
cache.clear_all()  # Deletes all cached transcripts
```

### Delete Specific Cache Entry

```python
from utils.cache import get_cache

cache = get_cache()
cache.delete("video_url_or_hash")
```

## Dependencies

### Required

- `ffmpeg` - For audio splitting and conversion
- `ffprobe` - For audio duration detection
- `whisper` - For local transcription
- `yt-dlp` - For YouTube downloads

### Verify Installation

```bash
# Check ffmpeg
ffmpeg -version

# Check ffprobe
ffprobe -version

# Check Python packages
pip list | grep -E "whisper|yt-dlp"
```

## Performance Tips

### For Long Videos (1-5 hours)

1. **Use caching** - Second transcription is instant
2. **Quality mode** - Use "fast" for quicker processing
3. **Monitor logs** - Check for chunk failures
4. **Disk space** - Ensure enough space for temporary files

### For Very Long Videos (5+ hours)

1. **Download separately** - Use yt-dlp to download first
2. **Upload as file** - Use STT endpoint instead
3. **Monitor progress** - Check backend logs for status
4. **Patience** - May take 10-30 minutes depending on duration

## Troubleshooting

### "All chunks failed to transcribe"

**Cause:** Audio format not compatible with Whisper
**Solution:** Try different YouTube video or quality mode

### "Downloaded file is empty"

**Cause:** YouTube blocked the download or video is restricted
**Solution:**
- Try again later
- Use different video
- Check if video requires authentication

### "Chunking process failed"

**Cause:** ffmpeg not installed or not in PATH
**Solution:**
```bash
# Windows (install ffmpeg)
choco install ffmpeg

# Verify
ffmpeg -version
```

### Chunks merging out of order

**Cause:** Should not happen (chunks are sorted by index)
**Solution:** Report bug - this is a critical issue

## Future Enhancements

- [ ] Real-time progress websockets
- [ ] Parallel chunk transcription
- [ ] Configurable chunk duration
- [ ] Automatic cache cleanup (LRU eviction)
- [ ] Progress bar in frontend
- [ ] Resume failed transcriptions

## Testing

### Test with Small File (<15MB)

1. Upload small MP3 file
2. Should use standard transcription
3. Check response time (fast)

### Test with Large File (>15MB)

1. Upload large audio file or long YouTube video
2. Check backend logs for "using chunked transcription"
3. Verify transcript quality
4. Check cache was created

### Test Caching

1. Transcribe same video twice
2. Second request should be instant
3. Response should be identical

### Test Retry Logic

1. Provide invalid YouTube URL
2. Check logs show 3 retry attempts
3. Verify error message is descriptive

## Summary

The chunking and caching system makes OrganAIzer Services production-ready for:
- ✅ Multi-hour YouTube videos
- ✅ Large audio files (up to 500MB)
- ✅ Unreliable network conditions
- ✅ Repeated transcriptions
- ✅ Cost optimization (caching reduces API calls)

All features work automatically - no configuration required!

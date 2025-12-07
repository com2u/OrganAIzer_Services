/**
 * API utility functions for communicating with the backend.
 * Handles all HTTP requests to the OrganAIzer Services API.
 */

// Get API base URL from environment variables
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

/**
 * Error structure returned by the backend API.
 * Used throughout the application to handle API errors consistently.
 */
export interface ApiError {
  code: string;
  message: string;
  details?: Record<string, any>;
}

/**
 * Request payload for generating speech from text.
 * Used when calling the POST /api/tts/generate endpoint.
 */
export interface TTSGenerateRequest {
  text_md: string;
}

/**
 * Response from the TTS generation endpoint.
 * Contains normalized text, detected language, and audio URL.
 */
export interface TTSGenerateResponse {
  text_normalized: string;
  language: string;
  audio_url: string;
}

/**
 * Generates speech from markdown-formatted text.
 * Calls the backend TTS API to convert text to audio.
 * 
 * @param textMd - Markdown-formatted text to convert to speech
 * @returns Promise resolving to the TTS response with audio URL
 * @throws Error with ApiError structure if the request fails
 */
export async function generateSpeech(textMd: string): Promise<TTSGenerateResponse> {
  const response = await fetch(`${API_BASE_URL}/api/tts/generate`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ text_md: textMd }),
  });

  const data = await response.json();

  if (!response.ok) {
    // Backend returns errors in { "error": { ... } } format
    if (data.error) {
      throw new Error(data.error.message || 'Failed to generate speech');
    }
    throw new Error('Failed to generate speech');
  }

  return data;
}

/**
 * Request payload for generating images from text.
 * Used when calling the POST /api/image-gen/generate endpoint.
 */
export interface ImageGenRequest {
  prompt: string;
  num_images?: number;
  aspect_ratio?: string;
}

/**
 * Response from the image generation endpoint.
 * Contains the prompt and array of generated image URLs.
 */
export interface ImageGenResponse {
  prompt: string;
  images: string[];
  num_images: number;
}

/**
 * Generates images from a text prompt.
 * Calls the backend image generation API using Google Vertex AI Imagen.
 * 
 * @param request - Image generation request with prompt and parameters
 * @returns Promise resolving to the image generation response with image URLs
 * @throws Error with ApiError structure if the request fails
 */
export async function generateImages(request: ImageGenRequest): Promise<ImageGenResponse> {
  const response = await fetch(`${API_BASE_URL}/api/image-gen/generate`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(request),
  });

  const data = await response.json();

  if (!response.ok) {
    // Backend returns errors in { "error": { ... } } format
    if (data.error) {
      throw new Error(data.error.message || 'Failed to generate images');
    }
    throw new Error('Failed to generate images');
  }

  return data;
}

/**
 * Request payload for nano banana (Gemini 2.5 Flash Image) generation.
 */
export interface NanoBananaRequest {
  prompt: string;
  num_images?: number;
}

/**
 * Response from the nano banana image generation endpoint.
 */
export interface NanoBananaResponse {
  success: boolean;
  model: string;
  prompt: string;
  images: Array<{
    image_id: string;
    url: string;
    dataUrl: string;
  }>;
}

/**
 * Generates images using Gemini 2.5 Flash Image (nano banana).
 * 
 * @param request - Image generation request with prompt
 * @returns Promise resolving to the nano banana response with images
 * @throws Error if the request fails
 */
export async function generateNanoBananaImages(request: NanoBananaRequest): Promise<NanoBananaResponse> {
  const response = await fetch(`${API_BASE_URL}/api/nano-banana/generate`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(request),
  });

  const data = await response.json();

  if (!response.ok) {
    if (data.error) {
      throw new Error(data.error.message || 'Failed to generate images with nano banana');
    }
    throw new Error('Failed to generate images with nano banana');
  }

  return data;
}

/**
 * Builds the full URL for downloading or playing an audio file.
 * Takes the relative audio URL from the API response and makes it absolute.
 * 
 * @param audioUrl - Relative audio URL from the API (e.g., "/api/tts/audio/{id}")
 * @returns Full URL for accessing the audio file
 */
export function getFullAudioUrl(audioUrl: string): string {
  return `${API_BASE_URL}${audioUrl}`;
}

/**
 * Response from the STT transcription endpoint.
 * Contains the transcribed text and optional metadata.
 */
export interface STTTranscribeResponse {
  transcript: string;
  language?: string;
  duration_seconds?: number;
}

/**
 * Response from the unified video transcription endpoint.
 */
export interface VideoTranscribeResponse {
  source_type: string;
  source_url?: string;
  transcript: string;
  detected_language?: string;
}

/**
 * Transcribes an audio file to text.
 * Calls the backend STT API to convert audio to text.
 * 
 * @param audioFile - Audio file to transcribe (MP3, WAV, M4A, OGG, FLAC)
 * @param language - Optional language hint (e.g., 'en', 'de') for better accuracy
 * @returns Promise resolving to the STT response with transcript
 * @throws Error with ApiError structure if the request fails
 */
export async function transcribeAudio(audioFile: File, language?: string): Promise<STTTranscribeResponse> {
  const formData = new FormData();
  formData.append('file', audioFile);
  
  // Add language hint if provided
  if (language) {
    formData.append('language', language);
  }

  const response = await fetch(`${API_BASE_URL}/api/stt/transcribe`, {
    method: 'POST',
    body: formData,
  });

  const data = await response.json();

  if (!response.ok) {
    // Backend returns errors in { "error": { ... } } format
    if (data.error) {
      throw new Error(data.error.message || 'Failed to transcribe audio');
    }
    throw new Error('Failed to transcribe audio');
  }

  return data;
}

/**
 * Transcribes a video from YouTube URL, generic video URL, or uploaded file.
 * Uses the unified video transcription endpoint.
 * 
 * @param sourceType - Type of video source: 'youtube', 'url', or 'upload'
 * @param videoUrl - Video URL (for youtube and url types)
 * @param languagePreference - Language hint for transcription
 * @param qualityMode - Quality mode: 'fast' or 'accurate'
 * @param file - Video file (for upload type)
 * @returns Promise resolving to the video transcription response
 * @throws Error if the request fails
 */
export async function transcribeVideo(
  sourceType: 'youtube' | 'url' | 'upload',
  videoUrl?: string,
  languagePreference: string = 'auto',
  qualityMode: 'fast' | 'accurate' = 'accurate',
  file?: File
): Promise<VideoTranscribeResponse> {
  const formData = new FormData();
  formData.append('source_type', sourceType);
  formData.append('language_preference', languagePreference);
  formData.append('quality_mode', qualityMode);
  
  if (videoUrl) {
    formData.append('video_url', videoUrl);
  }
  
  if (file) {
    formData.append('file', file);
  }

  const response = await fetch(`${API_BASE_URL}/api/video/transcribe`, {
    method: 'POST',
    body: formData,
  });

  const data = await response.json();

  if (!response.ok) {
    if (data.error) {
      throw new Error(data.error.message || 'Failed to transcribe video');
    }
    throw new Error('Failed to transcribe video');
  }

  return data;
}

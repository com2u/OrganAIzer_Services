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
 * Transcribes an audio file to text.
 * Calls the backend STT API to convert audio to text.
 * 
 * @param audioFile - Audio file to transcribe (MP3, WAV, M4A, OGG, FLAC)
 * @returns Promise resolving to the STT response with transcript
 * @throws Error with ApiError structure if the request fails
 */
export async function transcribeAudio(audioFile: File): Promise<STTTranscribeResponse> {
  const formData = new FormData();
  formData.append('file', audioFile);

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

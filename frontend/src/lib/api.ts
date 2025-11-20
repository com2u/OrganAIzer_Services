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
 * Builds the full URL for downloading or playing an audio file.
 * Takes the relative audio URL from the API response and makes it absolute.
 * 
 * @param audioUrl - Relative audio URL from the API (e.g., "/api/tts/audio/{id}")
 * @returns Full URL for accessing the audio file
 */
export function getFullAudioUrl(audioUrl: string): string {
  return `${API_BASE_URL}${audioUrl}`;
}

/**
 * Central API client — single source of truth for base URL and fetch helpers.
 *
 * Strategy:
 *   VITE_API_BASE_URL defaults to '' (empty = relative URLs).
 *   All paths are /api/... so the vite dev-proxy and nginx both work without config.
 *
 * Usage:  import { agentChat, sttTranscribe, ttsGenerate } from '../lib/apiClient';
 */

export const API_BASE_URL: string = import.meta.env.VITE_API_BASE_URL ?? '';
const API_KEY: string = import.meta.env.VITE_API_KEY || 'test-key-123';

function authHeaders(extra: Record<string, string> = {}): Record<string, string> {
  return { 'X-API-Key': API_KEY, ...extra };
}

// ── Executive Agent chat ─────────────────────────────────────────────────────

export interface AgentChatResponse {
  message: string;
  success: boolean;
  type?: string;
  data?: Record<string, unknown>;
  agent_state?: string;
  active_task?: unknown;
  pending_action?: unknown;
  last_action?: unknown;
}

export async function agentChat(
  message: string,
  sessionId = 'default',
  userId = 'default_user',
  calendarProvider = 'google',
  mailProvider = 'gmail',
): Promise<AgentChatResponse> {
  const res = await fetch(`${API_BASE_URL}/api/agent/chat`, {
    method: 'POST',
    headers: authHeaders({ 'Content-Type': 'application/json' }),
    body: JSON.stringify({
      message,
      session_id: sessionId,
      user_id: userId,
      calendar_provider: calendarProvider,
      mail_provider: mailProvider,
    }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error((err as any).detail ?? `Agent error ${res.status}`);
  }
  return res.json();
}

// ── STT ──────────────────────────────────────────────────────────────────────

export async function sttTranscribe(audioBlob: Blob): Promise<string> {
  const form = new FormData();
  form.append('file', audioBlob, 'recording.webm');
  const res = await fetch(`${API_BASE_URL}/api/stt/transcribe`, {
    method: 'POST',
    headers: authHeaders(),
    body: form,
  });
  if (!res.ok) throw new Error(`STT ${res.status}`);
  const data = await res.json();
  return (data.transcript ?? data.text ?? '') as string;
}

// ── TTS ──────────────────────────────────────────────────────────────────────

/**
 * Generate TTS audio.
 * Returns the absolute URL to the MP3 file, or null on failure.
 */
export async function ttsGenerate(text: string): Promise<string | null> {
  try {
    const res = await fetch(`${API_BASE_URL}/api/tts/generate`, {
      method: 'POST',
      headers: authHeaders({ 'Content-Type': 'application/json' }),
      body: JSON.stringify({ text_md: text }),
    });
    if (!res.ok) return null;
    const data = await res.json();
    const rel: string = data.audio_url ?? '';
    return rel ? `${API_BASE_URL}${rel}` : null;
  } catch {
    return null;
  }
}

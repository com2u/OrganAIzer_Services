9/**
 * Central API client — single source of truth for base URL and fetch helpers.
 *
 * Strategy:
 *   VITE_API_BASE_URL defaults to '' (empty = relative URLs).
 *   All paths are /api/... so the vite dev-proxy and nginx both work without config.
 *
 * Usage:  import { agentChat, sttTranscribe, ttsGenerate } from '../lib/apiClient';
 */

export const API_BASE_URL: string = import.meta.env.VITE_API_BASE_URL ?? '';

// SECURITY: API key MUST be set in .env (VITE_API_KEY). No fallback — an
// empty key would pass through to the backend where it would be rejected with
// 401, giving a clear error rather than silently using a guessable default.
const API_KEY: string = import.meta.env.VITE_API_KEY ?? '';

function authHeaders(extra: Record<string, string> = {}): Record<string, string> {
  return { 'X-API-Key': API_KEY, ...extra };
}

// ── Executive Agent chat ─────────────────────────────────────────────────────

/**
 * Standardized Executive Agent response envelope.
 * Every field is always present in the backend response.
 *
 * task_state canonical values:
 *   IDLE        — no active task
 *   COLLECTING  — gathering required slots
 *   CONFIRMING  — all slots ready, waiting for yes/no
 *   EXECUTING   — running provider API call
 *   COMPLETED   — action succeeded
 *   FAILED      — action failed (details in error field)
 */
export interface AgentChatResponse {
  // ── Core ────────────────────────────────────────────────────────────────
  message: string;
  success: boolean;
  /**
   * Response type from the Executive Agent.
   * Key values: calendar_confirmation, calendar_created, calendar_list,
   * email_confirmation, email_sent, email_list, provider_not_connected,
   * calendar_slot_request, email_slot_request, chat, acknowledge, error
   */
  type?: string;
  /** Structured payload (event details, email list, etc.) */
  data?: Record<string, unknown>;
  error?: string;

  // ── Standardized envelope ───────────────────────────────────────────────
  /** IntentType constant: CALENDAR_CREATE, EMAIL_READ, GENERAL_MESSAGE, etc. */
  intent: string;
  /** Canonical FSM state — use this instead of agent_state for UI decisions */
  task_state: 'IDLE' | 'COLLECTING' | 'CONFIRMING' | 'EXECUTING' | 'COMPLETED' | 'FAILED';
  /** Reserved for future structured action list */
  actions: unknown[];
  /** Suggested follow-up question/prompt to show the user */
  follow_up: string;

  // ── Action signalling ───────────────────────────────────────────────────
  /**
   * "confirmation" → show yes/no quick-reply buttons
   * "slot_request" → user must supply missing info
   */
  action_needed?: string | null;

  // ── Session state (debug / advanced use) ───────────────────────────────
  agent_state?: string;
  active_task?: unknown;
  pending_action?: unknown;
  last_action?: unknown;
}

export async function agentChat(
  message: string,
  sessionId = 'default',
  userId = 'default_user',
  // null = omit from request → backend applies its own resolution hierarchy
  // (explicit user mention → session preferred_provider → clarification question).
  // Only pass a real value when the UI has definitively locked a provider.
  calendarProvider: string | null = null,
  mailProvider: string | null = null,
): Promise<AgentChatResponse> {
  // Build payload — exclude provider fields when null so the backend knows
  // it must resolve the provider itself (EXEC_PROVIDER_DECISION rules).
  const body: Record<string, unknown> = {
    message,
    session_id: sessionId,
    user_id: userId,
  };
  if (calendarProvider) body.calendar_provider = calendarProvider;
  if (mailProvider)     body.mail_provider     = mailProvider;

  const res = await fetch(`${API_BASE_URL}/api/agent/chat`, {
    method: 'POST',
    headers: authHeaders({ 'Content-Type': 'application/json' }),
    body: JSON.stringify(body),
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

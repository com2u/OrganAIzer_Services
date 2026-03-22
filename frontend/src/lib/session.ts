/**
 * Shared session-ID utility.
 *
 * Persists the session ID in sessionStorage so that page refreshes within
 * the same browser tab reuse the same backend ConversationMemory object.
 *
 * Both ExecutiveAgent (text chat) and VoiceExecutiveAgent (voice chat)
 * import this function so that switching between the two modes does NOT
 * create a new backend session — the AI retains full context.
 *
 * sessionStorage lifetime:
 *   - Survives page refresh ✓
 *   - Cleared when the tab is closed ✓  (intentional — fresh session on new tab)
 *   - NOT shared between tabs         ✓  (each tab gets its own conversation)
 */

const SESSION_KEY = 'organAIzer-session-id';

/**
 * Return the current session ID for this tab, creating and persisting one
 * if it does not yet exist.
 */
export function getOrCreateSessionId(): string {
  const stored = sessionStorage.getItem(SESSION_KEY);
  if (stored) return stored;
  const id = `organAIzer-session-${Date.now()}`;
  sessionStorage.setItem(SESSION_KEY, id);
  return id;
}

/**
 * Explicitly start a new session by clearing the stored ID.
 * The next call to getOrCreateSessionId() will generate a fresh one.
 * Call this when the user explicitly requests "New conversation".
 */
export function clearSessionId(): void {
  sessionStorage.removeItem(SESSION_KEY);
}

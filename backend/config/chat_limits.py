"""
Shared chat / context-window limits.

Import from here instead of defining inline constants so that
executive_agent_service.py and chat_service.py always agree.

Previous state (before this file):
  ConversationMemory.MAX_HISTORY = 20   (executive_agent_service)
  ChatService        MAX_HISTORY = 10   (chat_service)          ← WRONG — caused silent context loss
"""

# Maximum number of conversation turns kept in ConversationMemory AND
# forwarded to the LLM on every request.
MAX_HISTORY: int = 20

# Approximate token budget for the conversation history block sent to
# the LLM.  Rule-of-thumb: 1 token ≈ 4 characters of UTF-8 text.
# Only the history (not the system prompt or current user message) is
# subject to this budget.  Trim from the oldest end only.
MAX_HISTORY_TOKENS: int = 3000

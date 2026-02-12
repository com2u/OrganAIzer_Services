# organAIzer Executive Agent - Complete Guide

## Overview

The **organAIzer Executive Agent** is the core intelligence layer of the organAIzer platform. It provides a conversational AI interface that unifies access to Gmail, Outlook, calendars, and multimodal AI tools with session memory and safety protocols.

## Key Features

### 🎯 Core Capabilities

1. **Email Management (Gmail & Outlook)**
   - Read and list recent emails
   - AI-powered email summarization
   - Draft intelligent replies with context awareness
   - Send emails with safety confirmations
   - Search across mailbox

2. **Calendar Management (Google & Outlook)**
   - View upcoming events
   - Create new calendar events
   - Update existing events
   - Delete events (with confirmation)
   - Natural language event parsing
   - Smart meeting time suggestions

3. **Knowledge Companion**
   - Answer questions about history, geography, and general facts
   - Session memory for contextual follow-ups
   - Concise, witty responses
   - Remembers conversation topics

4. **Multimodal Tools**
   - Text-to-Speech (TTS) generation
   - Speech-to-Text (STT) transcription
   - AI Image Generation
   - Video transcription

5. **Productivity Assistant**
   - Daily digest generation
   - Follow-up email reminders
   - Email-to-calendar event conversion
   - Action item extraction

### 🛡️ Safety Protocols

- **NEVER sends emails without explicit user approval**
- Requires confirmation for delete operations
- Always summarizes emails before suggesting replies
- Dry-run mode for previewing actions
- Second confirmation for destructive operations

### 💬 Communication Style

- **Professional** tone for email operations
- **Conversational and buddy-like** for general chat
- **Concise but witty** for knowledge queries

## API Endpoints

### Base URL
```
/api/agent
```

### Main Endpoints

#### 1. Chat with Agent
```http
POST /api/agent/chat
```

**Request Body:**
```json
{
  "message": "Show me my recent emails",
  "session_id": "user123",
  "user_id": "default_user",
  "provider": "gmail"
}
```

**Response:**
```json
{
  "message": "Here are your recent emails:\n\n1. **Project Update**\n   From: john@example.com\n   Let's discuss the progress...\n\n2. **Meeting Reminder**\n   From: calendar@google.com\n   Team sync at 2 PM...",
  "success": true,
  "type": "email",
  "data": {
    "messages": [...]
  }
}
```

#### 2. Get Session Info
```http
GET /api/agent/session/{session_id}
```

**Response:**
```json
{
  "session_id": "user123",
  "message_count": 15,
  "context": {
    "last_location": "Rome",
    "last_topic": "geography/history"
  },
  "last_activity": "2026-02-03T22:00:00"
}
```

#### 3. List Active Sessions
```http
GET /api/agent/sessions
```

#### 4. Clear Session
```http
DELETE /api/agent/session/{session_id}
```

#### 5. Get Capabilities
```http
GET /api/agent/capabilities
```

Returns detailed information about all agent capabilities, providers, and features.

## Usage Examples

### Example 1: Check Emails

**User:** "Show me my recent emails"

**Agent Response:**
```
Here are your recent emails:

1. **Q4 Sales Report**
   From: finance@company.com
   The quarterly sales figures are ready...

2. **Team Lunch Tomorrow**
   From: sarah@company.com
   Are you joining us for lunch at...

3. **Password Reset Confirmation**
   From: security@service.com
   Your password was successfully reset...
```

### Example 2: Summarize Email

**User:** "Summarize the first email"

**Agent Response:**
```
**Email Summary:**

The finance team has completed the Q4 sales report showing:
- 15% revenue growth year-over-year
- Strong performance in Europe and Asia markets
- Request for a meeting next week to discuss 2026 targets

**Action Items:**
- Review the attached report
- Prepare questions for the meeting
- Check calendar availability for next week

**Sentiment:** Positive
```

### Example 3: Calendar Management

**User:** "What's on my calendar today?"

**Agent Response:**
```
**Today's Schedule** (3 events):

⏰ 10:00 - Team Standup
   📍 Conference Room A

⏰ 14:00 - Client Presentation
   📍 Zoom Meeting

⏰ 16:30 - 1-on-1 with Manager
```

### Example 4: Knowledge Query

**User:** "Tell me about the history of Rome"

**Agent Response:**
```
Rome, the Eternal City, was founded (according to legend) in 753 BCE and became the heart of one of history's greatest empires. From republic to empire, it dominated the Mediterranean for centuries, giving us everything from aqueducts to Latin (and pizza, much later). Fun fact: Ancient Rome had better plumbing than most medieval European cities a thousand years later!
```

**User:** "When did it fall?"

**Agent Response (with context memory):**
```
The Western Roman Empire officially fell in 476 CE when the last emperor, Romulus Augustulus, was deposed. Though if you're talking about the Eastern Roman Empire (Byzantine), that party kept going until 1453! Talk about a long goodbye.
```

### Example 5: Safety Protocol in Action

**User:** "Send an email to john@example.com saying the meeting is confirmed"

**Agent Response:**
```
⚠️ **Safety Protocol:** I need more details to send an email.

Please provide:
1. Recipient email address ✓ (john@example.com)
2. Subject
3. Message content

I'll create a draft for your approval before sending.
```

### Example 6: Productivity Assistant

**User:** "Give me a daily digest"

**Agent Response:**
```
**Daily Digest** - February 3, 2026

📧 **Important Emails (3 unread):**
- ⚠️ Client deliverable deadline reminder from project-mgmt@company.com
- Team lunch invitation from sarah@company.com
- System maintenance notification from IT

📅 **Today's Events (3):**
- 10:00 AM - Team Standup
- 2:00 PM - Client Presentation (High Priority)
- 4:30 PM - 1-on-1 with Manager

✅ **Action Items:**
- ⚠️ Review client deliverable before 2 PM meeting
- Respond to lunch invitation
- Prepare questions for manager 1-on-1

You have a busy but manageable day ahead!
```

## Session Memory & Context

The Executive Agent maintains session-based memory to provide contextual conversations:

### What Gets Remembered:
- **Conversation history** (last 10 messages)
- **Mentioned topics** (e.g., "Rome" in geography discussions)
- **Email/calendar context** (currently viewed emails/events)
- **User preferences** (tone, provider choice)

### Session Management:
- Sessions persist in memory during runtime
- Each user should have a unique `session_id`
- Sessions automatically track last activity time
- Can be cleared manually via DELETE endpoint

### Context Examples:

```
User: "Tell me about Rome"
Agent: [Stores: last_location = "Rome"]

User: "What's the weather like there?"
Agent: [Uses context: "there" = Rome]

User: "When was it founded?"
Agent: [Uses context: "it" = Rome]
```

## Integration with Existing Services

The Executive Agent integrates with:

### Email Services
- `backend/api/email.py` - Email CRUD operations
- `backend/services/providers/google_provider.py` - Gmail integration
- `backend/services/providers/microsoft_provider.py` - Outlook integration

### Calendar Services
- `backend/api/calendar.py` - Calendar CRUD operations
- `backend/services/providers/google_provider.py` - Google Calendar
- `backend/services/providers/microsoft_provider.py` - Outlook Calendar

### Productivity Features
- `backend/api/assistant.py` - Daily digest, follow-ups, email-to-event

### AI Tools
- `backend/services/llm_service.py` - Language model responses
- `backend/services/tts_service.py` - Text-to-speech
- `backend/services/stt_service.py` - Speech-to-text
- `backend/services/image_gen_service.py` - Image generation

## Authentication & Providers

### Provider Options
- **Gmail/Google**: `provider="gmail"` or `provider="google"`
- **Outlook/Microsoft**: `provider="outlook"` or `provider="microsoft"`

### User ID
The `user_id` parameter identifies which user's credentials to use for OAuth access. This should match the OAuth token stored for that user.

## Best Practices

### 1. Session Management
```javascript
// Use consistent session IDs per user
const sessionId = `user_${userId}_${Date.now()}`;

// Or use persistent session IDs
const sessionId = `user_${userId}`;
```

### 2. Error Handling
```javascript
try {
  const response = await fetch('/api/agent/chat', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      message: userInput,
      session_id: sessionId,
      user_id: userId,
      provider: 'gmail'
    })
  });
  
  const data = await response.json();
  
  if (!data.success) {
    console.error('Agent error:', data.error);
    // Handle error gracefully
  }
} catch (error) {
  console.error('Request failed:', error);
}
```

### 3. Handling Action Confirmations
```javascript
// When agent requests confirmation
if (data.action_needed === 'send_confirmation') {
  const userConfirmed = await showConfirmDialog(data.message);
  
  if (userConfirmed) {
    // Send confirmation message
    await fetch('/api/agent/chat', {
      method: 'POST',
      body: JSON.stringify({
        message: 'Yes, confirm',
        session_id: sessionId
      })
    });
  }
}
```

### 4. Displaying Rich Responses
```javascript
function displayAgentResponse(response) {
  // Parse markdown formatting
  const formattedMessage = parseMarkdown(response.message);
  
  // Display the message
  messageContainer.innerHTML = formattedMessage;
  
  // Handle additional data
  if (response.data?.messages) {
    displayEmailList(response.data.messages);
  }
  
  if (response.data?.events) {
    displayCalendarEvents(response.data.events);
  }
}
```

## Example Integration Code

### Simple Chat Interface

```javascript
class ExecutiveAgentClient {
  constructor(baseUrl, userId, provider = 'gmail') {
    this.baseUrl = baseUrl;
    this.userId = userId;
    this.provider = provider;
    this.sessionId = `session_${userId}_${Date.now()}`;
  }
  
  async chat(message) {
    const response = await fetch(`${this.baseUrl}/api/agent/chat`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        message,
        session_id: this.sessionId,
        user_id: this.userId,
        provider: this.provider
      })
    });
    
    return await response.json();
  }
  
  async getSessionInfo() {
    const response = await fetch(
      `${this.baseUrl}/api/agent/session/${this.sessionId}`
    );
    return await response.json();
  }
  
  async clearSession() {
    await fetch(
      `${this.baseUrl}/api/agent/session/${this.sessionId}`,
      { method: 'DELETE' }
    );
    // Create new session
    this.sessionId = `session_${this.userId}_${Date.now()}`;
  }
}

// Usage
const agent = new ExecutiveAgentClient('http://localhost:8000', 'user123');

const response = await agent.chat('Show me my emails');
console.log(response.message);

const sessionInfo = await agent.getSessionInfo();
console.log(`Messages exchanged: ${sessionInfo.message_count}`);
```

### React Component Example

```typescript
import React, { useState } from 'react';

interface AgentMessage {
  role: 'user' | 'agent';
  content: string;
  timestamp: string;
}

export const ExecutiveAgentChat: React.FC = () => {
  const [messages, setMessages] = useState<AgentMessage[]>([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  
  const sendMessage = async () => {
    if (!input.trim()) return;
    
    // Add user message
    const userMessage: AgentMessage = {
      role: 'user',
      content: input,
      timestamp: new Date().toISOString()
    };
    setMessages(prev => [...prev, userMessage]);
    setInput('');
    setLoading(true);
    
    try {
      const response = await fetch('/api/agent/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          message: input,
          session_id: 'demo_session',
          user_id: 'demo_user',
          provider: 'gmail'
        })
      });
      
      const data = await response.json();
      
      // Add agent response
      const agentMessage: AgentMessage = {
        role: 'agent',
        content: data.message,
        timestamp: new Date().toISOString()
      };
      setMessages(prev => [...prev, agentMessage]);
      
    } catch (error) {
      console.error('Failed to send message:', error);
    } finally {
      setLoading(false);
    }
  };
  
  return (
    <div className="agent-chat">
      <div className="messages">
        {messages.map((msg, idx) => (
          <div key={idx} className={`message ${msg.role}`}>
            <div className="content">{msg.content}</div>
            <div className="timestamp">{msg.timestamp}</div>
          </div>
        ))}
      </div>
      
      <div className="input-area">
        <input
          value={input}
          onChange={e => setInput(e.target.value)}
          onKeyPress={e => e.key === 'Enter' && sendMessage()}
          placeholder="Ask me anything..."
          disabled={loading}
        />
        <button onClick={sendMessage} disabled={loading}>
          {loading ? 'Sending...' : 'Send'}
        </button>
      </div>
    </div>
  );
};
```

## Troubleshooting

### Common Issues

#### 1. "Session not found" Error
- **Cause:** Session expired or invalid session_id
- **Solution:** Create a new session or use a valid session_id

#### 2. Email/Calendar Access Errors
- **Cause:** OAuth tokens expired or not configured
- **Solution:** Re-authenticate via `/google/auth` or `/outlook/auth`

#### 3. LLM Timeout
- **Cause:** OpenRouter API slow or unavailable
- **Solution:** Check OPENROUTER_API_KEY in backend/.env

#### 4. Agent Gives Generic Responses
- **Cause:** Intent not recognized properly
- **Solution:** Be more explicit ("Show emails" instead of "emails")

## Future Enhancements

Potential improvements for the Executive Agent:

- [ ] Multi-turn email composition workflows
- [ ] Voice interface integration with STT/TTS
- [ ] Proactive notifications and reminders
- [ ] Integration with more calendar providers (iCloud, etc.)
- [ ] Advanced natural language understanding for complex queries
- [ ] Learning from user preferences over time
- [ ] Integration with task management systems
- [ ] Meeting notes and summary generation
- [ ] Smart email categorization and prioritization

## Support

For issues or questions:
- Check the API documentation at `/docs` (FastAPI Swagger UI)
- Review error logs in backend console
- Test individual services (email, calendar) separately
- Verify OAuth credentials are configured correctly

---

**Version:** 1.0.0  
**Last Updated:** February 3, 2026  
**Status:** Production Ready ✅

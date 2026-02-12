# Executive Agent - Quick Start Guide

## What is the Executive Agent?

The **organAIzer Executive Agent** is your intelligent AI companion that manages emails, calendars, and provides knowledge assistance through natural conversation.

## 🚀 Quick Start (3 Steps)

### 1. Start the Backend
```bash
cd backend
python main.py
```

### 2. Test the Agent
```bash
# In a new terminal
python test_executive_agent.py
```

### 3. Try It Out

**Get Capabilities:**
```bash
curl http://localhost:8000/api/agent/capabilities
```

**Chat with Agent:**
```bash
curl -X POST http://localhost:8000/api/agent/chat \
  -H "Content-Type: application/json" \
  -d '{
    "message": "Hello! What can you do?",
    "session_id": "demo",
    "user_id": "demo_user",
    "provider": "gmail"
  }'
```

## 📝 Common Commands

### Email Management
```json
{"message": "Show me my recent emails"}
{"message": "Summarize the first email"}
{"message": "Help me draft a reply"}
```

### Calendar Management
```json
{"message": "What's on my calendar today?"}
{"message": "Show me today's events"}
{"message": "Schedule a meeting tomorrow"}
```

### Knowledge Queries
```json
{"message": "Tell me about the history of Rome"}
{"message": "What's the capital of France?"}
{"message": "When was it founded?"}
```

### Productivity
```json
{"message": "Give me a daily digest"}
{"message": "What emails need follow-up?"}
```

## 🔧 Configuration

### Environment Variables (backend/.env)
```bash
OPENROUTER_API_KEY=your_key_here
MODEL=openai/gpt-3.5-turbo

# For email/calendar (if using OAuth)
GOOGLE_CLIENT_ID=your_google_id
GOOGLE_CLIENT_SECRET=your_google_secret
```

### Provider Options
- **Gmail/Google**: `"provider": "gmail"`
- **Outlook/Microsoft**: `"provider": "outlook"`

## 📊 API Endpoints

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/agent/chat` | POST | Chat with agent |
| `/api/agent/session/{id}` | GET | Get session info |
| `/api/agent/sessions` | GET | List all sessions |
| `/api/agent/session/{id}` | DELETE | Clear session |
| `/api/agent/capabilities` | GET | Get capabilities |

## 🎯 Example Use Cases

### Use Case 1: Email Triage
```
You: "Show me my emails"
Agent: [Lists recent emails]

You: "Summarize the first one"
Agent: [AI summary with action items]

You: "Draft a reply saying I'll review it by tomorrow"
Agent: [Creates draft for approval]
```

### Use Case 2: Meeting Scheduling
```
You: "What's on my calendar?"
Agent: [Shows today's events]

You: "Schedule a team meeting for tomorrow at 2pm"
Agent: [Creates event preview, waits for confirmation]
```

### Use Case 3: Knowledge Assistant
```
You: "Tell me about Rome"
Agent: [Historical facts about Rome]

You: "When did it fall?"
Agent: [Continues with context about Roman Empire fall]
```

## 🛡️ Safety Features

✅ **Never sends emails without explicit approval**  
✅ **Requires confirmation for deletions**  
✅ **Always summarizes before replying**  
✅ **Dry-run mode for previewing actions**

## 🐛 Troubleshooting

**Agent not responding?**
- Check backend is running: `curl http://localhost:8000/`
- Verify OPENROUTER_API_KEY in `.env`

**Email/Calendar errors?**
- Ensure OAuth is configured
- Re-authenticate via `/google/auth` or `/outlook/auth`

**Generic responses?**
- Be more specific: "Show my emails" vs "emails"
- Check session context with `/session/{id}`

## 📚 More Information

- **Full Guide:** [EXECUTIVE_AGENT_GUIDE.md](./EXECUTIVE_AGENT_GUIDE.md)
- **API Docs:** http://localhost:8000/docs (when backend running)
- **Test Suite:** `python test_executive_agent.py`

## 💡 Tips

1. **Use consistent session IDs** for contextual conversations
2. **Start simple** with greetings and basic queries
3. **Be explicit** when requesting actions (send, delete, etc.)
4. **Check capabilities** endpoint to see what's available
5. **Monitor sessions** to understand context tracking

---

**Ready to Chat?** Run `python test_executive_agent.py` and select option 4 for interactive mode! 🚀

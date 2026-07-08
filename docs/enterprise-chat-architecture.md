# Enterprise Agentic Chat Frontend — Architecture Design

## Overview

An enterprise-grade chat interface that enables staff to interact with the platform's AI agents. Built for non-technical users who need to query, summarize, extract, and collaborate with AI agents on corporate data.

## Key Requirements

| Requirement | Priority | Notes |
|------------|----------|-------|
| Multi-turn conversation with context | P0 | Users should have coherent conversations spanning multiple turns |
| File upload & document processing | P0 | Drag-and-drop PDFs, spreadsheets, text files |
| Conversation history | P0 | Users should be able to review and continue past conversations |
| Agent handoff | P1 | Seamless switching between specialized agents |
| Role-based access | P0 | Users only see data their role permits |
| Message search | P1 | Search across all conversations |
| Typing indicators | P1 | Show when agent is processing |
| Streaming responses | P0 | Real-time token streaming for better UX |
| Audio/voice input | P2 | Optional for accessibility |
| Mobile responsive | P1 | Tablet and phone support |

## Tech Stack

| Component | Choice | Rationale |
|-----------|--------|-----------|
| Framework | React + TypeScript | Existing expertise in the team (NeurOS, HALF) |
| Build tool | Vite | Fast, modern, already in use |
| UI components | Radix UI + Tailwind | Accessible, composable, unstyled |
| Chat state | Zustand | Simple, performant, TypeScript-native |
| API streaming | Server-Sent Events (SSE) | Native browser support, no extra deps |
| Routing | React Router v7 | Standard |
| Testing | Vitest + Playwright | Existing patterns |

## API Contract

### Chat Endpoint

```
POST /api/v1/chat
Content-Type: application/json

{
  "conversation_id": "uuid",      // Optional: new conversation if omitted
  "message": "What are Q3 trends?",
  "attachments": ["file-id-1"],    // Optional: file IDs from upload
  "agent_id": "auto"              // Optional: specific agent or auto-route
}

Response (SSE stream):
data: {"type": "token", "content": "Based on"}
data: {"type": "token", "content": " the Q3 data..."}
data: {"type": "done", "conversation_id": "uuid", "tokens_used": 450}
```

### File Upload

```
POST /api/v1/chat/upload
Content-Type: multipart/form-data

Response:
{
  "file_id": "uuid",
  "name": "report.pdf",
  "size": 245000,
  "type": "application/pdf",
  "status": "ready"  // or "processing"
}
```

### Conversation Management

```
GET  /api/v1/chat/conversations         → List user's conversations
GET  /api/v1/chat/conversations/:id     → Get full conversation
DELETE /api/v1/chat/conversations/:id   → Delete conversation
POST /api/v1/chat/conversations/:id/title  → Rename conversation
```

## Frontend Component Tree

```
App
├── ChatLayout
│   ├── Sidebar
│   │   ├── ConversationList
│   │   │   ├── SearchBar
│   │   │   ├── ConversationItem (active, title, preview, timestamp)
│   │   │   └── NewChatButton
│   │   └── UserMenu (settings, logout)
│   └── ChatArea
│       ├── MessageList
│       │   ├── Message (user/assistant, content, timestamp, files)
│       │   │   ├── MessageContent (markdown rendering, code blocks)
│       │   │   ├── FilePreview (inline images, PDF previews)
│       │   │   └── FeedbackButtons (thumbs up/down)
│       │   └── TypingIndicator
│       ├── InputArea
│       │   ├── TextInput (multiline, with @mention for agent switching)
│       │   ├── FileDropzone (drag-and-drop, file picker)
│       │   ├── SendButton
│       │   └── AgentSelector (current agent indicator)
│       └── ConversationHeader
│           ├── ModelSelector (T1-T4 toggle, visible to power users)
│           └── ShareButton (export conversation)
```

## State Management (Zustand)

```typescript
interface ChatState {
  conversations: Conversation[];
  activeConversationId: string | null;
  messages: Message[];
  isStreaming: boolean;
  currentAgent: string;
  attachments: FileUpload[];
  
  // Actions
  sendMessage: (content: string) => Promise<void>;
  uploadFile: (file: File) => Promise<void>;
  switchConversation: (id: string) => void;
  deleteConversation: (id: string) => void;
  clearAttachments: () => void;
}
```

## Integration Points

| Platform Component | How Chat Connects |
|-------------------|-------------------|
| **Model Router** | Chat sends messages → router classifies intent → selects model tier → streams response |
| **Data Pipeline** | File uploads → pipeline ingests → chunks → indexes → available for RAG |
| **Policy Engine** | Every chat message checked against policies before routing |
| **Audit Store** | Every chat interaction logged in WORM audit store |
| **ACP Dashboard** | Chat usage tracked in cost dashboard |

## Implementation Plan

| Phase | What | Effort |
|-------|------|--------|
| 1 | Chat API endpoints (SSE streaming, conversation CRUD) | 3-4 days |
| 2 | Basic React chat UI (MessageList, InputArea, Sidebar) | 4-5 days |
| 3 | File upload + drag-and-drop integration | 2-3 days |
| 4 | Agent routing + status indicators | 2-3 days |
| 5 | Conversation search + history management | 2-3 days |
| 6 | Mobile responsive + accessibility polish | 2-3 days |
| 7 | E2E tests with Playwright | 2-3 days |

**Total estimated effort:** 2-3 weeks for a full team, or use existing NeurOS chat frontend as a starting point.

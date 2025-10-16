# AuraLink Platform - API Documentation

## Overview

Complete API reference for all AuraLink microservices.

**Base URLs:**
- Dashboard Service: `https://api.auralink.com` (Port 8080)
- AI Core Service: `https://ai.auralink.com` (Port 8000)
- WebRTC Server: `https://rtc.auralink.com` (Port 7880)
- Communication Service: `https://comm.auralink.com` (Port 8008)

**Authentication:** Bearer JWT token in `Authorization` header

---

## Dashboard Service API

### Authentication Endpoints

#### POST /api/v1/auth/signup
Register a new user account.

**Request:**
```json
{
  "email": "user@example.com",
  "password": "SecurePass123!",
  "name": "John Doe",
  "organization_name": "Acme Corp"
}
```

**Response:** 201 Created
```json
{
  "user_id": "uuid-string",
  "email": "user@example.com",
  "name": "John Doe",
  "organization_id": "uuid-string",
  "access_token": "jwt-token",
  "refresh_token": "jwt-refresh-token",
  "expires_in": 86400
}
```

#### POST /api/v1/auth/login
Authenticate existing user.

**Request:**
```json
{
  "email": "user@example.com",
  "password": "SecurePass123!"
}
```

**Response:** 200 OK
```json
{
  "access_token": "jwt-token",
  "refresh_token": "jwt-refresh-token",
  "expires_in": 86400,
  "user": {
    "id": "uuid-string",
    "email": "user@example.com",
    "name": "John Doe"
  }
}
```

#### POST /api/v1/auth/refresh
Refresh access token using refresh token.

**Request:**
```json
{
  "refresh_token": "jwt-refresh-token"
}
```

**Response:** 200 OK
```json
{
  "access_token": "new-jwt-token",
  "expires_in": 86400
}
```

---

### Room Management

#### POST /api/v1/rooms
Create a new video call room.

**Headers:** `Authorization: Bearer <token>`

**Request:**
```json
{
  "name": "Team Standup",
  "max_participants": 10,
  "enable_recording": false,
  "enable_aic": true
}
```

**Response:** 201 Created
```json
{
  "room_id": "room-uuid",
  "name": "Team Standup",
  "livekit_room_name": "internal-room-id",
  "created_at": "2025-10-16T10:00:00Z",
  "max_participants": 10,
  "join_url": "https://auralink.com/room/room-uuid"
}
```

#### GET /api/v1/rooms
List all rooms for authenticated user.

**Response:** 200 OK
```json
{
  "rooms": [
    {
      "room_id": "room-uuid-1",
      "name": "Team Standup",
      "created_at": "2025-10-16T10:00:00Z",
      "participant_count": 3,
      "status": "active"
    }
  ],
  "total": 1
}
```

#### POST /api/v1/rooms/{room_id}/token
Generate join token for a room.

**Response:** 200 OK
```json
{
  "token": "livekit-join-token",
  "room_id": "room-uuid",
  "expires_at": "2025-10-16T12:00:00Z"
}
```

---

### File Sharing

#### POST /api/v1/files
Upload a file for sharing during calls.

**Headers:** 
- `Authorization: Bearer <token>`
- `Content-Type: multipart/form-data`

**Request:** FormData with file

**Response:** 201 Created
```json
{
  "file_id": "file-uuid",
  "filename": "presentation.pdf",
  "size": 1048576,
  "mime_type": "application/pdf",
  "upload_url": "https://storage.auralink.com/...",
  "download_url": "https://api.auralink.com/api/v1/files/file-uuid/download"
}
```

---

## AI Core Service API

### AI Agents

#### POST /api/v1/agents
Create a new AI agent.

**Request:**
```json
{
  "name": "Research Assistant",
  "type": "research",
  "model": "gpt-4",
  "system_prompt": "You are a helpful research assistant.",
  "tools": ["web_search", "document_analysis"]
}
```

**Response:** 201 Created
```json
{
  "agent_id": "agent-uuid",
  "name": "Research Assistant",
  "type": "research",
  "status": "ready",
  "created_at": "2025-10-16T10:00:00Z"
}
```

#### POST /api/v1/agents/{agent_id}/chat
Chat with an AI agent.

**Request:**
```json
{
  "message": "What are the latest developments in AI compression?",
  "conversation_id": "conv-uuid",
  "stream": false
}
```

**Response:** 200 OK
```json
{
  "message_id": "msg-uuid",
  "content": "Recent developments in AI compression include...",
  "agent_id": "agent-uuid",
  "conversation_id": "conv-uuid",
  "usage": {
    "prompt_tokens": 50,
    "completion_tokens": 200,
    "total_tokens": 250,
    "cost_usd": 0.005
  }
}
```

---

### Memory System

#### POST /api/v1/memory
Store a memory.

**Request:**
```json
{
  "content": "User prefers technical documentation with code examples",
  "type": "preference",
  "user_id": "user-uuid",
  "metadata": {
    "context": "documentation request",
    "confidence": 0.95
  }
}
```

**Response:** 201 Created
```json
{
  "memory_id": "mem-uuid",
  "content": "User prefers technical documentation with code examples",
  "embedding_id": "emb-uuid",
  "created_at": "2025-10-16T10:00:00Z"
}
```

#### POST /api/v1/memory/search
Search memories semantically.

**Request:**
```json
{
  "query": "user preferences for documentation",
  "limit": 10,
  "min_similarity": 0.7
}
```

**Response:** 200 OK
```json
{
  "results": [
    {
      "memory_id": "mem-uuid",
      "content": "User prefers technical documentation with code examples",
      "similarity": 0.95,
      "created_at": "2025-10-16T10:00:00Z"
    }
  ],
  "total": 1
}
```

---

### Speech Services

#### POST /api/v1/speech/tts
Convert text to speech.

**Request:**
```json
{
  "text": "Hello, welcome to AuraLink!",
  "voice": "alloy",
  "model": "tts-1",
  "format": "mp3"
}
```

**Response:** 200 OK
```json
{
  "audio_url": "https://storage.auralink.com/audio/uuid.mp3",
  "duration_seconds": 2.5,
  "format": "mp3",
  "cost_usd": 0.001
}
```

#### POST /api/v1/speech/stt
Convert speech to text.

**Headers:** `Content-Type: multipart/form-data`

**Request:** Audio file upload

**Response:** 200 OK
```json
{
  "text": "Hello, welcome to AuraLink!",
  "language": "en",
  "confidence": 0.98,
  "duration_seconds": 2.5,
  "words": [
    {"word": "Hello", "start": 0.0, "end": 0.5},
    {"word": "welcome", "start": 0.6, "end": 1.0}
  ]
}
```

---

### Translation

#### POST /api/v1/translation/translate
Translate text between languages.

**Request:**
```json
{
  "text": "Hello, how are you?",
  "source_language": "en",
  "target_language": "es"
}
```

**Response:** 200 OK
```json
{
  "translated_text": "Hola, ¿cómo estás?",
  "source_language": "en",
  "target_language": "es",
  "confidence": 0.99
}
```

---

## WebRTC Server API (LiveKit)

### Room Tokens

Tokens are generated via Dashboard API (`POST /api/v1/rooms/{room_id}/token`).

### WebRTC Connection

**Client SDK Usage:**
```javascript
import { Room } from 'livekit-client';

const room = new Room({
  adaptiveStream: true,
  dynacast: true,
});

await room.connect('wss://rtc.auralink.com', token, {
  autoSubscribe: true,
});

// AIC compression automatically enabled if configured
```

---

## Error Responses

All APIs use consistent error format:

**400 Bad Request:**
```json
{
  "error": {
    "code": "INVALID_INPUT",
    "message": "Email is required",
    "field": "email"
  }
}
```

**401 Unauthorized:**
```json
{
  "error": {
    "code": "UNAUTHORIZED",
    "message": "Invalid or expired token"
  }
}
```

**403 Forbidden:**
```json
{
  "error": {
    "code": "FORBIDDEN",
    "message": "Insufficient permissions"
  }
}
```

**404 Not Found:**
```json
{
  "error": {
    "code": "NOT_FOUND",
    "message": "Room not found"
  }
}
```

**429 Too Many Requests:**
```json
{
  "error": {
    "code": "RATE_LIMIT_EXCEEDED",
    "message": "Rate limit exceeded. Try again in 60 seconds",
    "retry_after": 60
  }
}
```

**500 Internal Server Error:**
```json
{
  "error": {
    "code": "INTERNAL_ERROR",
    "message": "An unexpected error occurred"
  }
}
```

---

## Rate Limits

**Dashboard Service:**
- Authentication: 5 requests/minute per IP
- API calls: 100 requests/minute per user
- File uploads: 10 requests/minute per user

**AI Core Service:**
- AI requests: 20 requests/minute per user
- Translation: 50 requests/minute per user
- Memory operations: 100 requests/minute per user

**Headers:**
```
X-RateLimit-Limit: 100
X-RateLimit-Remaining: 95
X-RateLimit-Reset: 1697456400
```

---

## Webhooks

Configure webhooks in Dashboard settings to receive events.

**Events:**
- `room.created`
- `room.ended`
- `participant.joined`
- `participant.left`
- `recording.completed`
- `file.uploaded`

**Webhook Payload:**
```json
{
  "event": "participant.joined",
  "timestamp": "2025-10-16T10:00:00Z",
  "data": {
    "room_id": "room-uuid",
    "participant_id": "participant-uuid",
    "participant_name": "John Doe"
  }
}
```

---

**Version:** 1.0  
**Last Updated:** 2025-10-16  
**Support:** api-support@auralink.com

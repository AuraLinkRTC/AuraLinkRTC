# AuraLink Communication Service - API Documentation

**Version:** 1.0.0  
**Base URL:** `http://localhost:8008` (Development)  
**Protocol:** HTTP/HTTPS  
**Authentication:** JWT Bearer Token (Internal APIs)

---

## Table of Contents

1. [Overview](#overview)
2. [Authentication](#authentication)
3. [Internal APIs](#internal-apis)
   - [Matrix Integration](#matrix-integration)
   - [Mesh Network](#mesh-network)
   - [Presence Management](#presence-management)
4. [Matrix Standard APIs](#matrix-standard-apis)
5. [Error Handling](#error-handling)
6. [Rate Limiting](#rate-limiting)
7. [Webhooks](#webhooks)

---

## Overview

The Communication Service provides internal APIs for AuraID-to-Matrix user management, mesh network coordination, and presence tracking. It integrates with Matrix Synapse for federated communication.

### Service Endpoints

| Service | Port | Purpose |
|---------|------|---------|
| Matrix HTTP | 8008 | Client and Federation API |
| Matrix Federation | 8448 | Server-to-server communication |
| Prometheus Metrics | 9000 | Metrics export |

---

## Authentication

### Internal API Authentication

Internal APIs use JWT tokens from the Dashboard Service.

**Header:**
```
Authorization: Bearer <JWT_TOKEN>
```

**Token Payload:**
```json
{
  "sub": "user_id",
  "aud": "auralink-communication-service",
  "iat": 1704067200,
  "exp": 1704153600
}
```

### Matrix API Authentication

Matrix APIs use access tokens obtained during user registration.

**Header:**
```
Authorization: Bearer <MATRIX_ACCESS_TOKEN>
```

---

## Internal APIs

### Matrix Integration

#### POST /internal/matrix/register

Register a Matrix user for an AuraID.

**Request:**
```json
{
  "aura_id": "@alice.aura",
  "user_id": "usr_abc123",
  "username": "alice",
  "password": "optional_password",
  "display_name": "Alice Smith"
}
```

**Response:** `201 Created`
```json
{
  "matrix_user_id": "@alice_aura:auralink.network",
  "aura_id": "@alice.aura",
  "homeserver_url": "https://auralink.network",
  "access_token": "syt_..."
}
```

**Errors:**
- `400` - Invalid request body
- `409` - Matrix user already exists
- `500` - Registration failed

---

#### GET /internal/matrix/resolve/{aura_id}

Resolve AuraID to Matrix user information.

**Parameters:**
- `aura_id` (path) - The AuraID to resolve (e.g., `@alice.aura`)

**Response:** `200 OK`
```json
{
  "aura_id": "@alice.aura",
  "matrix_user_id": "@alice_aura:auralink.network",
  "display_name": "Alice Smith",
  "avatar_url": "mxc://auralink.network/abc123",
  "homeserver": "auralink.network"
}
```

**Errors:**
- `404` - Matrix user not found
- `500` - Resolution failed

---

### Mesh Network

#### POST /internal/mesh/register_node

Register a device as a mesh network node.

**Request:**
```json
{
  "aura_id": "@alice.aura",
  "device_id": "device_mobile_001",
  "device_type": "mobile",
  "capabilities": {
    "supports_video": true,
    "supports_audio": true,
    "supports_relay": false,
    "max_bandwidth_mbps": 10
  },
  "location": {
    "latitude": 37.7749,
    "longitude": -122.4194
  }
}
```

**Response:** `201 Created`
```json
{
  "node_id": "node_xyz789",
  "aura_id": "@alice.aura",
  "device_id": "device_mobile_001",
  "status": "active",
  "trust_score": 50.0,
  "capabilities": {
    "supports_video": true,
    "supports_audio": true,
    "supports_relay": false,
    "max_bandwidth_mbps": 10
  }
}
```

**Errors:**
- `400` - Invalid device type or capabilities
- `409` - Device already registered
- `500` - Registration failed

---

#### GET /internal/mesh/nodes/{aura_id}

Get all mesh nodes for an AuraID.

**Parameters:**
- `aura_id` (path) - The AuraID to query

**Response:** `200 OK`
```json
{
  "aura_id": "@alice.aura",
  "nodes": [
    {
      "node_id": "node_xyz789",
      "device_id": "device_mobile_001",
      "device_type": "mobile",
      "is_online": true,
      "trust_score": 75.0,
      "last_seen": "2025-01-15T10:30:00Z"
    }
  ],
  "count": 1
}
```

---

#### POST /internal/mesh/nodes/{node_id}/heartbeat

Send heartbeat to keep node alive.

**Parameters:**
- `node_id` (path) - The node ID

**Request:**
```json
{
  "status": "online",
  "current_load": 0.3,
  "available_bandwidth_mbps": 8
}
```

**Response:** `200 OK`
```json
{
  "node_id": "node_xyz789",
  "acknowledged": true,
  "timestamp": "2025-01-15T10:35:00Z"
}
```

---

### Presence Management

#### POST /internal/presence/update

Update user presence status.

**Request:**
```json
{
  "aura_id": "@alice.aura",
  "status": "online",
  "status_message": "Available for calls",
  "device_id": "device_mobile_001"
}
```

**Valid Statuses:** `online`, `offline`, `away`, `busy`, `dnd`

**Response:** `200 OK`
```json
{
  "aura_id": "@alice.aura",
  "status": "online",
  "updated": true,
  "timestamp": "2025-01-15T10:40:00Z"
}
```

**Errors:**
- `400` - Invalid status value
- `404` - AuraID not found
- `500` - Update failed

---

#### GET /internal/presence/{aura_id}

Get current presence status for an AuraID.

**Parameters:**
- `aura_id` (path) - The AuraID to query

**Response:** `200 OK`
```json
{
  "aura_id": "@alice.aura",
  "status": "online",
  "last_seen": "2025-01-15T10:40:00Z",
  "is_online": true
}
```

---

#### GET /internal/presence/bulk

Get presence for multiple AuraIDs.

**Query Parameters:**
- `aura_ids` (required) - Comma-separated list of AuraIDs

**Example:**
```
GET /internal/presence/bulk?aura_ids=@alice.aura,@bob.aura,@charlie.aura
```

**Response:** `200 OK`
```json
{
  "presence": [
    {
      "aura_id": "@alice.aura",
      "status": "online",
      "is_online": true
    },
    {
      "aura_id": "@bob.aura",
      "status": "away",
      "is_online": true
    },
    {
      "aura_id": "@charlie.aura",
      "status": "offline",
      "is_online": false
    }
  ],
  "count": 3
}
```

---

## Matrix Standard APIs

The Communication Service exposes standard Matrix Client-Server and Server-Server APIs on port 8008.

### Key Matrix Endpoints

#### GET /_matrix/client/versions

Get supported Matrix specification versions.

**Response:**
```json
{
  "versions": ["r0.6.1", "v1.1"]
}
```

---

#### POST /_matrix/client/r0/login

User login (for testing purposes - production uses SSO).

**Request:**
```json
{
  "type": "m.login.password",
  "identifier": {
    "type": "m.id.user",
    "user": "@alice_aura:auralink.network"
  },
  "password": "secret_password"
}
```

**Response:**
```json
{
  "user_id": "@alice_aura:auralink.network",
  "access_token": "syt_...",
  "device_id": "DEVICEID",
  "well_known": {
    "m.homeserver": {
      "base_url": "https://auralink.network"
    }
  }
}
```

---

#### GET /_matrix/client/r0/sync

Sync Matrix events (long-polling).

**Headers:**
```
Authorization: Bearer <access_token>
```

**Query Parameters:**
- `since` - Sync from this point
- `timeout` - Long-poll timeout in milliseconds

**Response:**
```json
{
  "next_batch": "s123_456_789",
  "rooms": {
    "join": {
      "!roomid:auralink.network": {
        "timeline": {
          "events": [],
          "limited": false
        }
      }
    }
  }
}
```

---

#### POST /_matrix/client/r0/rooms/{roomId}/send/{eventType}/{txnId}

Send a room event (e.g., message or call invite).

**Example - Send AuraLink Call Invite:**
```
POST /_matrix/client/r0/rooms/!room123:auralink.network/send/m.auralink.call.invite/txn1
```

**Request Body:**
```json
{
  "caller_aura_id": "@alice.aura",
  "caller_app": "telemedicine-app",
  "call_id": "call_abc123",
  "offer": {
    "type": "webrtc",
    "sdp": "v=0\r\no=- 1234..."
  },
  "expires": 30
}
```

**Response:**
```json
{
  "event_id": "$event123:auralink.network"
}
```

---

## Error Handling

### Standard Error Response

```json
{
  "error": "Error description",
  "error_code": "ERROR_CODE",
  "status_code": 400
}
```

### Common Error Codes

| Code | HTTP Status | Description |
|------|-------------|-------------|
| `INVALID_REQUEST` | 400 | Malformed request body |
| `UNAUTHORIZED` | 401 | Missing or invalid authentication |
| `FORBIDDEN` | 403 | Insufficient permissions |
| `NOT_FOUND` | 404 | Resource not found |
| `CONFLICT` | 409 | Resource already exists |
| `RATE_LIMITED` | 429 | Too many requests |
| `INTERNAL_ERROR` | 500 | Server error |
| `SERVICE_UNAVAILABLE` | 503 | Service temporarily unavailable |

---

## Rate Limiting

### Rate Limit Headers

Responses include rate limit information:

```
X-RateLimit-Limit: 100
X-RateLimit-Remaining: 95
X-RateLimit-Reset: 1704067200
```

### Limits

| Endpoint Category | Limit |
|------------------|-------|
| Internal APIs | 1000 req/min per service |
| Matrix Client API | 100 req/min per user |
| Matrix Federation | 100 req/min per server |

When rate limited, response status is `429 Too Many Requests`.

---

## Webhooks

### Call Event Webhooks (Phase 3)

Communication Service can send webhooks to registered URLs when call events occur.

**Webhook Registration:**
```
POST /internal/webhooks/register
```

**Webhook Payload (Call Invite):**
```json
{
  "event_type": "call.invite",
  "timestamp": "2025-01-15T10:45:00Z",
  "data": {
    "call_id": "call_abc123",
    "caller_aura_id": "@alice.aura",
    "callee_aura_id": "@bob.aura",
    "caller_app": "telemedicine-app",
    "callee_app": "business-comm-app"
  }
}
```

**Webhook Signature:**

Webhooks are signed with HMAC-SHA256:

```
X-Auralink-Signature: sha256=<signature>
```

Verify signature:
```python
import hmac
import hashlib

signature = hmac.new(
    webhook_secret.encode(),
    payload.encode(),
    hashlib.sha256
).hexdigest()
```

---

## API Testing

### Health Check

```bash
curl http://localhost:8008/health
```

**Response:**
```json
{
  "status": "healthy",
  "service": "communication-service"
}
```

### Matrix User Registration Example

```bash
curl -X POST http://localhost:8008/internal/matrix/register \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <JWT_TOKEN>" \
  -d '{
    "aura_id": "@alice.aura",
    "user_id": "usr_abc123",
    "username": "alice",
    "display_name": "Alice Smith"
  }'
```

### Presence Update Example

```bash
curl -X POST http://localhost:8008/internal/presence/update \
  -H "Content-Type: application/json" \
  -d '{
    "aura_id": "@alice.aura",
    "status": "online",
    "status_message": "Available for calls"
  }'
```

---

## SDK Integration (Future)

AuraLink will provide official SDKs for popular languages:

- **JavaScript/TypeScript:** `@auralink/communication-sdk`
- **Python:** `auralink-communication`
- **Go:** `github.com/auralink/communication-go`
- **Swift:** `AuraLinkCommunication`
- **Kotlin:** `com.auralink:communication`

**Example (JavaScript):**
```javascript
import { CommunicationClient } from '@auralink/communication-sdk';

const client = new CommunicationClient({
  baseUrl: 'https://comm.auralink.network',
  apiKey: 'your_api_key'
});

// Register Matrix user
const matrixUser = await client.registerMatrixUser({
  auraId: '@alice.aura',
  userId: 'usr_abc123',
  username: 'alice'
});

// Update presence
await client.updatePresence({
  auraId: '@alice.aura',
  status: 'online'
});
```

---

## Support

For API questions and support:
- **Documentation:** https://docs.auralink.network
- **GitHub Issues:** https://github.com/auralink/auralink/issues
- **Discord:** https://discord.gg/auralink

---

**Version:** 1.0.0  
**Last Updated:** 2025-01-15

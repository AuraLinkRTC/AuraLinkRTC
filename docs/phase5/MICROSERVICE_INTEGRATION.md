# 🔗 Microservice Integration Guide - Phase 5

**Integrating AI Core with WebRTC, Dashboard, and Ingress/Egress Services**

---

## 📋 Overview

This guide demonstrates how to integrate Phase 5 AI capabilities (MCP, LangGraph agents, CrewAI teams) across AuraLinkRTC's microservice architecture.

### Microservice Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    AuraLinkRTC Platform                      │
│                  Microservice Integration                    │
└─────────────────────────────────────────────────────────────┘

┌──────────────────┐         ┌──────────────────┐
│  WebRTC Server   │◀───────▶│  AI Core         │
│  (Go/LiveKit)    │  gRPC   │  (Python/FastAPI)│
│  Port: 7880      │         │  Port: 8001      │
└────────┬─────────┘         └────────┬─────────┘
         │                             │
         │    ┌──────────────────┐    │
         └───▶│  Dashboard       │◀───┘
              │  Service (Go)    │
              │  Port: 8080      │
              └────────┬─────────┘
                       │
              ┌────────▼─────────┐
              │  Ingress/Egress  │
              │  (Go/Java)       │
              │  SIP/PSTN        │
              └──────────────────┘
```

---

## 🚀 Integration Examples

### 1. WebRTC Server → AI Core Integration

The WebRTC Server communicates with AI Core for real-time AI features during calls.

#### Use Cases
- **AI Agent Auto-Join**: Agent joins video call automatically
- **Real-Time Transcription**: Live STT during calls
- **AI Moderation**: Content filtering in real-time
- **Smart Routing**: AI-powered call routing decisions

#### Implementation

**Go Client in WebRTC Server** (`auralink-webrtc-server/pkg/ai/client.go`):

```go
package ai

import (
    "context"
    "encoding/json"
    "fmt"
    "net/http"
    "time"
)

// AIClient handles communication with AI Core
type AIClient struct {
    BaseURL    string
    HTTPClient *http.Client
    APIKey     string
}

// NewAIClient creates a new AI Core client
func NewAIClient(baseURL, apiKey string) *AIClient {
    return &AIClient{
        BaseURL: baseURL,
        APIKey:  apiKey,
        HTTPClient: &http.Client{
            Timeout: 30 * time.Second,
        },
    }
}

// TriggerAgentJoin triggers an AI agent to join a room
func (c *AIClient) TriggerAgentJoin(ctx context.Context, agentID, roomID string) error {
    url := fmt.Sprintf("%s/api/v1/agents/%s/join-room", c.BaseURL, agentID)
    
    payload := map[string]interface{}{
        "room_id": roomID,
        "auto_speak": true,
        "enable_transcription": true,
    }
    
    payloadBytes, _ := json.Marshal(payload)
    
    req, err := http.NewRequestWithContext(ctx, "POST", url, bytes.NewBuffer(payloadBytes))
    if err != nil {
        return err
    }
    
    req.Header.Set("Authorization", "Bearer "+c.APIKey)
    req.Header.Set("Content-Type", "application/json")
    
    resp, err := c.HTTPClient.Do(req)
    if err != nil {
        return err
    }
    defer resp.Body.Close()
    
    if resp.StatusCode != http.StatusOK {
        return fmt.Errorf("AI Core returned status %d", resp.StatusCode)
    }
    
    return nil
}

// TranscribeAudioChunk sends audio for real-time transcription
func (c *AIClient) TranscribeAudioChunk(ctx context.Context, audioData []byte, callID string) (string, error) {
    url := fmt.Sprintf("%s/api/v1/speech/stt/stream", c.BaseURL)
    
    // Implementation for streaming transcription
    // Returns transcribed text
    
    return "Transcribed text...", nil
}

// QueryMCP queries an MCP server through AI Core
func (c *AIClient) QueryMCP(ctx context.Context, serverType, query string, connectionID string) (map[string]interface{}, error) {
    url := fmt.Sprintf("%s/api/v1/mcp/%s/query", c.BaseURL, serverType)
    
    payload := map[string]interface{}{
        "connection_id": connectionID,
        "query": query,
    }
    
    payloadBytes, _ := json.Marshal(payload)
    
    req, err := http.NewRequestWithContext(ctx, "POST", url, bytes.NewBuffer(payloadBytes))
    if err != nil {
        return nil, err
    }
    
    req.Header.Set("Authorization", "Bearer "+c.APIKey)
    req.Header.Set("Content-Type", "application/json")
    
    resp, err := c.HTTPClient.Do(req)
    if err != nil {
        return nil, err
    }
    defer resp.Body.Close()
    
    var result map[string]interface{}
    if err := json.NewDecoder(resp.Body).Decode(&result); err != nil {
        return nil, err
    }
    
    return result, nil
}
```

**Usage in WebRTC Server**:

```go
// In room creation handler
func (s *Server) CreateRoom(ctx context.Context, req *livekit.CreateRoomRequest) (*livekit.Room, error) {
    room, err := s.roomService.CreateRoom(ctx, req)
    if err != nil {
        return nil, err
    }
    
    // Check if AI agent should auto-join
    if req.Metadata != nil && req.Metadata["ai_agent_enabled"] == "true" {
        agentID := req.Metadata["agent_id"]
        
        // Trigger agent to join via AI Core
        go func() {
            err := s.aiClient.TriggerAgentJoin(context.Background(), agentID, room.Name)
            if err != nil {
                log.Errorf("Failed to trigger agent join: %v", err)
            }
        }()
    }
    
    return room, nil
}
```

---

### 2. Dashboard Service → AI Core Integration

Dashboard provides UI/API for managing AI agents, MCP connections, and workflows.

#### Use Cases
- **Agent Management**: Create, configure, delete AI agents
- **MCP Connection Setup**: Connect users to MCP servers
- **Team Configuration**: Set up CrewAI teams
- **Analytics Dashboard**: View AI usage metrics

#### Implementation

**Go Client in Dashboard** (`auralink-dashboard-service/internal/ai/client.go`):

```go
package ai

import (
    "bytes"
    "context"
    "encoding/json"
    "fmt"
    "net/http"
)

type AIService struct {
    baseURL    string
    httpClient *http.Client
}

func NewAIService(baseURL string) *AIService {
    return &AIService{
        baseURL:    baseURL,
        httpClient: &http.Client{},
    }
}

// CreateAgent creates a new AI agent
func (s *AIService) CreateAgent(ctx context.Context, userToken string, req AgentCreateRequest) (*Agent, error) {
    url := fmt.Sprintf("%s/api/v1/agents", s.baseURL)
    
    payload, _ := json.Marshal(req)
    httpReq, _ := http.NewRequestWithContext(ctx, "POST", url, bytes.NewBuffer(payload))
    httpReq.Header.Set("Authorization", "Bearer "+userToken)
    httpReq.Header.Set("Content-Type", "application/json")
    
    resp, err := s.httpClient.Do(httpReq)
    if err != nil {
        return nil, err
    }
    defer resp.Body.Close()
    
    var agent Agent
    if err := json.NewDecoder(resp.Body).Decode(&agent); err != nil {
        return nil, err
    }
    
    return &agent, nil
}

// ConnectMCPServer connects user to an MCP server
func (s *AIService) ConnectMCPServer(ctx context.Context, userToken, serverType string, credentials map[string]string) (*MCPConnection, error) {
    url := fmt.Sprintf("%s/api/v1/mcp/connect", s.baseURL)
    
    payload := map[string]interface{}{
        "server_type": serverType,
        "credentials": credentials,
    }
    
    payloadBytes, _ := json.Marshal(payload)
    httpReq, _ := http.NewRequestWithContext(ctx, "POST", url, bytes.NewBuffer(payloadBytes))
    httpReq.Header.Set("Authorization", "Bearer "+userToken)
    httpReq.Header.Set("Content-Type", "application/json")
    
    resp, err := s.httpClient.Do(httpReq)
    if err != nil {
        return nil, err
    }
    defer resp.Body.Close()
    
    var connection MCPConnection
    if err := json.NewDecoder(resp.Body).Decode(&connection); err != nil {
        return nil, err
    }
    
    return &connection, nil
}

// GetAIAnalytics retrieves AI usage analytics
func (s *AIService) GetAIAnalytics(ctx context.Context, userToken string) (*Analytics, error) {
    url := fmt.Sprintf("%s/api/v1/analytics/ai", s.baseURL)
    
    httpReq, _ := http.NewRequestWithContext(ctx, "GET", url, nil)
    httpReq.Header.Set("Authorization", "Bearer "+userToken)
    
    resp, err := s.httpClient.Do(httpReq)
    if err != nil {
        return nil, err
    }
    defer resp.Body.Close()
    
    var analytics Analytics
    if err := json.NewDecoder(resp.Body).Decode(&analytics); err != nil {
        return nil, err
    }
    
    return &analytics, nil
}
```

**Dashboard API Endpoints** (`auralink-dashboard-service/internal/api/ai.go`):

```go
package api

import (
    "net/http"
    "github.com/gin-gonic/gin"
)

// AgentHandler handles AI agent operations
type AgentHandler struct {
    aiService *ai.AIService
}

// CreateAgent godoc
// @Summary Create AI agent
// @Description Create a new AI agent with specified configuration
// @Tags agents
// @Accept json
// @Produce json
// @Param request body AgentCreateRequest true "Agent configuration"
// @Success 200 {object} Agent
// @Router /api/v1/dashboard/agents [post]
func (h *AgentHandler) CreateAgent(c *gin.Context) {
    var req AgentCreateRequest
    if err := c.ShouldBindJSON(&req); err != nil {
        c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
        return
    }
    
    userToken := c.GetHeader("Authorization")
    
    agent, err := h.aiService.CreateAgent(c.Request.Context(), userToken, req)
    if err != nil {
        c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
        return
    }
    
    c.JSON(http.StatusOK, agent)
}

// ConnectMCP godoc
// @Summary Connect to MCP server
// @Description Connect user to an MCP server (DeepWiki, Memory, etc.)
// @Tags mcp
// @Accept json
// @Produce json
// @Param request body MCPConnectRequest true "Connection details"
// @Success 200 {object} MCPConnection
// @Router /api/v1/dashboard/mcp/connect [post]
func (h *AgentHandler) ConnectMCP(c *gin.Context) {
    var req MCPConnectRequest
    if err := c.ShouldBindJSON(&req); err != nil {
        c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
        return
    }
    
    userToken := c.GetHeader("Authorization")
    
    connection, err := h.aiService.ConnectMCPServer(
        c.Request.Context(),
        userToken,
        req.ServerType,
        req.Credentials,
    )
    if err != nil {
        c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
        return
    }
    
    c.JSON(http.StatusOK, connection)
}
```

---

### 3. Ingress/Egress → AI Core Integration

Ingress/Egress service handles external media (SIP, PSTN) with AI processing.

#### Use Cases
- **AI on Phone Calls**: Transcription and AI responses on PSTN
- **Smart IVR**: AI-powered interactive voice response
- **Call Analytics**: Analyze external call quality
- **Translation**: Real-time translation on SIP calls

#### Implementation

**Java Client for Ingress/Egress** (`IngressEgress/src/main/java/ai/AIClient.java`):

```java
package com.auralink.ingress.ai;

import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.net.URI;
import java.time.Duration;
import com.google.gson.Gson;

public class AIClient {
    private final String baseURL;
    private final HttpClient httpClient;
    private final String apiKey;
    private final Gson gson;
    
    public AIClient(String baseURL, String apiKey) {
        this.baseURL = baseURL;
        this.apiKey = apiKey;
        this.httpClient = HttpClient.newBuilder()
            .connectTimeout(Duration.ofSeconds(30))
            .build();
        this.gson = new Gson();
    }
    
    // Transcribe audio from SIP call
    public TranscriptionResult transcribeAudio(byte[] audioData, String callId) 
            throws Exception {
        String url = baseURL + "/api/v1/speech/stt";
        
        // Create multipart request with audio data
        HttpRequest request = HttpRequest.newBuilder()
            .uri(URI.create(url))
            .header("Authorization", "Bearer " + apiKey)
            .header("Content-Type", "application/json")
            .POST(HttpRequest.BodyPublishers.ofByteArray(audioData))
            .build();
        
        HttpResponse<String> response = httpClient.send(
            request, 
            HttpResponse.BodyHandlers.ofString()
        );
        
        return gson.fromJson(response.body(), TranscriptionResult.class);
    }
    
    // Generate AI response via agent
    public String generateAIResponse(String agentId, String userMessage, 
                                     String callId) throws Exception {
        String url = String.format("%s/api/v1/agents/%s/chat", baseURL, agentId);
        
        ChatRequest chatReq = new ChatRequest(userMessage, callId);
        String payload = gson.toJson(chatReq);
        
        HttpRequest request = HttpRequest.newBuilder()
            .uri(URI.create(url))
            .header("Authorization", "Bearer " + apiKey)
            .header("Content-Type", "application/json")
            .POST(HttpRequest.BodyPublishers.ofString(payload))
            .build();
        
        HttpResponse<String> response = httpClient.send(
            request,
            HttpResponse.BodyHandlers.ofString()
        );
        
        ChatResponse chatResp = gson.fromJson(response.body(), ChatResponse.class);
        return chatResp.getMessage();
    }
    
    // Convert text to speech for SIP response
    public byte[] textToSpeech(String text, String voiceId) throws Exception {
        String url = baseURL + "/api/v1/speech/tts";
        
        TTSRequest ttsReq = new TTSRequest(text, voiceId);
        String payload = gson.toJson(ttsReq);
        
        HttpRequest request = HttpRequest.newBuilder()
            .uri(URI.create(url))
            .header("Authorization", "Bearer " + apiKey)
            .header("Content-Type", "application/json")
            .POST(HttpRequest.BodyPublishers.ofString(payload))
            .build();
        
        HttpResponse<byte[]> response = httpClient.send(
            request,
            HttpResponse.BodyHandlers.ofByteArray()
        );
        
        return response.body();
    }
}
```

---

## 🔄 Event-Driven Integration

### Message Queue Architecture

For asynchronous communication between microservices:

```
┌──────────────┐         ┌──────────────┐
│  WebRTC      │────────▶│   Redis      │
│  Server      │  Pub    │   PubSub     │
└──────────────┘         └──────┬───────┘
                                │
                                │ Sub
                         ┌──────▼───────┐
                         │   AI Core    │
                         └──────────────┘
```

**Redis PubSub Events**:

```python
# In AI Core - Subscribe to events
import redis.asyncio as redis

async def listen_to_room_events():
    r = await redis.from_url("redis://localhost:6379")
    pubsub = r.pubsub()
    
    await pubsub.subscribe(
        "room:created",
        "room:participant_joined",
        "room:ended"
    )
    
    async for message in pubsub.listen():
        if message['type'] == 'message':
            channel = message['channel']
            data = json.loads(message['data'])
            
            if channel == 'room:created':
                await handle_room_created(data)
            elif channel == 'room:participant_joined':
                await handle_participant_joined(data)
            elif channel == 'room:ended':
                await handle_room_ended(data)

async def handle_room_created(data):
    room_id = data['room_id']
    # Check if AI agent should auto-join
    # Trigger agent workflows
    pass
```

---

## 📊 Monitoring Integration

### Centralized Metrics

All microservices should export metrics to Prometheus:

```yaml
# prometheus.yml
scrape_configs:
  - job_name: 'auralink-webrtc'
    static_configs:
      - targets: ['webrtc-server:7880']
  
  - job_name: 'auralink-ai-core'
    static_configs:
      - targets: ['ai-core:8001']
  
  - job_name: 'auralink-dashboard'
    static_configs:
      - targets: ['dashboard:8080']
  
  - job_name: 'auralink-ingress'
    static_configs:
      - targets: ['ingress:8082']
```

### Distributed Tracing

Use Jaeger for tracing requests across microservices:

```python
# In AI Core
from opentelemetry import trace
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

tracer = trace.get_tracer(__name__)

@app.post("/api/v1/agents/{agent_id}/chat")
async def chat_with_agent(agent_id: str, message: str):
    with tracer.start_as_current_span("chat_with_agent"):
        # Processing
        pass
```

---

## 🔐 Security Integration

### Service-to-Service Authentication

Use JWT tokens for inter-service communication:

```go
// In WebRTC Server
func (c *AIClient) getServiceToken() (string, error) {
    // Generate service-to-service JWT
    claims := jwt.MapClaims{
        "service": "webrtc-server",
        "iss": "auralink",
        "exp": time.Now().Add(5 * time.Minute).Unix(),
    }
    
    token := jwt.NewWithClaims(jwt.SigningMethodHS256, claims)
    return token.SignedString([]byte(c.serviceSecret))
}
```

### mTLS for Internal Communication

Configure mutual TLS for production:

```yaml
# kubernetes/service-mesh/mtls-policy.yaml
apiVersion: security.istio.io/v1beta1
kind: PeerAuthentication
metadata:
  name: auralink-mtls
spec:
  mtls:
    mode: STRICT
```

---

## 🧪 End-to-End Testing

### Integration Test Example

```python
# tests/integration/test_microservice_integration.py
import pytest
import asyncio

@pytest.mark.asyncio
async def test_webrtc_ai_integration():
    # 1. Create room via Dashboard API
    room = await dashboard_client.create_room({
        "name": "Test Room",
        "ai_agent_enabled": True,
        "agent_id": "test-agent-123"
    })
    
    # 2. Verify agent joined via WebRTC Server
    participants = await webrtc_client.get_room_participants(room['id'])
    assert any(p['is_agent'] for p in participants)
    
    # 3. Send message via AI Core
    response = await ai_client.chat_with_agent(
        agent_id="test-agent-123",
        message="Hello, agent!"
    )
    assert response['message'] is not None
    
    # 4. Verify message in room
    messages = await webrtc_client.get_room_messages(room['id'])
    assert len(messages) > 0
```

---

## 📝 Best Practices

1. **Use HTTP for synchronous requests** (agent creation, MCP queries)
2. **Use Redis PubSub for events** (room events, call updates)
3. **Implement circuit breakers** for resilience
4. **Add request timeouts** (30s default, 60s for AI operations)
5. **Log with correlation IDs** for distributed tracing
6. **Handle graceful degradation** (fallback to basic features)
7. **Monitor inter-service latency**
8. **Use service mesh** (Istio) for advanced routing
9. **Implement rate limiting** per service
10. **Document API contracts** (OpenAPI/Swagger)

---

## 🎯 Summary

### Integration Points

| From Service | To Service | Protocol | Use Case |
|--------------|------------|----------|----------|
| WebRTC Server | AI Core | HTTP/gRPC | Agent auto-join, transcription |
| Dashboard | AI Core | HTTP | Agent management, MCP setup |
| Ingress/Egress | AI Core | HTTP | SIP call AI processing |
| All Services | Redis | PubSub | Event notifications |
| All Services | Prometheus | Metrics | Monitoring |
| All Services | Jaeger | Traces | Distributed tracing |

### Key Takeaways

✅ **HTTP/REST** for synchronous operations  
✅ **Redis PubSub** for asynchronous events  
✅ **gRPC** for high-performance streaming  
✅ **Circuit breakers** for fault tolerance  
✅ **Service mesh** for advanced networking  
✅ **Distributed tracing** for debugging  

---

*Integration Complete - All microservices connected to Phase 5 AI capabilities*  
*© 2025 AuraLinkRTC Inc.*

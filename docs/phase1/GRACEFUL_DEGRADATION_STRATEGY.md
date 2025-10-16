# Graceful Degradation & Fallback Strategy - Phase 1

**Version**: 1.0  
**Date**: October 15, 2025  
**Status**: Phase 1 Resilience Framework

---

## 📋 Overview

This document outlines graceful degradation scenarios and fallback service strategies for AuraLink microservices. It defines how each service should behave when dependencies fail, ensuring the system remains partially functional rather than completely failing.

---

## 🎯 Core Principles

1. **Fail Gracefully**: Degrade functionality rather than crash
2. **User Transparency**: Inform users of reduced functionality
3. **Automatic Recovery**: Return to full functionality when dependencies recover
4. **Data Integrity**: Never compromise data consistency
5. **Circuit Breaker First**: Use circuit breakers before fallbacks activate

---

## 🏗️ Service Degradation Matrix

### Dashboard Service

#### Dependencies
- **PostgreSQL (Supabase)**: Primary data store
- **Redis**: Session cache
- **AI Core Service**: AI features
- **WebRTC Server**: Room management

#### Degradation Scenarios

##### 1. PostgreSQL Unavailable
**Impact**: CRITICAL  
**Circuit Breaker**: 5 failures → Open  
**Timeout**: 60 seconds before half-open

**Fallback Strategy**:
```go
// Read operations
- Try cache first (Redis)
- If cache miss → Return cached stale data (with warning)
- If no cache → Return error with retry-after header

// Write operations
- Queue in Redis with TTL
- Return 503 Service Unavailable
- Background job processes queue when DB recovers
```

**User Experience**:
- Read: Show cached data with "Data may be outdated" banner
- Write: "Service temporarily unavailable. Please try again in a few minutes"

**Implementation**:
```go
func (s *DashboardService) GetUser(ctx context.Context, userID string) (*User, error) {
    // Try database with circuit breaker
    user, err := s.circuitBreaker.Execute(ctx, func() error {
        return s.db.GetUser(ctx, userID)
    })
    
    if err == resilience.ErrCircuitOpen {
        // Fallback to cache
        cached, cacheErr := s.cache.GetJSON(ctx, "user:"+userID, &user)
        if cacheErr == nil {
            user.Stale = true // Mark as potentially outdated
            return user, nil
        }
        return nil, ErrServiceDegraded
    }
    
    return user, err
}
```

##### 2. Redis Unavailable
**Impact**: MEDIUM  
**Circuit Breaker**: 3 failures → Open  
**Timeout**: 30 seconds before half-open

**Fallback Strategy**:
```go
// Session management
- Use in-memory cache (per-instance, expires in 5 minutes)
- Accept slight session inconsistency across replicas

// Rate limiting
- Disable rate limiting temporarily (log warning)
- Fall back to API gateway rate limiting

// Caching
- Direct database queries (slower but functional)
```

**User Experience**:
- Normal operation, slightly slower responses
- Users may need to re-authenticate if load balanced to different instance

**Implementation**:
```go
func (s *DashboardService) GetFromCache(ctx context.Context, key string) (string, error) {
    val, err := s.redis.Get(ctx, key)
    if err != nil {
        // Fallback to in-memory cache
        s.logger.Warn("Redis unavailable, using in-memory cache")
        return s.memoryCache.Get(key)
    }
    return val, nil
}
```

##### 3. AI Core Service Unavailable
**Impact**: LOW  
**Circuit Breaker**: 5 failures → Open  
**Timeout**: 60 seconds before half-open

**Fallback Strategy**:
```go
// AI features disabled
- Agent creation: Queue for later processing
- Chat: Return "AI temporarily unavailable"
- Translation: Disable feature, show original language
- Memory: Store without embedding (process later)
```

**User Experience**:
- Core features (calls, rooms) work normally
- AI features show "Temporarily unavailable" message
- Queued operations process when service recovers

##### 4. WebRTC Server Unavailable
**Impact**: HIGH  
**Circuit Breaker**: 3 failures → Open  
**Timeout**: 30 seconds before half-open

**Fallback Strategy**:
```go
// Room operations
- Room creation: Return error immediately
- Existing rooms: Read from cache/database
- Token generation: Fail with clear error message

// No fallback for core media functionality
```

**User Experience**:
- Cannot create new calls
- Can view call history and recordings
- Clear error: "Video calling temporarily unavailable"

---

### AI Core Service

#### Dependencies
- **PostgreSQL (Supabase)**: Agent/memory storage
- **Redis**: Caching
- **Vector Database (Future)**: Semantic search
- **External APIs**: OpenAI, ElevenLabs, etc.

#### Degradation Scenarios

##### 1. PostgreSQL Unavailable
**Impact**: HIGH  
**Circuit Breaker**: 5 failures → Open

**Fallback Strategy**:
```python
# Agent operations
- Read: Return from Redis cache
- Write: Queue in Redis, sync later

# Memory operations
- Store in Redis temporarily
- Background job syncs to database
```

##### 2. External AI Provider Unavailable
**Impact**: HIGH  
**Circuit Breaker**: 3 failures → Open

**Fallback Strategy**:
```python
# LLM calls
- Try fallback provider (if configured)
- GPT-4 → GPT-3.5 → Claude → Error

# Return cached responses for identical queries
- Check Redis for query hash
- Return with "Cached response" indicator
```

**Implementation**:
```python
async def chat_with_fallback(message: str, config: AgentConfig):
    providers = [config.primary_model, config.fallback_model]
    
    for provider in providers:
        try:
            response = await circuit_breaker.execute(
                lambda: call_llm(provider, message)
            )
            return response
        except CircuitBreakerError:
            logger.warning(f"{provider} unavailable, trying fallback")
            continue
    
    # All providers failed, check cache
    cached = await redis.get(f"chat_cache:{hash(message)}")
    if cached:
        return {"response": cached, "cached": True}
    
    raise ServiceDegradedError("All AI providers unavailable")
```

---

### WebRTC Server

#### Dependencies
- **Redis**: State synchronization
- **PostgreSQL**: Call metadata
- **TURN/STUN Servers**: NAT traversal

#### Degradation Scenarios

##### 1. Redis Unavailable
**Impact**: CRITICAL  
**Circuit Breaker**: 3 failures → Open

**Fallback Strategy**:
```go
// State management
- Use in-memory state (single instance only)
- Disable multi-region clustering
- Log warning about potential data loss

// Room coordination
- Direct peer-to-peer where possible
- Reduce to single SFU instance
```

**User Experience**:
- Calls continue for connected users
- New calls may fail
- Performance degraded

##### 2. TURN Server Unavailable
**Impact**: MEDIUM  
**Fallback**: Automatic by WebRTC

**Strategy**:
```
- Try STUN only (works for ~80% of cases)
- Direct P2P if possible
- Fail only if both peers behind symmetric NAT
```

---

## 🔄 Fallback Priority Matrix

| Service | Dependency | Priority | Fallback | Data Loss Risk |
|---------|-----------|----------|----------|----------------|
| Dashboard | PostgreSQL | P0 | Cache → Queue | Low (queued) |
| Dashboard | Redis | P1 | Memory Cache | Medium (per-instance) |
| Dashboard | AI Core | P2 | Disable Feature | None |
| Dashboard | WebRTC | P0 | Read-only Mode | None |
| AI Core | PostgreSQL | P0 | Redis Queue | Low (queued) |
| AI Core | LLM API | P0 | Fallback Provider | None |
| WebRTC | Redis | P0 | In-Memory | High (state) |
| WebRTC | TURN | P1 | STUN Only | None |

---

## 🚨 Failure Response Codes

### HTTP Status Codes
- `503 Service Unavailable`: Dependency down, retry later
- `429 Too Many Requests`: Circuit breaker open
- `200 OK` + `X-Degraded-Mode: true`: Functioning with fallback

### Custom Headers
```
X-Degraded-Mode: true
X-Fallback-Used: redis-cache
X-Retry-After: 60
X-Circuit-State: open
```

---

## 📊 Monitoring & Alerting

### Key Metrics

1. **Circuit Breaker States**
   ```
   circuit_breaker_state{service="dashboard", dependency="postgres"}
   ```

2. **Fallback Usage**
   ```
   fallback_activations_total{service="dashboard", fallback="cache"}
   ```

3. **Degraded Mode Duration**
   ```
   degraded_mode_duration_seconds{service="ai-core"}
   ```

### Alert Conditions

```yaml
# Critical: Primary dependency down
- alert: ServiceDegraded
  expr: circuit_breaker_state{state="open"} == 1
  for: 5m
  severity: warning

# Critical: Fallback failing too
- alert: FallbackFailing
  expr: rate(fallback_errors_total[5m]) > 0.1
  for: 2m
  severity: critical
```

---

## 🔧 Configuration

### Environment Variables

```bash
# Circuit breaker settings
CIRCUIT_BREAKER_MAX_FAILURES=5
CIRCUIT_BREAKER_TIMEOUT=60s

# Fallback settings
ENABLE_CACHE_FALLBACK=true
ENABLE_MEMORY_CACHE=true
MEMORY_CACHE_SIZE=100MB
MEMORY_CACHE_TTL=300s

# Queue settings
FALLBACK_QUEUE_TTL=3600s
FALLBACK_QUEUE_MAX_SIZE=10000
```

---

## 🧪 Testing Scenarios

### Chaos Engineering

1. **Kill PostgreSQL**
   ```bash
   kubectl scale deployment postgres --replicas=0
   # Verify: Dashboard returns cached data
   # Verify: Writes queued in Redis
   ```

2. **Kill Redis**
   ```bash
   kubectl scale deployment redis --replicas=0
   # Verify: In-memory cache activated
   # Verify: Sessions still work (per-instance)
   ```

3. **Kill AI Core**
   ```bash
   kubectl scale deployment ai-core --replicas=0
   # Verify: Core features (calls) still work
   # Verify: AI features return "unavailable"
   ```

4. **Simulate High Latency**
   ```bash
   # Add 5s delay to database
   # Verify: Requests timeout and fallback activates
   ```

---

## 📝 Recovery Procedures

### Automatic Recovery

1. **Circuit Breaker Half-Open**
   - After timeout, allow 1 request through
   - If successful → Close circuit
   - If failed → Reopen circuit

2. **Queue Processing**
   - Background job checks queue every 30s
   - Process queued writes in order
   - Retry failed items 3 times
   - Dead letter queue after 3 failures

3. **Cache Invalidation**
   - Invalidate all stale cache entries
   - Force refresh from primary source

### Manual Recovery

```bash
# Force circuit breaker reset
curl -X POST http://dashboard:8080/admin/circuit-breaker/reset

# Clear fallback queue
redis-cli DEL fallback:queue:*

# Verify health
curl http://dashboard:8080/health/detailed
```

---

## ✅ Implementation Checklist

### Dashboard Service
- [x] Circuit breakers for all dependencies
- [x] Redis cache fallback
- [ ] In-memory cache implementation
- [ ] Queue for write operations
- [ ] Background queue processor
- [ ] Degraded mode HTTP headers

### AI Core Service
- [x] Circuit breakers for providers
- [x] Provider fallback chain
- [ ] Response caching by query hash
- [ ] Queue for storage operations
- [ ] Graceful error messages

### WebRTC Server
- [x] Redis circuit breaker
- [ ] In-memory state fallback
- [ ] STUN-only fallback mode
- [ ] Connection quality monitoring

---

## 🎓 Best Practices

1. **Always Cache Successfully**
   - Cache all successful responses
   - Set appropriate TTL
   - Use cache for fallback

2. **Log All Degradations**
   - Log when fallback activates
   - Log circuit breaker state changes
   - Alert operations team

3. **Test Regularly**
   - Monthly chaos engineering tests
   - Verify fallbacks work
   - Measure recovery time

4. **Monitor User Impact**
   - Track degraded mode usage
   - Measure user complaints
   - A/B test fallback strategies

5. **Document Every Scenario**
   - Keep this document updated
   - Add new scenarios as discovered
   - Share with operations team

---

**Status**: ✅ Phase 1 Graceful Degradation Strategy Complete  
**Next Review**: After Phase 2 implementation  
**Owner**: Platform Engineering Team

*© 2025 AuraLinkRTC Inc.*

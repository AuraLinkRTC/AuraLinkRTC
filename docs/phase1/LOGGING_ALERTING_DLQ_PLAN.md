# Comprehensive Logging, Alerting & Dead-Letter Queue Plan - Phase 1

**Version**: 1.0  
**Date**: October 15, 2025  
**Status**: Phase 1 Observability Framework

---

## 📋 Executive Summary

This document defines the comprehensive strategy for logging, alerting, and dead-letter queue (DLQ) handling across all AuraLink microservices. It establishes standards, tooling, and procedures for Phase 1 and beyond.

---

## 📝 Logging Strategy

### Logging Levels

| Level | Usage | Examples |
|-------|-------|----------|
| **TRACE** | Detailed execution flow | Function entry/exit, loop iterations |
| **DEBUG** | Development debugging | Variable values, state transitions |
| **INFO** | Normal operations | Request started, user logged in, room created |
| **WARN** | Recoverable issues | Fallback activated, retry attempted, cache miss |
| **ERROR** | Error conditions | Database timeout, API call failed |
| **FATAL** | Unrecoverable errors | Cannot start service, critical resource missing |

### Structured Logging Format

**Standard**: JSON format for all services

```json
{
  "timestamp": "2025-10-15T23:21:00.000Z",
  "level": "INFO",
  "service": "dashboard-service",
  "trace_id": "abc123...",
  "span_id": "def456...",
  "user_id": "user_789",
  "message": "Room created successfully",
  "context": {
    "room_id": "room_xyz",
    "participants": 3,
    "duration_ms": 45
  },
  "metadata": {
    "instance_id": "pod-1",
    "version": "1.0.0",
    "environment": "production"
  }
}
```

### Required Fields

**Every log entry MUST include**:
- `timestamp` (ISO 8601)
- `level` (TRACE|DEBUG|INFO|WARN|ERROR|FATAL)
- `service` (service name)
- `message` (human-readable)
- `trace_id` (distributed tracing ID)

**Include when available**:
- `user_id` (for user actions)
- `request_id` (for API requests)
- `span_id` (Jaeger span)
- `error_code` (for errors)
- `stack_trace` (for errors)

---

## 🏗️ Logging Infrastructure

### Log Aggregation Stack

**Phase 1 Stack**: Loki + Promtail + Grafana

```yaml
# Why Loki over ELK?
# - Lower resource usage
# - Better Kubernetes integration
# - Easier to operate
# - Integrates with Grafana
```

### Architecture

```
┌─────────────┐
│ Microservice│
│   (stdout)  │
└──────┬──────┘
       │
       ▼
┌─────────────┐
│  Promtail   │  ← Collects logs from pods
└──────┬──────┘
       │
       ▼
┌─────────────┐
│    Loki     │  ← Stores and indexes logs
└──────┬──────┘
       │
       ▼
┌─────────────┐
│   Grafana   │  ← Query and visualize
└─────────────┘
```

### Deployment Configuration

**Loki Deployment** (`infrastructure/logging/loki.yaml`):
```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: loki-config
  namespace: auralink
data:
  loki.yaml: |
    auth_enabled: false
    
    server:
      http_listen_port: 3100
    
    ingester:
      lifecycler:
        ring:
          kvstore:
            store: inmemory
          replication_factor: 1
      chunk_idle_period: 5m
      chunk_retain_period: 30s
    
    schema_config:
      configs:
        - from: 2025-10-01
          store: boltdb-shipper
          object_store: s3
          schema: v11
          index:
            prefix: loki_index_
            period: 24h
    
    storage_config:
      boltdb_shipper:
        active_index_directory: /loki/index
        cache_location: /loki/cache
        shared_store: s3
      aws:
        s3: s3://auralink-logs
        region: us-east-1
    
    limits_config:
      retention_period: 720h  # 30 days
      ingestion_rate_mb: 10
      ingestion_burst_size_mb: 20
    
    chunk_store_config:
      max_look_back_period: 720h
```

**Promtail Deployment** (`infrastructure/logging/promtail.yaml`):
```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: promtail-config
  namespace: auralink
data:
  promtail.yaml: |
    server:
      http_listen_port: 9080
      grpc_listen_port: 0
    
    positions:
      filename: /tmp/positions.yaml
    
    clients:
      - url: http://loki:3100/loki/api/v1/push
    
    scrape_configs:
      - job_name: kubernetes-pods
        kubernetes_sd_configs:
          - role: pod
        relabel_configs:
          - source_labels: [__meta_kubernetes_pod_label_app]
            target_label: app
          - source_labels: [__meta_kubernetes_namespace]
            target_label: namespace
          - source_labels: [__meta_kubernetes_pod_name]
            target_label: pod
        pipeline_stages:
          - json:
              expressions:
                level: level
                trace_id: trace_id
                user_id: user_id
          - labels:
              level:
              trace_id:
              user_id:
```

---

## 🎯 Service-Specific Logging Standards

### Dashboard Service (Go)

**Implementation** (`shared/libs/go/logging/logger.go`):
```go
package logging

import (
    "context"
    "encoding/json"
    "os"
    "time"
    
    "go.opentelemetry.io/otel/trace"
)

type Logger struct {
    serviceName string
    level       Level
    output      *os.File
}

type LogEntry struct {
    Timestamp string                 `json:"timestamp"`
    Level     string                 `json:"level"`
    Service   string                 `json:"service"`
    TraceID   string                 `json:"trace_id,omitempty"`
    SpanID    string                 `json:"span_id,omitempty"`
    UserID    string                 `json:"user_id,omitempty"`
    Message   string                 `json:"message"`
    Context   map[string]interface{} `json:"context,omitempty"`
    Error     string                 `json:"error,omitempty"`
    Stack     string                 `json:"stack,omitempty"`
}

func (l *Logger) Info(ctx context.Context, message string, fields map[string]interface{}) {
    l.log(ctx, LevelInfo, message, fields, nil)
}

func (l *Logger) Error(ctx context.Context, message string, err error, fields map[string]interface{}) {
    l.log(ctx, LevelError, message, fields, err)
}

func (l *Logger) log(ctx context.Context, level Level, message string, fields map[string]interface{}, err error) {
    entry := LogEntry{
        Timestamp: time.Now().UTC().Format(time.RFC3339Nano),
        Level:     level.String(),
        Service:   l.serviceName,
        Message:   message,
        Context:   fields,
    }
    
    // Extract trace context
    span := trace.SpanFromContext(ctx)
    if span.SpanContext().IsValid() {
        entry.TraceID = span.SpanContext().TraceID().String()
        entry.SpanID = span.SpanContext().SpanID().String()
    }
    
    // Extract user context
    if userID, ok := ctx.Value("user_id").(string); ok {
        entry.UserID = userID
    }
    
    // Add error details
    if err != nil {
        entry.Error = err.Error()
        // TODO: Add stack trace capture
    }
    
    json.NewEncoder(l.output).Encode(entry)
}
```

**Usage**:
```go
logger.Info(ctx, "Room created", map[string]interface{}{
    "room_id": roomID,
    "created_by": userID,
    "max_participants": maxParticipants,
})

logger.Error(ctx, "Failed to create room", err, map[string]interface{}{
    "room_name": roomName,
    "retry_count": retryCount,
})
```

### AI Core Service (Python)

**Implementation** (`shared/libs/python/auralink_shared/logging.py`):
```python
import json
import logging
import sys
from datetime import datetime
from typing import Dict, Any, Optional
from contextvars import ContextVar

# Context variables for request tracking
trace_id_var: ContextVar[str] = ContextVar('trace_id', default='')
user_id_var: ContextVar[str] = ContextVar('user_id', default='')

class StructuredLogger:
    def __init__(self, service_name: str, level: str = "INFO"):
        self.service_name = service_name
        self.level = getattr(logging, level.upper())
        
    def _log(self, level: str, message: str, context: Optional[Dict[str, Any]] = None, 
             error: Optional[Exception] = None):
        entry = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": level,
            "service": self.service_name,
            "message": message,
        }
        
        # Add trace context
        trace_id = trace_id_var.get()
        if trace_id:
            entry["trace_id"] = trace_id
        
        # Add user context
        user_id = user_id_var.get()
        if user_id:
            entry["user_id"] = user_id
        
        # Add custom context
        if context:
            entry["context"] = context
        
        # Add error details
        if error:
            entry["error"] = str(error)
            entry["error_type"] = type(error).__name__
        
        print(json.dumps(entry), file=sys.stdout, flush=True)
    
    def info(self, message: str, context: Optional[Dict[str, Any]] = None):
        self._log("INFO", message, context)
    
    def error(self, message: str, error: Optional[Exception] = None, 
              context: Optional[Dict[str, Any]] = None):
        self._log("ERROR", message, context, error)
    
    def warn(self, message: str, context: Optional[Dict[str, Any]] = None):
        self._log("WARN", message, context)
```

**Usage**:
```python
logger.info("Agent created", context={
    "agent_id": agent_id,
    "model": config.model,
    "temperature": config.temperature
})

logger.error("LLM call failed", error=e, context={
    "model": model_name,
    "retry_count": retry_count
})
```

---

## 🚨 Alerting Strategy

### Alert Hierarchy

```
CRITICAL (P0) → PagerDuty + Slack + Email
   ↓
WARNING (P1) → Slack + Email
   ↓
INFO (P2) → Slack only
```

### Alert Rules (Already defined in `infrastructure/monitoring/alert-rules.yaml`)

**Enhanced with DLQ Alerts**:
```yaml
- name: auralink_dead_letter_queue
  interval: 30s
  rules:
    - alert: DLQHighVolume
      expr: rate(dlq_messages_total[5m]) > 10
      for: 5m
      labels:
        severity: warning
      annotations:
        summary: "High DLQ volume"
        description: "{{ $value }} messages/sec in dead letter queue"
    
    - alert: DLQProcessingFailed
      expr: rate(dlq_processing_errors_total[5m]) > 1
      for: 5m
      labels:
        severity: critical
      annotations:
        summary: "DLQ processing failing"
        description: "DLQ messages cannot be processed"
```

### Alert Manager Configuration

**`infrastructure/monitoring/alertmanager.yaml`**:
```yaml
global:
  resolve_timeout: 5m
  slack_api_url: '${SLACK_WEBHOOK_URL}'

route:
  group_by: ['alertname', 'service']
  group_wait: 10s
  group_interval: 10s
  repeat_interval: 12h
  receiver: 'slack-notifications'
  
  routes:
    # Critical alerts go to PagerDuty
    - match:
        severity: critical
      receiver: 'pagerduty'
      continue: true
    
    # All alerts go to Slack
    - match_re:
        severity: (critical|warning|info)
      receiver: 'slack-notifications'

receivers:
  - name: 'pagerduty'
    pagerduty_configs:
      - service_key: '${PAGERDUTY_SERVICE_KEY}'
        description: '{{ .GroupLabels.alertname }}: {{ .CommonAnnotations.summary }}'
  
  - name: 'slack-notifications'
    slack_configs:
      - channel: '#auralink-alerts'
        title: '[{{ .Status | toUpper }}] {{ .GroupLabels.alertname }}'
        text: >-
          {{ range .Alerts }}
            *Alert:* {{ .Annotations.summary }}
            *Description:* {{ .Annotations.description }}
            *Severity:* {{ .Labels.severity }}
          {{ end }}
```

---

## 📬 Dead-Letter Queue (DLQ) Strategy

### Purpose

DLQ handles messages that cannot be processed after multiple retry attempts, preventing data loss and enabling manual review.

### Use Cases

1. **Write Operations During DB Outage**
   - User creates room → DB down → Queue in Redis
   - After 3 retries fail → Move to DLQ
   - Manual review and replay

2. **Failed AI Operations**
   - Agent creation → LLM API timeout
   - After 3 retries → DLQ
   - Process when API recovers

3. **Webhook Delivery Failures**
   - External webhook → Target down
   - Retry with backoff → DLQ after 5 attempts

### Architecture

```
┌──────────────┐
│   Request    │
└──────┬───────┘
       │
       ▼
┌──────────────┐
│   Primary    │
│  Processing  │
└──────┬───────┘
       │ (failure)
       ▼
┌──────────────┐
│ Retry Queue  │ ← 3 retry attempts
└──────┬───────┘
       │ (still failing)
       ▼
┌──────────────┐
│     DLQ      │ ← Manual review
└──────────────┘
```

### Implementation

**Redis-Based DLQ** (`shared/libs/go/dlq/dlq.go`):
```go
package dlq

import (
    "context"
    "encoding/json"
    "time"
    
    "github.com/redis/go-redis/v9"
)

type Message struct {
    ID            string                 `json:"id"`
    OriginalQueue string                 `json:"original_queue"`
    Payload       map[string]interface{} `json:"payload"`
    Error         string                 `json:"error"`
    Attempts      int                    `json:"attempts"`
    FirstAttempt  time.Time              `json:"first_attempt"`
    LastAttempt   time.Time              `json:"last_attempt"`
    CreatedAt     time.Time              `json:"created_at"`
}

type DLQ struct {
    redis  *redis.Client
    prefix string
}

func NewDLQ(client *redis.Client) *DLQ {
    return &DLQ{
        redis:  client,
        prefix: "dlq:",
    }
}

func (d *DLQ) Add(ctx context.Context, msg Message) error {
    msg.CreatedAt = time.Now()
    
    data, err := json.Marshal(msg)
    if err != nil {
        return err
    }
    
    key := d.prefix + msg.OriginalQueue
    return d.redis.LPush(ctx, key, data).Err()
}

func (d *DLQ) List(ctx context.Context, queue string, limit int64) ([]Message, error) {
    key := d.prefix + queue
    results, err := d.redis.LRange(ctx, key, 0, limit-1).Result()
    if err != nil {
        return nil, err
    }
    
    messages := make([]Message, 0, len(results))
    for _, result := range results {
        var msg Message
        if err := json.Unmarshal([]byte(result), &msg); err != nil {
            continue
        }
        messages = append(messages, msg)
    }
    
    return messages, nil
}

func (d *DLQ) Remove(ctx context.Context, queue, messageID string) error {
    // Remove specific message by ID
    key := d.prefix + queue
    messages, err := d.List(ctx, queue, 1000)
    if err != nil {
        return err
    }
    
    for _, msg := range messages {
        if msg.ID == messageID {
            data, _ := json.Marshal(msg)
            return d.redis.LRem(ctx, key, 1, data).Err()
        }
    }
    
    return nil
}

func (d *DLQ) Retry(ctx context.Context, queue, messageID string) error {
    messages, err := d.List(ctx, queue, 1000)
    if err != nil {
        return err
    }
    
    for _, msg := range messages {
        if msg.ID == messageID {
            // Remove from DLQ
            if err := d.Remove(ctx, queue, messageID); err != nil {
                return err
            }
            
            // Re-queue to original queue
            data, _ := json.Marshal(msg.Payload)
            return d.redis.RPush(ctx, msg.OriginalQueue, data).Err()
        }
    }
    
    return nil
}
```

**Usage**:
```go
// When operation fails after retries
if retryCount >= maxRetries {
    dlqMessage := dlq.Message{
        ID:            uuid.New().String(),
        OriginalQueue: "rooms:create",
        Payload: map[string]interface{}{
            "room_name": roomName,
            "user_id": userID,
        },
        Error:        err.Error(),
        Attempts:     retryCount,
        FirstAttempt: firstAttemptTime,
        LastAttempt:  time.Now(),
    }
    
    deadLetterQueue.Add(ctx, dlqMessage)
    logger.Error(ctx, "Operation moved to DLQ", err, map[string]interface{}{
        "dlq_message_id": dlqMessage.ID,
    })
}
```

### DLQ Management API

**Dashboard Service Endpoints**:
```go
// GET /api/v1/admin/dlq
// List DLQ messages
func ListDLQMessages(w http.ResponseWriter, r *http.Request) {
    queue := r.URL.Query().Get("queue")
    messages, err := dlq.List(ctx, queue, 100)
    json.NewEncoder(w).Encode(messages)
}

// POST /api/v1/admin/dlq/{message_id}/retry
// Retry a DLQ message
func RetryDLQMessage(w http.ResponseWriter, r *http.Request) {
    messageID := mux.Vars(r)["message_id"]
    queue := r.FormValue("queue")
    
    err := dlq.Retry(ctx, queue, messageID)
    if err != nil {
        http.Error(w, err.Error(), 500)
        return
    }
    
    w.WriteHeader(204)
}

// DELETE /api/v1/admin/dlq/{message_id}
// Remove a DLQ message (acknowledge failure)
func DeleteDLQMessage(w http.ResponseWriter, r *http.Request) {
    messageID := mux.Vars(r)["message_id"]
    queue := r.FormValue("queue")
    
    err := dlq.Remove(ctx, queue, messageID)
    if err != nil {
        http.Error(w, err.Error(), 500)
        return
    }
    
    w.WriteHeader(204)
}
```

---

## 📊 Log Queries & Dashboards

### Common Loki Queries

**1. Error logs in last hour**:
```logql
{app="dashboard-service", level="ERROR"} |= "" | json
```

**2. Logs for specific user**:
```logql
{app=~".*-service"} | json | user_id="user_123"
```

**3. Trace all requests for a trace_id**:
```logql
{app=~".*-service"} | json | trace_id="abc123..."
```

**4. High latency requests**:
```logql
{app="dashboard-service"} | json | duration_ms > 1000
```

**5. Circuit breaker opens**:
```logql
{app=~".*-service"} |= "circuit breaker" | json | state="open"
```

### Grafana Dashboard Panels

**Log Volume**:
```logql
sum(rate({app=~".*-service"}[5m])) by (app, level)
```

**Error Rate**:
```logql
sum(rate({app=~".*-service", level="ERROR"}[5m])) by (app)
```

**DLQ Size**:
```promql
redis_list_length{key=~"dlq:.*"}
```

---

## ✅ Implementation Checklist

### Logging
- [x] Define logging format (JSON structured)
- [x] Define log levels and standards
- [ ] Implement Go structured logger
- [ ] Implement Python structured logger
- [ ] Deploy Loki stack
- [ ] Deploy Promtail on all nodes
- [ ] Configure log retention (30 days)
- [ ] Create Grafana log dashboards

### Alerting
- [x] Define alert rules
- [x] Configure AlertManager
- [ ] Set up PagerDuty integration
- [ ] Set up Slack integration
- [ ] Test alert routing
- [ ] Document on-call procedures

### Dead-Letter Queue
- [ ] Implement DLQ library (Go)
- [ ] Implement DLQ library (Python)
- [ ] Add DLQ management API
- [ ] Create DLQ monitoring dashboard
- [ ] Document DLQ retry procedures
- [ ] Set up automated DLQ cleanup (>30 days)

---

## 🎯 Success Metrics

### Logging
- **Log Volume**: < 1GB/day per service
- **Log Latency**: < 5 seconds from generation to Loki
- **Log Retention**: 30 days minimum
- **Search Performance**: < 2 seconds for most queries

### Alerting
- **MTTR** (Mean Time To Respond): < 5 minutes for critical
- **False Positive Rate**: < 5%
- **Alert Fatigue**: < 10 alerts/day in normal operation

### DLQ
- **DLQ Size**: < 100 messages in normal operation
- **DLQ Processing Time**: < 1 hour for manual review
- **Message Loss Rate**: 0%

---

**Status**: ✅ Phase 1 Logging/Alerting/DLQ Plan Complete  
**Implementation**: Ongoing  
**Next Review**: After Phase 1 completion  

*© 2025 AuraLinkRTC Inc.*

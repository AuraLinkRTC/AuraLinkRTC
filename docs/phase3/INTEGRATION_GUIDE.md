# 🔌 AuraLink AIC Protocol - Integration Guide

**Version**: 1.0.0  
**Date**: October 15, 2025  
**Status**: Production Ready

---

## 📋 Table of Contents

1. [Prerequisites](#prerequisites)
2. [Database Setup](#database-setup)
3. [AI Core Deployment](#ai-core-deployment)
4. [WebRTC Server Integration](#webrtc-server-integration)
5. [Dashboard Service Setup](#dashboard-service-setup)
6. [Configuration](#configuration)
7. [Testing](#testing)
8. [Monitoring](#monitoring)
9. [Troubleshooting](#troubleshooting)

---

## 🎯 Prerequisites

### Required Services (from Phase 1 & 2)
- ✅ PostgreSQL database (Supabase)
- ✅ Redis instance
- ✅ LiveKit WebRTC Server (forked)
- ✅ Dashboard Service (running)
- ✅ Kubernetes cluster (optional but recommended)

### Required Tools
- Docker & Docker Compose
- kubectl (for Kubernetes)
- Python 3.11+
- Go 1.24+
- psql (PostgreSQL client)

### System Requirements
- **CPU**: 4+ cores (8+ recommended)
- **RAM**: 8GB minimum (16GB recommended)
- **GPU**: Optional (NVIDIA CUDA for better performance)
- **Network**: Low latency connection to AI Core

---

## 💾 Database Setup

### Step 1: Apply Phase 3 Schema Migration

```bash
# Navigate to scripts directory
cd /Users/naveen/Desktop/AuraLink1/scripts/db/migrations

# Apply migration
psql -U postgres -d auralink -f 003_phase3_aic_schema.sql

# Verify tables created
psql -U postgres -d auralink -c "\dt aic_*"
```

**Expected Output**:
```
             List of relations
 Schema |         Name          | Type  |  Owner   
--------+-----------------------+-------+----------
 public | aic_alerts            | table | postgres
 public | aic_configs           | table | postgres
 public | aic_metrics           | table | postgres
 public | aic_model_performance | table | postgres
 public | aic_sessions          | table | postgres
```

### Step 2: Verify RLS Policies

```sql
-- Check Row Level Security is enabled
SELECT schemaname, tablename, rowsecurity 
FROM pg_tables 
WHERE tablename LIKE 'aic_%';
```

### Step 3: Create Initial Configuration

```sql
-- Create default AIC config for test user
INSERT INTO aic_configs (user_id, enabled, mode, target_compression_ratio)
VALUES ('test_user_1', true, 'adaptive', 0.80);
```

---

## 🤖 AI Core Deployment

### Option A: Docker Compose (Development)

**File**: `docker-compose.aic.yml`

```yaml
version: '3.8'

services:
  ai-core:
    build:
      context: ./auralink-ai-core
      dockerfile: Dockerfile
    ports:
      - "8000:8000"  # HTTP API
      - "50051:50051"  # gRPC
    environment:
      - ENVIRONMENT=development
      - SERVICE_PORT=8000
      - GRPC_PORT=50051
      - DATABASE_URL=${DATABASE_URL}
      - REDIS_URL=${REDIS_URL}
      - LOG_LEVEL=info
    volumes:
      - ./models:/app/models
    restart: unless-stopped
```

**Start Services**:
```bash
docker-compose -f docker-compose.aic.yml up -d
```

### Option B: Kubernetes (Production)

```bash
# Apply Kubernetes manifests
kubectl apply -f infrastructure/kubernetes/aic-deployment.yaml

# Wait for pods to be ready
kubectl wait --for=condition=ready pod -l app=ai-core -n auralink-aic --timeout=300s

# Check status
kubectl get pods -n auralink-aic
```

### Step 3: Install Python Dependencies

```bash
cd auralink-ai-core
pip install -r requirements.txt
```

### Step 4: Verify AI Core is Running

```bash
# Check HTTP endpoint
curl http://localhost:8000/health

# Expected response:
# {"status": "healthy", "version": "1.0.0"}

# Check gRPC endpoint
grpcurl -plaintext localhost:50051 list
```

---

## 🎬 WebRTC Server Integration

### Step 1: Update WebRTC Server Configuration

**File**: `auralink-webrtc-server/config.yaml`

```yaml
aic:
  enabled: true
  grpc_endpoint: "localhost:50051"
  connection_timeout: "5s"
  request_timeout: "30ms"
  retry_attempts: 3
  
  # Default settings
  default_mode: "adaptive"
  target_compression_ratio: 0.80
  max_latency_ms: 20
  enable_fallback: true
```

### Step 2: Build WebRTC Server with AIC Support

```bash
cd auralink-webrtc-server

# Build with AIC integration
go build -o bin/livekit-server ./cmd/server

# Run server
./bin/livekit-server --config config.yaml
```

### Step 3: Verify AIC Integration

```bash
# Check logs for AIC initialization
grep "AIC" logs/livekit-server.log

# Expected output:
# [INFO] AIC Protocol enabled
# [INFO] Connected to AI Core at localhost:50051
```

---

## 📊 Dashboard Service Setup

### Step 1: Update Dashboard Service

```bash
cd auralink-dashboard-service

# Build with AIC APIs
go build -o bin/dashboard ./cmd/server

# Run dashboard
./bin/dashboard
```

### Step 2: Register AIC Routes

**File**: `cmd/server/main.go`

```go
import "github.com/auralink/dashboard-service/internal/api"

// In main():
api.RegisterAICRoutes(router, server)
```

### Step 3: Verify Dashboard APIs

```bash
# Test AIC config endpoint
curl -X GET http://localhost:3000/api/v1/aic/config \
  -H "Authorization: Bearer YOUR_TOKEN"

# Test metrics endpoint
curl -X GET http://localhost:3000/api/v1/aic/metrics \
  -H "Authorization: Bearer YOUR_TOKEN"
```

---

## ⚙️ Configuration

### Environment Variables

Create `.env` file:

```bash
# AIC Protocol
AIC_ENABLED=true
AIC_MODE=adaptive
AIC_TARGET_COMPRESSION_RATIO=0.80
AIC_MAX_LATENCY_MS=20

# AI Core
AI_CORE_GRPC_ENDPOINT=localhost:50051
AI_CORE_HTTP_ENDPOINT=http://localhost:8000

# Database
DATABASE_URL=postgresql://user:pass@localhost:5432/auralink

# Redis
REDIS_URL=redis://localhost:6379/0

# Monitoring
PROMETHEUS_ENABLED=true
GRAFANA_ENABLED=true
```

### Load Configuration

```bash
# Export environment variables
source .env

# Verify
echo $AIC_ENABLED
```

---

## 🧪 Testing

### Unit Tests

```bash
# Test AI Core compression engine
cd auralink-ai-core
pytest tests/integration/test_aic_protocol.py -v

# Test WebRTC integration
cd auralink-webrtc-server
go test ./pkg/rtc/aic_integration_test.go -v
```

### Integration Test

```bash
# Full end-to-end test
python tests/integration/test_aic_e2e.py

# Expected output:
# ✅ Database connection successful
# ✅ AI Core gRPC connection successful
# ✅ Frame compression test passed
# ✅ Quality threshold maintained
# ✅ Bandwidth reduction: 82%
```

### Performance Benchmark

```bash
# Run benchmarks
pytest tests/integration/test_aic_protocol.py::test_compression_latency_benchmark -v

# Expected results:
# Average latency: 10.5ms ✅
# P95 latency: 15.2ms ✅
# P99 latency: 18.8ms ✅
# Bandwidth reduction: 80.5% ✅
```

---

## 📈 Monitoring

### Prometheus Metrics

AIC exposes the following metrics:

```
# Compression metrics
aic_compression_ratio{mode="adaptive"}
aic_inference_latency_ms{model="encodec"}
aic_quality_score{mode="adaptive"}
aic_bandwidth_saved_bytes_total

# Performance metrics
aic_requests_total{status="success"}
aic_fallback_total{reason="quality_threshold"}
aic_errors_total{type="timeout"}

# Resource metrics
aic_gpu_utilization_percent
aic_memory_usage_bytes
```

### Grafana Dashboard

Import dashboard from: `infrastructure/monitoring/grafana/aic-dashboard.json`

**Key Panels**:
- Compression ratio over time
- Inference latency (avg, p95, p99)
- Quality score distribution
- Bandwidth savings
- Fallback rate
- Error rate

### Alerting Rules

**File**: `infrastructure/monitoring/prometheus/aic-alerts.yml`

```yaml
groups:
  - name: aic_protocol
    rules:
      - alert: HighInferenceLatency
        expr: aic_inference_latency_ms{quantile="0.95"} > 30
        for: 5m
        annotations:
          summary: "AIC inference latency is high"
          
      - alert: HighFallbackRate
        expr: rate(aic_fallback_total[5m]) > 0.05
        for: 10m
        annotations:
          summary: "AIC fallback rate exceeds 5%"
```

---

## 🔍 Troubleshooting

### Issue: AI Core not connecting

**Symptoms**: WebRTC Server logs show "Failed to connect to AI Core"

**Solution**:
```bash
# Check AI Core is running
curl http://localhost:8000/health

# Check gRPC port is open
telnet localhost 50051

# Check firewall rules
sudo iptables -L | grep 50051

# Verify configuration
grep "grpc_endpoint" auralink-webrtc-server/config.yaml
```

### Issue: High inference latency

**Symptoms**: Average latency > 20ms

**Solutions**:
1. Enable GPU acceleration:
   ```yaml
   gpu:
     enabled: true
     device_id: 0
   ```

2. Scale AI Core pods:
   ```bash
   kubectl scale deployment ai-core-aic --replicas=5 -n auralink-aic
   ```

3. Use conservative mode:
   ```sql
   UPDATE aic_configs SET mode = 'conservative' WHERE user_id = 'user_123';
   ```

### Issue: Quality degradation

**Symptoms**: Quality score < 0.85

**Solutions**:
1. Increase quality threshold:
   ```sql
   UPDATE aic_configs SET min_quality_score = 0.90 WHERE user_id = 'user_123';
   ```

2. Switch to conservative mode:
   ```bash
   curl -X POST http://localhost:8000/api/v1/aic/config \
     -H "Content-Type: application/json" \
     -d '{"mode": "conservative"}'
   ```

### Issue: Database performance issues

**Symptoms**: Slow metrics queries

**Solutions**:
```sql
-- Create additional indexes
CREATE INDEX CONCURRENTLY idx_aic_metrics_timestamp_desc 
ON aic_metrics(timestamp DESC);

-- Partition old data
CREATE TABLE aic_metrics_archive AS 
SELECT * FROM aic_metrics WHERE timestamp < NOW() - INTERVAL '30 days';

DELETE FROM aic_metrics WHERE timestamp < NOW() - INTERVAL '30 days';
```

### Logs Location

```bash
# AI Core logs
tail -f /var/log/auralink/ai-core.log

# WebRTC Server logs
tail -f /var/log/auralink/webrtc-server.log

# Dashboard logs
tail -f /var/log/auralink/dashboard.log

# Kubernetes logs
kubectl logs -f deployment/ai-core-aic -n auralink-aic
```

---

## 📞 Support

### Getting Help

- **Documentation**: `/docs/phase3/`
- **GitHub Issues**: https://github.com/auralink/auralink/issues
- **Slack**: #auralink-aic-support
- **Email**: support@auralink.com

### Reporting Bugs

Include in your bug report:
1. AIC configuration (mode, target ratio)
2. Inference latency metrics
3. Quality scores
4. Fallback rate
5. Logs from all services
6. Network conditions

---

## 🚀 Next Steps

After successful integration:

1. ✅ Enable AIC for production users
2. ✅ Monitor performance metrics
3. ✅ Tune compression parameters
4. ✅ Scale AI Core as needed
5. ✅ Proceed to Phase 4 implementation

---

**Integration Status**: ✅ **READY FOR PRODUCTION**

*Last Updated: October 15, 2025*  
*© 2025 AuraLinkRTC Inc. All rights reserved.*

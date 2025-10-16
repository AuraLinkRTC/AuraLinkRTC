# AuraLink Ingress-Egress Service Integration

## Overview

This directory contains the **AuraLink integration layer** for the Ingress-Egress Service, built on top of Jitsi Videobridge and Jicofo. The integration layer provides connectivity to the AuraLink ecosystem, including Dashboard Service, AI Core, WebRTC Server, and Communication Service.

## Current Implementation Status

### ✅ Completed (Phase 1 - Foundation Layer)

- **Custom Configuration System** - `auralink.conf` with environment-based feature flags
- **Database Connectivity** - PostgreSQL connection pooling with HikariCP
- **Redis Integration** - State synchronization and caching layer
- **Health Check Endpoints** - `/health` (liveness) and `/ready` (readiness) with dependency validation
- **Docker Containerization** - Multi-stage Dockerfile with optimized image size
- **Service Entrypoint** - Docker entrypoint script with dependency waiting logic

### 🚧 In Progress (Phase 2 - Service Integration)

- REST API client to Dashboard Service
- Authentication layer with JWT validation
- Room synchronization with WebRTC Server
- Prometheus metrics export
- Kubernetes deployment manifests

### ⏳ Planned (Phases 3-6)

- AIC Protocol integration (Phase 3)
- External system bridges - SIP, RTMP, Recording (Phase 4)
- AuraID and Mesh routing integration (Phase 5)
- Enterprise features and comprehensive testing (Phase 6)

---

## Architecture

### Integration Layer Components

```
auralink-integration/
├── src/main/kotlin/org/jitsi/auralink/integration/
│   ├── config/          # Configuration management
│   ├── database/        # PostgreSQL connection pooling
│   ├── redis/           # Redis state management
│   ├── health/          # Health check endpoints
│   ├── api/             # REST API clients (Dashboard, WebRTC Server)
│   ├── grpc/            # gRPC clients (AI Core)
│   ├── auth/            # Authentication and authorization
│   ├── metrics/         # Prometheus metrics exporter
│   ├── sip/             # SIP gateway integration (Phase 4)
│   ├── rtmp/            # RTMP streaming bridge (Phase 4)
│   ├── recording/       # Recording service (Phase 4)
│   └── aic/             # AIC Protocol adapter (Phase 3)
└── auralink.conf        # Main configuration file
```

### Service Dependencies

```
┌─────────────────────────────────────┐
│  Ingress-Egress Service             │
│  ┌─────────────┐  ┌───────────────┐ │
│  │   Jitsi     │  │   AuraLink    │ │
│  │ Videobridge │◄─┤  Integration  │ │
│  │    (JVB)    │  │     Layer     │ │
│  └─────────────┘  └───────┬───────┘ │
└─────────────────────────────┼─────────┘
                              │
              ┌───────────────┼───────────────┐
              │               │               │
              ▼               ▼               ▼
      ┌──────────────┐ ┌──────────┐ ┌──────────────┐
      │  Dashboard   │ │ AI Core  │ │WebRTC Server │
      │   Service    │ │ (gRPC)   │ │  (LiveKit)   │
      └──────────────┘ └──────────┘ └──────────────┘
              │
              ▼
      ┌──────────────┐
      │ PostgreSQL   │
      │   + Redis    │
      └──────────────┘
```

---

## Configuration

### Environment Variables

#### Service Identity
- `AURALINK_SERVICE_NAME` - Service name (default: "ingress-egress")
- `AURALINK_REGION` - Deployment region (default: "us-west-2")
- `AURALINK_ENV` - Environment (default: "production")
- `BRIDGE_ID` - Unique bridge identifier (auto-generated if not provided)

#### Feature Flags
- `ENABLE_AIC` - Enable AIC Protocol support (default: true)
- `ENABLE_SIP` - Enable SIP gateway (default: true)
- `ENABLE_RTMP` - Enable RTMP streaming (default: true)
- `ENABLE_RECORDING` - Enable recording service (default: true)
- `ENABLE_MESH` - Enable mesh routing (default: false)
- `ENABLE_AURAID` - Enable AuraID resolution (default: true)

#### Service Endpoints
- `DASHBOARD_SERVICE_URL` - Dashboard Service endpoint
- `DASHBOARD_API_KEY` - Dashboard authentication key
- `AI_CORE_GRPC_URL` - AI Core gRPC endpoint
- `WEBRTC_SERVER_URL` - WebRTC Server endpoint
- `WEBRTC_API_KEY` - WebRTC Server authentication key

#### Database Configuration
- `DATABASE_URL` - PostgreSQL JDBC URL
- `DB_USER` - Database username
- `DB_PASSWORD` - Database password
- `DB_POOL_SIZE` - Connection pool size (default: 20)
- `DB_AUTO_MIGRATE` - Auto-run migrations (default: true)

#### Redis Configuration
- `REDIS_HOST` - Redis hostname (default: "redis")
- `REDIS_PORT` - Redis port (default: 6379)
- `REDIS_PASSWORD` - Redis authentication password
- `REDIS_DB` - Redis database index (default: 0)

#### External Bridges
- `SIP_SERVER_URL` - SIP gateway endpoint
- `SIP_TRUNK_PROVIDER` - SIP trunk provider (e.g., "twilio")
- `SIP_TRUNK_CREDENTIALS` - SIP trunk authentication
- `RTMP_INGEST_PORT` - RTMP ingest server port (default: 1935)
- `RECORDING_BUCKET` - S3 bucket for recordings
- `RECORDING_S3_REGION` - S3 region

#### Monitoring
- `ENABLE_METRICS` - Enable Prometheus metrics (default: true)
- `PROMETHEUS_PORT` - Metrics export port (default: 9090)
- `LOG_LEVEL` - Logging level (default: "INFO")
- `LOG_FORMAT` - Log format: json or text (default: "json")

### Configuration File Structure

See `auralink.conf` for the complete HOCON configuration structure. Key sections:

- **auralink.service** - Service identity and metadata
- **auralink.features** - Feature flag definitions
- **auralink.dashboard** - Dashboard Service integration settings
- **auralink.ai_core** - AI Core gRPC configuration
- **auralink.webrtc_server** - WebRTC Server integration
- **auralink.database** - PostgreSQL connection settings
- **auralink.redis** - Redis configuration
- **auralink.sip** - SIP gateway settings (Phase 4)
- **auralink.rtmp** - RTMP bridge configuration (Phase 4)
- **auralink.recording** - Recording service settings (Phase 4)
- **auralink.metrics** - Prometheus metrics configuration
- **auralink.health** - Health check settings
- **auralink.security** - Authentication and security

---

## Building and Deployment

### Local Development

#### Prerequisites
- Java 17 or higher
- Maven 3.8+
- Docker and Docker Compose
- PostgreSQL 14+
- Redis 7+

#### Build from Source

```bash
# Navigate to ingress-egress directory
cd auralink-ingress-egress

# Build the project
mvn clean package

# Build Docker image
docker build -t auralink/ingress-egress:latest .
```

#### Run with Docker Compose

```yaml
# docker-compose.yml
version: '3.8'

services:
  ingress-egress:
    image: auralink/ingress-egress:latest
    ports:
      - "8080:8080"   # HTTP API
      - "9090:9090"   # Prometheus metrics
      - "10000:10000/udp"  # RTP media
    environment:
      - AURALINK_ENV=development
      - BRIDGE_ID=bridge-dev-001
      - ENABLE_AIC=true
      - DATABASE_URL=jdbc:postgresql://postgres:5432/auralink
      - DB_USER=auralink
      - DB_PASSWORD=secret
      - REDIS_HOST=redis
      - DASHBOARD_SERVICE_URL=http://auralink-dashboard:8080
      - DASHBOARD_API_KEY=dev-dashboard-key
      - AI_CORE_GRPC_URL=auralink-ai-core:50051
      - WEBRTC_SERVER_URL=http://auralink-webrtc:7880
      - LOG_LEVEL=DEBUG
    depends_on:
      - postgres
      - redis
    networks:
      - auralink-network

  postgres:
    image: postgres:14
    environment:
      - POSTGRES_DB=auralink
      - POSTGRES_USER=auralink
      - POSTGRES_PASSWORD=secret
    volumes:
      - postgres-data:/var/lib/postgresql/data

  redis:
    image: redis:7-alpine
    command: redis-server --appendonly yes
    volumes:
      - redis-data:/data

volumes:
  postgres-data:
  redis-data:

networks:
  auralink-network:
    driver: bridge
```

```bash
# Start services
docker-compose up -d

# View logs
docker-compose logs -f ingress-egress

# Check health
curl http://localhost:8080/health
curl http://localhost:8080/ready
```

### Kubernetes Deployment

#### Deployment Manifest (Phase 2)

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: auralink-ingress-egress
  namespace: auralink
  labels:
    app: ingress-egress
    component: media
spec:
  replicas: 3
  selector:
    matchLabels:
      app: ingress-egress
  template:
    metadata:
      labels:
        app: ingress-egress
    spec:
      containers:
      - name: ingress-egress
        image: auralink/ingress-egress:latest
        ports:
        - containerPort: 8080
          name: http
        - containerPort: 9090
          name: metrics
        - containerPort: 10000
          protocol: UDP
          name: rtp
        env:
        - name: AURALINK_ENV
          value: "production"
        - name: BRIDGE_ID
          valueFrom:
            fieldRef:
              fieldPath: metadata.name
        - name: DATABASE_URL
          valueFrom:
            secretKeyRef:
              name: auralink-secrets
              key: database-url
        - name: DB_PASSWORD
          valueFrom:
            secretKeyRef:
              name: auralink-secrets
              key: database-password
        - name: DASHBOARD_API_KEY
          valueFrom:
            secretKeyRef:
              name: auralink-secrets
              key: dashboard-api-key
        resources:
          requests:
            memory: "2Gi"
            cpu: "1000m"
          limits:
            memory: "4Gi"
            cpu: "2000m"
        livenessProbe:
          httpGet:
            path: /health
            port: 8080
          initialDelaySeconds: 60
          periodSeconds: 10
        readinessProbe:
          httpGet:
            path: /ready
            port: 8080
          initialDelaySeconds: 30
          periodSeconds: 5
```

```bash
# Deploy to Kubernetes
kubectl apply -f infrastructure/kubernetes/ingress-egress-deployment.yaml

# Check status
kubectl get pods -n auralink -l app=ingress-egress

# View logs
kubectl logs -n auralink -l app=ingress-egress -f
```

---

## API Endpoints

### Health Checks

#### GET /health
**Liveness check** - Returns healthy if application is running

**Response:**
```json
{
  "status": "healthy",
  "checks": {
    "application": true
  },
  "timestamp": 1697673600000
}
```

#### GET /ready
**Readiness check** - Validates all dependencies

**Response:**
```json
{
  "status": "ready",
  "checks": {
    "database": true,
    "redis": true,
    "dashboard_service": true,
    "ai_core": true,
    "webrtc_server": true
  },
  "timestamp": 1697673600000
}
```

#### GET /status
**Detailed status** - Comprehensive health information with metrics

**Response:**
```json
{
  "status": "ready",
  "checks": { "...": "..." },
  "timestamp": 1697673600000,
  "service": {
    "name": "ingress-egress",
    "version": "1.0.0",
    "environment": "production",
    "region": "us-west-2",
    "bridgeId": "bridge-prod-001"
  },
  "resources": {
    "memoryUsed": 1073741824,
    "memoryMax": 2147483648,
    "cpuProcessors": 4,
    "databasePoolStats": {
      "active_connections": 5,
      "idle_connections": 15
    },
    "redisPoolStats": {
      "active_connections": 2,
      "idle_connections": 8
    }
  },
  "dependencies": {
    "database": {
      "status": "healthy",
      "endpoint": "jdbc:postgresql://postgres:5432/auralink"
    }
  }
}
```

### Prometheus Metrics

#### GET /metrics
**Metrics export** - Prometheus-formatted metrics

**Key Metrics:**
- `auralink_bridge_status` - Bridge operational status
- `auralink_conference_count` - Active conferences
- `auralink_participant_count` - Total participants
- `auralink_database_pool_active` - Active DB connections
- `auralink_redis_pool_active` - Active Redis connections
- `auralink_aic_compression_ratio` - AIC compression efficiency (Phase 3)
- `auralink_sip_call_count` - Active SIP calls (Phase 4)
- `auralink_rtmp_stream_count` - Active RTMP streams (Phase 4)

---

## Database Schema

### Tables Created by Migration

#### bridges
Tracks bridge registration and status

```sql
CREATE TABLE ingress_egress.bridges (
    bridge_id VARCHAR(255) PRIMARY KEY,
    region VARCHAR(50) NOT NULL,
    status VARCHAR(20) NOT NULL,
    capacity INT DEFAULT 0,
    current_load INT DEFAULT 0,
    last_heartbeat TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

#### conferences
Tracks active conferences on each bridge

```sql
CREATE TABLE ingress_egress.conferences (
    conference_id VARCHAR(255) PRIMARY KEY,
    bridge_id VARCHAR(255) REFERENCES ingress_egress.bridges(bridge_id),
    room_name VARCHAR(255) NOT NULL,
    participant_count INT DEFAULT 0,
    status VARCHAR(20) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    ended_at TIMESTAMP
);
```

#### participants
Tracks participants in conferences

```sql
CREATE TABLE ingress_egress.participants (
    participant_id VARCHAR(255) PRIMARY KEY,
    conference_id VARCHAR(255) REFERENCES ingress_egress.conferences(conference_id),
    aura_id VARCHAR(255),
    display_name VARCHAR(255),
    join_source VARCHAR(50),
    joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    left_at TIMESTAMP
);
```

#### external_sessions
Tracks SIP, RTMP, and external WebRTC sessions

```sql
CREATE TABLE ingress_egress.external_sessions (
    session_id VARCHAR(255) PRIMARY KEY,
    session_type VARCHAR(50) NOT NULL,  -- 'sip', 'rtmp', 'external_webrtc'
    conference_id VARCHAR(255) REFERENCES ingress_egress.conferences(conference_id),
    external_id VARCHAR(255),
    status VARCHAR(20) NOT NULL,
    metadata JSONB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    ended_at TIMESTAMP
);
```

---

## Redis Key Structure

### Key Prefixes
All keys prefixed with: `auralink:ingress-egress:`

### Key Patterns

#### Bridge State
- `bridge:{bridge_id}:status` - Bridge operational status (HASH)
- `bridge:{bridge_id}:conferences` - Set of active conference IDs (SET)
- `bridge:{bridge_id}:participants` - Set of participant IDs (SET)

#### Conference State
- `conference:{conference_id}:info` - Conference metadata (HASH)
- `conference:{conference_id}:participants` - Participant list (SET)
- `conference:{conference_id}:media` - Media state (HASH)

#### Room Synchronization
- `room:{room_name}:bridges` - Bridges handling this room (SET)
- `room:{room_name}:state` - Room state from WebRTC Server (HASH)

#### Participant Cache
- `participant:{participant_id}:info` - Participant information (HASH)
- `auraid:{aura_id}:participant` - AuraID to participant mapping (STRING)

#### Metrics
- `metrics:conferences:count` - Total active conferences (STRING)
- `metrics:participants:count` - Total active participants (STRING)
- `metrics:sip:calls` - Active SIP calls (STRING)
- `metrics:rtmp:streams` - Active RTMP streams (STRING)

---

## Testing

### Unit Tests (In Progress)

```bash
# Run unit tests
mvn test

# Run with coverage
mvn test -Pcoverage

# View coverage report
open target/site/jacoco/index.html
```

### Integration Tests (Planned - Phase 6)

```bash
# Run integration tests
mvn verify -Pintegration-tests

# Test specific component
mvn test -Dtest=DatabaseManagerTest
mvn test -Dtest=RedisManagerTest
mvn test -Dtest=HealthCheckManagerTest
```

### Manual Testing

```bash
# Test health endpoints
curl -v http://localhost:8080/health
curl -v http://localhost:8080/ready
curl -v http://localhost:8080/status

# Test metrics
curl http://localhost:9090/metrics

# Test database connectivity
docker exec -it <container> psql -h postgres -U auralink -d auralink -c "SELECT * FROM ingress_egress.bridges;"

# Test Redis connectivity
docker exec -it <container> redis-cli -h redis PING
docker exec -it <container> redis-cli -h redis KEYS "auralink:ingress-egress:*"
```

---

## Troubleshooting

### Common Issues

#### Service Not Starting

**Symptom:** Container exits immediately or fails health checks

**Solutions:**
1. Check logs: `docker-compose logs ingress-egress`
2. Verify environment variables are set correctly
3. Ensure PostgreSQL and Redis are accessible
4. Check firewall/network policies

#### Database Connection Failures

**Symptom:** "Failed to initialize database connection pool"

**Solutions:**
1. Verify DATABASE_URL format: `jdbc:postgresql://host:port/database`
2. Check database credentials (DB_USER, DB_PASSWORD)
3. Ensure PostgreSQL is running and accessible
4. Test connection: `psql -h <host> -U <user> -d <database>`

#### Redis Connection Failures

**Symptom:** "Redis connection test failed"

**Solutions:**
1. Verify REDIS_HOST and REDIS_PORT
2. Check if Redis password is required (REDIS_PASSWORD)
3. Ensure Redis is running: `redis-cli -h <host> PING`
4. Check network connectivity

#### Readiness Check Failing

**Symptom:** `/ready` endpoint returns "not_ready"

**Solutions:**
1. Check `/status` endpoint for detailed dependency status
2. Verify all configured services are running:
   - Dashboard Service (if `config.health.dependencies.dashboard = true`)
   - AI Core (if `config.health.dependencies.aiCore = true`)
   - WebRTC Server (if `config.health.dependencies.webrtcServer = true`)
3. Increase `auralink.health.dependency_timeout` if checks are timing out

### Debug Mode

Enable detailed logging:

```bash
# Set environment variable
export LOG_LEVEL=DEBUG

# Or in docker-compose.yml
environment:
  - LOG_LEVEL=DEBUG
```

---

## Next Steps

### Phase 2: Service Integration Layer (Weeks 3-4)

**Priority Tasks:**
1. Implement REST API client to Dashboard Service
2. Create JWT authentication layer
3. Implement room synchronization with WebRTC Server
4. Set up Prometheus metrics export
5. Create Kubernetes deployment manifests

### Phase 3: AIC Protocol Integration (Weeks 5-8)

**Priority Tasks:**
1. Design RTP extension structure for AIC metadata
2. Implement gRPC client to AI Core
3. Create compression hint injection pipeline
4. Add fallback mechanisms for native codecs

### Phase 4: External System Bridges (Weeks 9-12)

**Priority Tasks:**
1. Implement SIP gateway integration
2. Create RTMP bridge for streaming platforms
3. Implement recording service with cloud storage
4. Add external WebRTC app connectors

---

## Contributing

### Code Style

- Follow Kotlin coding conventions
- Use ktlint for code formatting
- Document all public APIs
- Write unit tests for new components

### Pull Request Process

1. Create feature branch from `main`
2. Implement changes with tests
3. Run linting and tests: `mvn verify`
4. Submit PR with description of changes
5. Ensure CI pipeline passes

---

## Support

For issues, questions, or contributions:

- **Documentation:** See `/AuraLinkDocs/` directory
- **Implementation Plan:** See `/INGRESS_EGRESS_IMPLEMENTATION_PLAN.md`
- **Design Analysis:** Refer to design document provided

---

**Last Updated:** 2025-10-17  
**Version:** 1.0.0 (Phase 1 Complete)  
**Status:** Foundation layer implemented, ready for Phase 2

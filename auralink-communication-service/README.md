# AuraLink Communication Service

## Overview

The Communication Service is AuraLink's **universal identity layer** and **decentralized mesh network**, built on Matrix Synapse. It enables cross-app calling through the AuraID system (@username.aura), transforming AuraLink into the "TCP/IP of real-time calls."

## Architecture

```
Communication Service
├── Matrix Synapse Core       (Federated homeserver)
├── AuraID Module             (Universal identity management)
├── WebRTC Bridge             (Matrix ↔ LiveKit integration)
├── Mesh Routing Engine       (AI-optimized P2P routing)
├── Trust & Reputation System (Decentralized trust scoring)
└── Notification Hub          (Unified cross-app notifications)
```

## Features

### Phase 1: Infrastructure (Current)
- ✅ Docker containerization with multi-stage build
- ✅ PostgreSQL database with comprehensive schema
- ✅ Redis for caching and presence
- ✅ Docker Compose configuration
- ✅ Environment configuration templates

### Phase 2: AuraID Identity Layer (Planned)
- Universal @username.aura identities
- Multi-method verification (email, phone, document)
- Privacy controls (public, friends, private)
- Dashboard Service integration

### Phase 3: Cross-App Calling (Planned)
- Matrix-to-WebRTC bridge
- Custom Matrix call events
- Unified notification hub
- Multi-app ring prevention

### Phase 4: Mesh Network Routing (Planned)
- AI-optimized route selection
- Node discovery and advertisement
- P2P relay capabilities
- Fallback routing hierarchy

### Phase 5: Federation & Trust (Planned)
- Secure Matrix federation
- Trust score calculation
- Abuse prevention system
- Reputation visualization

## Quick Start

### Prerequisites

- Docker 20.10+
- Docker Compose 2.0+
- PostgreSQL 15+ (or use provided docker-compose)
- Redis 7+ (or use provided docker-compose)

### Development Setup

1. **Clone the repository**
   ```bash
   cd /Users/naveen/Desktop/AuraLink1
   ```

2. **Configure environment**
   ```bash
   cd auralink-communication-service
   cp .env.template .env
   # Edit .env with your configuration
   ```

3. **Start services**
   ```bash
   cd ../infrastructure/docker
   docker-compose -f docker-compose.communication.yml up -d
   ```

4. **Check service health**
   ```bash
   curl http://localhost:8008/health
   ```

### Database Migration

Run migrations manually:
```bash
psql -h localhost -p 5433 -U auralink -d auralink_comm \
  -f scripts/db/migrations/006_phase6_auraid_mesh_schema.sql

psql -h localhost -p 5433 -U auralink -d auralink_comm \
  -f scripts/db/migrations/008_communication_service_schema.sql
```

## Configuration

### Environment Variables

Key configuration options (see `.env.template`):

| Variable | Purpose | Default |
|----------|---------|---------|
| `SYNAPSE_SERVER_NAME` | Matrix homeserver domain | auralink.network |
| `MATRIX_REGISTRATION_SECRET` | Registration secret | (generate securely) |
| `COMM_POSTGRES_*` | Database configuration | See template |
| `COMM_REDIS_*` | Redis configuration | See template |
| `DASHBOARD_SERVICE_URL` | Dashboard integration | http://dashboard-service:8080 |
| `AI_CORE_URL` | AI Core integration | http://ai-core:8000 |
| `ENABLE_FEDERATION` | Enable Matrix federation | true |
| `ENABLE_MESH_ROUTING` | Enable mesh routing | true |

### Matrix Homeserver

The homeserver configuration is auto-generated from environment variables during container startup. Manual customization can be done by editing `/data/homeserver.yaml` inside the container.

## API Endpoints

### Matrix Standard Endpoints (Port 8008)

- `GET /_matrix/client/versions` - Client API versions
- `POST /_matrix/client/r0/register` - User registration
- `POST /_matrix/client/r0/login` - User login
- `GET /_matrix/federation/v1/version` - Federation version

### AuraLink Custom Endpoints (Phase 2+)

- `POST /internal/matrix/register` - Register Matrix user with AuraID
- `POST /internal/mesh/register_node` - Register mesh node
- `POST /internal/routing/query` - Query optimal route
- `GET /health` - Health check

### Metrics (Port 9001)

- `GET /metrics` - Prometheus metrics

## Database Schema

### Key Tables

| Table | Purpose |
|-------|---------|
| `aura_id_registry` | Universal AuraID registry |
| `aura_id_verifications` | Verification records |
| `matrix_user_mappings` | AuraID ↔ Matrix user mapping |
| `mesh_nodes` | Network node registry |
| `mesh_routes` | Cached routes with AI scores |
| `cross_app_calls` | Cross-app call tracking |
| `trust_scores` | Trust and reputation |
| `notification_queue` | Unified notifications |
| `federation_servers` | Federated homeservers |

See `scripts/db/migrations/008_communication_service_schema.sql` for complete schema.

## Development

### Module Structure

```
auralink-communication-service/
├── Dockerfile                    # Multi-stage container build
├── docker/
│   ├── start.py                 # Startup orchestration
│   └── conf/
│       ├── homeserver.yaml      # Matrix config template
│       └── log.config           # Logging configuration
├── auralink-modules/            # Custom Matrix modules
│   ├── auraid_module.py        # AuraID integration (Phase 2)
│   ├── webrtc_bridge.py        # WebRTC bridge (Phase 3)
│   └── mesh_routing.py         # Mesh routing (Phase 4)
└── .env.template               # Environment configuration
```

### Testing

Unit tests (Phase 2+):
```bash
pytest tests/unit/
```

Integration tests (Phase 2+):
```bash
pytest tests/integration/
```

## Deployment

### Docker Compose (Development)

```bash
docker-compose -f infrastructure/docker/docker-compose.communication.yml up -d
```

### Kubernetes (Production)

Manifests will be created in Phase 1 deployment task:
```bash
kubectl apply -f infrastructure/kubernetes/communication-service-deployment.yaml
```

## Monitoring

### Prometheus Metrics

Exported metrics include:
- Matrix Synapse built-in metrics
- Custom AuraLink metrics (Phase 2+):
  - `auraid_registrations_total`
  - `cross_app_calls_total`
  - `mesh_routes_active`
  - `trust_score_distribution`

### Grafana Dashboards

Dashboard templates will be created in deployment phase:
- AuraID Overview
- Cross-App Calling
- Mesh Network Health
- Federation Status

## Security

### Authentication

- Matrix: Standard Matrix access tokens
- Internal APIs: JWT tokens from Dashboard Service
- Federation: Server-to-server signatures

### Encryption

- TLS 1.3 for all external connections
- mTLS for service-to-service communication
- Matrix E2EE for end-to-end encryption
- Database encryption at rest

## Troubleshooting

### Common Issues

**Container fails to start:**
- Check database connectivity: `docker-compose logs postgres-comm`
- Verify environment variables in `.env`
- Check logs: `docker-compose logs communication-service`

**Database connection refused:**
- Ensure PostgreSQL is healthy: `docker-compose ps`
- Check port mapping: `5433:5432`
- Verify credentials in `.env`

**Health check failing:**
- Allow 60s startup time
- Check Matrix logs: `docker-compose logs communication-service`
- Verify port 8008 is accessible

## Roadmap

- ✅ **Phase 1**: Infrastructure setup (Complete)
- ⏳ **Phase 2**: AuraID implementation (Weeks 3-4)
- ⏳ **Phase 3**: Cross-app calling bridge (Weeks 5-7)
- ⏳ **Phase 4**: Mesh network routing (Weeks 8-10)
- ⏳ **Phase 5**: Federation & trust system (Weeks 11-13)

## Contributing

This service is part of the AuraLink monorepo. See main `README.md` for contribution guidelines.

## License

Proprietary - AuraLink Platform

## Support

For issues and questions, refer to:
- Main documentation: `/AuraLinkDocs/`
- Implementation guide: `/COMMUNICATION_SERVICE_INTEGRATION_GUIDE.md`
- Architecture analysis: `/BACKEND_CRITICAL_ANALYSIS.md`

# 🚀 AuraLink - Intelligent Real-Time Communication Platform

> **Enterprise-grade WebRTC platform with cutting-edge AI integration**

[![Monorepo](https://img.shields.io/badge/monorepo-yes-blue)](MONOREPO.md)
[![License](https://img.shields.io/badge/license-Proprietary-red)](LICENSE)
[![Services](https://img.shields.io/badge/services-5-green)](#architecture)

## 📋 Overview

AuraLink is a proprietary WebRTC platform that combines real-time communication with advanced AI capabilities. Built on proven open-source foundations (LiveKit, Matrix, Jitsi) with custom enhancements, AuraLink delivers intelligent, bandwidth-efficient communication experiences.

### 📦 Monorepo Structure

This repository uses a **monorepo architecture** to manage all microservices, shared libraries, and infrastructure in one place. See [MONOREPO.md](MONOREPO.md) for details.

**Key Benefits:**
- 🔄 Atomic cross-service changes
- 📦 Unified dependency management
- 🚀 Simplified deployment
- 🔧 Shared tooling and configuration

### Key Features

- **Intelligent WebRTC**: High-quality audio/video calls with AI-powered optimization
- **AI Integration**: Real-time agents, translation, transcription, and memory
- **AuraLink AIC Protocol**: Proprietary compression for 80% bandwidth reduction
- **Universal Identity (AuraID)**: Cross-app communication with @username.aura
- **Enterprise-Ready**: Comprehensive monitoring, security, and compliance

## 🏗️ Architecture

AuraLink uses a microservices architecture with 5 core services:

1. **WebRTC Server** (Go) - Media handling via LiveKit
2. **AI Core** (Python/FastAPI) - Intelligence layer
3. **Dashboard Service** (Go) - API gateway and management
4. **Ingress/Egress** (Go/Java) - External media via Jitsi
5. **Communication Service** (Python) - Cross-app calling via Matrix

## 🚦 Phase 1 Status: COMPLETED ✅

### Implemented Components

#### ✅ Database Infrastructure
- **Supabase PostgreSQL** with complete schema
- Core tables: `users`, `organizations`, `calls`, `call_participants`, `contacts`, `quality_issues`, `quality_alerts`
- Row Level Security (RLS) policies configured
- API keys and sessions management

#### ✅ AI Core Microservice (Python/FastAPI)
- Complete REST API structure
- Authentication middleware with JWT verification
- Endpoints for:
  - AI Agents (create, manage, chat)
  - Memory system (SuperMemory.ai-inspired)
  - Speech processing (TTS/STT)
  - Real-time translation (10+ languages)
- Health checks and metrics

#### ✅ Dashboard Service (Go)
- Full API gateway implementation
- Supabase authentication integration
- Endpoints for:
  - User authentication (signup, login, logout, refresh)
  - Room management
  - Call history
  - Contacts management
  - Organization management
- JWT middleware with role-based access control

#### ✅ Shared Libraries
- **Go Libraries**:
  - Error handling framework
  - Supabase auth client
  - Configuration management
- **Python Libraries**:
  - Error handling utilities
  - Auth helpers
  - Config loader

#### ✅ Infrastructure
- **Monitoring**: Prometheus + Grafana + Jaeger
  - Service metrics
  - Alert rules
  - Grafana dashboards
- **Kubernetes**: Complete deployment manifests
  - Deployments for all services
  - ConfigMaps and Secrets
  - Service definitions with health checks
- **Docker**: Multi-stage builds and docker-compose

#### ✅ Configuration
- Environment templates
- Shared YAML configurations
- Service-specific settings

## 🚀 Quick Start

### Prerequisites

- Docker & Docker Compose
- Go 1.24+
- Python 3.11+
- Supabase account (already configured)
- Kubernetes cluster (for production)

### Development Setup

```bash
# 1. Clone and setup
git clone <repository-url>
cd AuraLink1

# 2. Install dependencies
make setup

# 3. Configure environment
# Edit .env with your Supabase credentials
cp shared/configs/.env.template .env

# 4. Start development environment
make dev

# 5. Verify services
make health
```

### Services will be available at:

- **WebRTC Server**: http://localhost:7880
- **AI Core**: http://localhost:8000
- **Dashboard API**: http://localhost:8080
- **Prometheus**: http://localhost:9090
- **Grafana**: http://localhost:3000 (admin/admin)
- **Jaeger**: http://localhost:16686

### API Documentation

#### Authentication

```bash
# Sign up
curl -X POST http://localhost:8080/api/v1/auth/signup \
  -H "Content-Type: application/json" \
  -d '{"email": "user@example.com", "password": "secure_password"}'

# Login
curl -X POST http://localhost:8080/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "user@example.com", "password": "secure_password"}'
```

#### AI Agents

```bash
# Create AI agent
curl -X POST http://localhost:8000/api/v1/agents \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Assistant",
    "model": "gpt-4",
    "temperature": 0.7
  }'

# Chat with agent
curl -X POST http://localhost:8000/api/v1/agents/{agent_id}/chat \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"message": "Hello!"}'
```

## 📦 Project Structure

```
AuraLink1/
├── auralink-webrtc-server/        # LiveKit-based media server
├── auralink-ai-core/               # Python AI service
│   ├── app/
│   │   ├── api/                    # REST endpoints
│   │   └── core/                   # Core utilities
│   ├── main.py
│   └── requirements.txt
├── auralink-dashboard-service/     # Go API gateway
│   ├── cmd/server/                 # Main entry point
│   ├── internal/
│   │   ├── api/                    # HTTP handlers
│   │   ├── middleware/             # Auth & logging
│   │   └── config/                 # Configuration
│   └── go.mod
├── auralink-ingress-egress/        # Jitsi-based external media
├── auralink-communication-service/ # Matrix-based cross-app calling
├── shared/                         # Shared libraries
│   ├── configs/                    # Configuration files
│   └── libs/
│       ├── go/                     # Go shared code
│       └── python/                 # Python shared code
├── infrastructure/                 # Deployment configs
│   ├── kubernetes/                 # K8s manifests
│   ├── docker/                     # Docker configs
│   └── monitoring/                 # Prometheus/Grafana
└── AuraLinkDocs/                   # Documentation
```

## 🔧 Development

### Building Services

```bash
# Build all services
make build

# Build Docker images
make docker-build

# Run tests
make test
```

### Database Migrations

Database schema is managed via Supabase. Use the MCP tools for migrations:

```javascript
// Example: Add new table
mcp4_apply_migration({
  project_id: "mydyucwvdnjbhqigseis",
  name: "add_feature_table",
  query: "CREATE TABLE..."
})
```

## 🚢 Deployment

### Kubernetes

```bash
# Deploy to Kubernetes
make deploy

# Update secrets first
kubectl create secret generic auralink-secrets \
  --from-env-file=.env \
  -n auralink

# Check status
kubectl get pods -n auralink
```

### Docker Compose (Development)

```bash
# Start all services
docker-compose -f infrastructure/docker/docker-compose.yaml up -d

# View logs
make logs

# Stop services
make dev-stop
```

## 📊 Monitoring

### Metrics
- **Prometheus**: Scrapes metrics from all services
- **Grafana**: Visualization dashboards
- **Jaeger**: Distributed tracing

### Health Checks
```bash
# Check all services
make health

# Individual service health
curl http://localhost:8080/health
curl http://localhost:8000/health
```

## 🔐 Security

### Authentication
- **Supabase Auth**: JWT-based authentication
- **RLS Policies**: Row-level security on all tables
- **API Keys**: Scoped access tokens
- **Role-based Access**: User, moderator, admin roles

### Best Practices
- Never commit `.env` or secrets
- Use Kubernetes secrets in production
- Rotate API keys regularly
- Enable 2FA for admin accounts

## 🧪 Testing

```bash
# Run all tests
make test

# Python tests
cd auralink-ai-core && pytest

# Go tests
cd auralink-dashboard-service && go test ./...
```

## 📚 Documentation

- [BIGPLAN.md](AuraLinkDocs/BIGPLAN.md) - 7-Phase development roadmap
- [Auth.md](AuraLinkDocs/Auth.md) - Authentication flow
- [coreai.md](AuraLinkDocs/coreai.md) - AI capabilities
- [folder.md](AuraLinkDocs/folder.md) - Project structure

## 🛣️ Roadmap

- [x] **Phase 1**: Foundation & Core Infrastructure ✅
- [ ] **Phase 2**: Basic Call Management & File Sharing
- [ ] **Phase 3**: AuraLink AIC Protocol Development
- [ ] **Phase 4**: AI Core & Memory System
- [ ] **Phase 5**: MCP Integration & AI Agents
- [ ] **Phase 6**: AuraID & Mesh Network
- [ ] **Phase 7**: Enterprise Features & Finalization

## 🤝 Contributing

This is a proprietary platform. For internal development guidelines, see CONTRIBUTING.md.

## 📄 License

Proprietary - © 2025 AuraLinkRTC Inc. All rights reserved.

## 🆘 Support

For issues and questions:
- Internal Wiki: [Link]
- Slack: #auralink-dev
- Email: dev@auralink.com

---

**Built with ❤️ by the AuraLink team**

# AuraLinkRTC Project Folder Structure

## Overview

This document outlines the folder structure for the full AuraLinkRTC project, a proprietary WebRTC platform with AI integration. The architecture consists of 5 microservices implemented as separate Git repositories for scalability and independence.

## Root Directory: `/AuraLinkRTC/` (Workspace)

```bash
/AuraLinkRTC/ (workspace directory)
├── auralink-webrtc-server/       # Git repo: WebRTC  (Go)
├── auralink-ai-core/             # (Python/FastAPI)
├── auralink-dashboard-service/   #  API  (Go)
├── auralink-ingress-egress/      # Git repo: External media handling (Go)
├── auralink-communication-service/ # Git repo: Cross-app calling and messaging Matrix (Go)
├── shared/                       # Shared libraries and configurations
│   ├── libs/                     # Common utilities and utilities
│   ├── configs/                  # Shared configuration templates
│   └── protos/                   # Protocol buffer definitions
├── infrastructure/               # Deployment and operations (shared)
│   ├── kubernetes/               # K8s manifests and helm charts
│   ├── docker/                   # Dockerfiles and compose files
│   ├── monitoring/               # Prometheus, Grafana, Jaeger configs
│   ├── logging/                  # ELK stack configuration
│   └── ci-cd/                    # CI/CD pipelines and scripts
├── tests/                        # Testing infrastructure
│   ├── integration/              # End-to-end tests
│   ├── unit/                     # Unit tests for each service
│   └── load/                     # Performance and load testing
├── scripts/                      # Utility scripts
│   ├── build/                    # Build and deployment scripts
│   ├── db/                       # Database migration scripts
│   └── dev/                      # Development environment setup
├── .github/                      # GitHub workflows and templates (if applicable)
├── docker-compose.yml            # Local development environment
├── Makefile                      # Build automation
├── README.md                     # Project overview and setup
└── go.mod / requirements.txt      # Dependency management (if any shared)
```



## Original Repositories to Clone

For services that build on existing open-source projects, clone from these official repositories:

### WebRTC Server Base
- **LiveKit Server**: `https://github.com/livekit/livekit` - Core WebRTC SFU and media server

### Dashboard Service Base  
- **Matrix Synapse**: `https://github.com/matrix-org/synapse` - Federation and identity server for decentralized communication

### Ingress/Egress Base
- **Jitsi Videobridge**: `https://github.com/jitsi/jvb` - Backend media routing for video calls
- **Jitsi Conference Focus**: `https://github.com/jitsi/jicofo` - Conference management and signaling

### Communication Service Base
- **Matrix Synapse**: `https://github.com/matrix-org/synapse` - Used for AuraID and cross-app messaging federation

Clone these repositories to customize and integrate into your microservices as needed.

This clean micro-repo structure supports your 7-phase development plan with 5 independent microservices and shared infrastructure components.

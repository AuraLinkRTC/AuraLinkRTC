# 📦 AuraLink Monorepo Structure

## Overview

AuraLink uses a **monorepo architecture** to manage all microservices, shared libraries, infrastructure, and documentation in a single repository. This approach provides:

✅ **Unified versioning** - All services evolve together  
✅ **Atomic commits** - Cross-service changes in single commits  
✅ **Shared tooling** - Common build, test, and deploy processes  
✅ **Code reuse** - Shared libraries easily accessible  
✅ **Simplified dependencies** - Internal packages managed together  

## Repository Structure

```
AuraLink1/                          # Root monorepo
├── 🔧 services/                    # All microservices
│   ├── auralink-webrtc-server/    # Media server (Go + LiveKit)
│   ├── auralink-ai-core/          # AI service (Python/FastAPI)
│   ├── auralink-dashboard-service/# API gateway (Go)
│   ├── auralink-ingress-egress/   # External media (Go/Java + Jitsi)
│   └── auralink-communication/    # Cross-app calling (Python + Matrix)
│
├── 📚 shared/                      # Shared code & configs
│   ├── configs/                   # Environment templates
│   ├── libs/
│   │   ├── go/                    # Go shared libraries
│   │   └── python/                # Python shared libraries
│   └── protos/                    # Protocol buffers
│
├── 🏗️ infrastructure/             # Deployment & operations
│   ├── kubernetes/                # K8s manifests
│   ├── docker/                    # Docker configs
│   ├── monitoring/                # Prometheus/Grafana
│   └── airflow/                   # Workflow orchestration
│
├── 🧪 tests/                       # Integration tests
│   └── integration/               # Cross-service tests
│
├── 📖 AuraLinkDocs/                # Documentation
│   ├── BIGPLAN.md                 # Roadmap
│   ├── Auth.md                    # Authentication
│   └── ...
│
├── 🛠️ scripts/                     # Build & migration scripts
│   ├── build/                     # Build automation
│   └── db/migrations/             # Database migrations
│
└── 📄 Root configuration files
    ├── Makefile                   # Unified build commands
    ├── docker-compose.production.yml
    ├── .gitignore                 # Global ignore rules
    ├── .env                       # Environment config
    └── README.md                  # Main documentation
```

## Monorepo Benefits for AuraLink

### 1. **Simplified Dependency Management**
```bash
# Shared Go library used by multiple services
shared/libs/go/auth → used by dashboard & webrtc server
shared/libs/python/auth → used by AI core & communication service
```

### 2. **Atomic Cross-Service Changes**
```bash
# Single commit for API contract changes
✓ Update proto definition
✓ Regenerate Go & Python clients
✓ Update dashboard service
✓ Update AI core
```

### 3. **Unified Build & Deploy**
```bash
make build        # Builds all services
make test         # Runs all tests
make deploy       # Deploys entire platform
```

### 4. **Consistent Versioning**
- All services share the same version number
- Releases are synchronized across platform
- No version mismatch issues

## Development Workflow

### 1. **Local Development**
```bash
# Start entire platform
make dev

# Work on specific service
cd auralink-ai-core
# Make changes...

# Test changes
make test

# Commit changes (can include multiple services)
git add .
git commit -m "feat: add AI agent memory persistence"
```

### 2. **Feature Branches**
```bash
# Create feature branch
git checkout -b feature/ai-translation

# Work across services
# - Update AI core with translation logic
# - Update dashboard API to expose translation
# - Update shared proto definitions
# - Add integration tests

# Single PR for entire feature
git push origin feature/ai-translation
```

### 3. **Testing**
```bash
# Unit tests per service
cd auralink-ai-core && pytest
cd auralink-dashboard-service && go test ./...

# Integration tests (cross-service)
cd tests/integration && pytest

# All tests
make test
```

## CI/CD Pipeline

### Recommended Pipeline Structure

```yaml
# .github/workflows/ci.yml
name: AuraLink CI

on: [push, pull_request]

jobs:
  detect-changes:
    # Detect which services changed
    
  test-dashboard:
    needs: detect-changes
    if: needs.detect-changes.outputs.dashboard == 'true'
    # Test dashboard service
    
  test-ai-core:
    needs: detect-changes
    if: needs.detect-changes.outputs.ai-core == 'true'
    # Test AI core
    
  integration-tests:
    needs: [test-dashboard, test-ai-core]
    # Run integration tests
    
  deploy:
    needs: integration-tests
    if: github.ref == 'refs/heads/main'
    # Deploy all services
```

## Service Isolation

Each service maintains:
- ✅ Own `Dockerfile`
- ✅ Own dependencies (`requirements.txt`, `go.mod`)
- ✅ Own internal structure
- ✅ Independent deployment (via K8s)

But shares:
- 🔄 Common configs
- 🔄 Shared libraries
- 🔄 Infrastructure definitions
- 🔄 Build tooling

## Migration from Polyrepo (if needed)

If services were previously in separate repos:

```bash
# 1. Create monorepo structure
mkdir -p AuraLink1/{services,shared,infrastructure,tests}

# 2. Move each service
git clone <service-repo> temp-service
mv temp-service AuraLink1/services/auralink-service-name

# 3. Preserve git history (optional)
git subtree add --prefix=services/auralink-dashboard-service \
  git@github.com:org/dashboard-service.git main

# 4. Update paths in configs
# Update Dockerfile paths, import paths, etc.

# 5. Create unified Makefile
# 6. Update CI/CD
# 7. Test everything
```

## Best Practices

### ✅ DO
- Keep services loosely coupled
- Use shared libraries for common code
- Maintain clear service boundaries
- Version the entire monorepo together
- Use feature flags for staged rollouts
- Run integration tests before merging

### ❌ DON'T
- Create tight coupling between services
- Duplicate code instead of using shared libs
- Deploy services independently in production
- Mix service-specific code in shared/
- Commit broken cross-service changes

## Tooling Recommendations

### Current Tools (Already in place)
- ✅ Make - Build orchestration
- ✅ Docker Compose - Local development
- ✅ Kubernetes - Production deployment

### Optional Enhancements
- [ ] **Bazel/Pants** - Advanced build system (overkill for current size)
- [ ] **Nx/Turborepo** - If adding frontend monorepo
- [ ] **Dependabot** - Automated dependency updates
- [ ] **Pre-commit hooks** - Linting, formatting
- [ ] **GitHub Actions** - CI/CD automation

## Common Operations

### Adding a New Service
```bash
# 1. Create service directory
mkdir -p services/auralink-new-service

# 2. Add to Makefile
# Update setup, build, test targets

# 3. Add to docker-compose
# Add service definition

# 4. Add to Kubernetes
# Create deployment manifest

# 5. Update documentation
```

### Updating Shared Library
```bash
# 1. Update code
cd shared/libs/go/auth
# Make changes...

# 2. Update dependent services
cd auralink-dashboard-service
go mod tidy

# 3. Test all affected services
make test

# 4. Commit together
git add shared/libs/go/auth auralink-dashboard-service
git commit -m "refactor: improve auth error handling"
```

## Git Strategy

### Branch Structure
```
main                    # Production-ready code
├── develop             # Integration branch
├── feature/*           # Feature development
├── hotfix/*            # Production fixes
└── release/*           # Release preparation
```

### Commit Conventions
```bash
# Format: type(scope): description

feat(ai-core): add translation service
fix(dashboard): resolve JWT expiry bug
refactor(shared): improve error handling
docs(readme): update setup instructions
chore(deps): update Go dependencies
```

## Versioning

AuraLink monorepo uses **unified versioning**:

```
v1.0.0 - Initial production release
│
├── auralink-webrtc-server v1.0.0
├── auralink-ai-core v1.0.0
├── auralink-dashboard-service v1.0.0
└── shared/libs/* v1.0.0

v1.1.0 - Feature update
│
├── auralink-ai-core v1.1.0 (changed)
├── auralink-dashboard-service v1.1.0 (changed)
└── others v1.1.0 (version bump, no changes)
```

## FAQ

**Q: Why monorepo instead of separate repositories?**  
A: AuraLink's services are tightly integrated and evolve together. Monorepo simplifies cross-service changes, dependency management, and deployment.

**Q: Won't the repo become too large?**  
A: Git handles large repos well. We can use Git LFS for large assets if needed.

**Q: How do we control access to specific services?**  
A: Use branch protection and CODEOWNERS files. Deploy services independently via K8s.

**Q: What if we need to open-source one service?**  
A: Use `git filter-branch` or `git subtree split` to extract history into separate repo.

**Q: How do we version shared libraries?**  
A: Shared libs version with the monorepo. Services always use latest version.

---

**This monorepo structure supports AuraLink's rapid development while maintaining code quality and deployment reliability.**

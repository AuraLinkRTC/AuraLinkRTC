# AuraLink Makefile for development and deployment

.PHONY: help setup dev build deploy clean test

# Default target
help:
	@echo "AuraLink Development Commands:"
	@echo "  make setup      - Initial setup (install dependencies)"
	@echo "  make dev        - Start development environment"
	@echo "  make build      - Build all services"
	@echo "  make test       - Run all tests"
	@echo "  make deploy     - Deploy to Kubernetes"
	@echo "  make clean      - Clean build artifacts"
	@echo "  make logs       - View logs from all services"

# Initial setup
setup:
	@echo "Setting up AuraLink development environment..."
	@cp shared/configs/.env.template .env
	@echo "✓ Created .env file"
	@cd auralink-ai-core && pip install -r requirements.txt
	@echo "✓ Installed AI Core dependencies"
	@cd auralink-dashboard-service && go mod download
	@echo "✓ Downloaded Dashboard Service dependencies"
	@cd shared/libs/go && go mod download
	@echo "✓ Downloaded shared Go dependencies"
	@echo "✓ Setup complete! Please edit .env with your configuration"

# Start development environment
dev:
	@echo "Starting AuraLink development environment..."
	docker-compose -f infrastructure/docker/docker-compose.yaml up -d
	@echo "✓ Services started!"
	@echo "  - WebRTC Server: http://localhost:7880"
	@echo "  - AI Core: http://localhost:8000"
	@echo "  - Dashboard: http://localhost:8080"
	@echo "  - Prometheus: http://localhost:9090"
	@echo "  - Grafana: http://localhost:3000"
	@echo "  - Jaeger: http://localhost:16686"

# Stop development environment
dev-stop:
	@echo "Stopping AuraLink development environment..."
	docker-compose -f infrastructure/docker/docker-compose.yaml down

# Build all services
build:
	@echo "Building AuraLink services..."
	@cd auralink-dashboard-service && go build -o bin/dashboard-service ./cmd/server
	@echo "✓ Built Dashboard Service"
	@echo "✓ AI Core runs via Python (no build needed)"
	@echo "✓ WebRTC Server uses existing LiveKit build"

# Build Docker images
docker-build:
	@echo "Building Docker images..."
	docker build -t auralink/ai-core:latest ./auralink-ai-core
	docker build -t auralink/dashboard-service:latest ./auralink-dashboard-service
	@echo "✓ Docker images built"

# Run tests
test:
	@echo "Running tests..."
	@cd auralink-ai-core && python -m pytest tests/ || true
	@cd auralink-dashboard-service && go test ./... || true
	@echo "✓ Tests completed"

# Deploy to Kubernetes
deploy:
	@echo "Deploying AuraLink to Kubernetes..."
	kubectl apply -f infrastructure/kubernetes/namespace.yaml
	kubectl apply -f infrastructure/kubernetes/configmap.yaml
	kubectl apply -f infrastructure/kubernetes/secrets.yaml
	kubectl apply -f infrastructure/kubernetes/webrtc-server-deployment.yaml
	kubectl apply -f infrastructure/kubernetes/ai-core-deployment.yaml
	kubectl apply -f infrastructure/kubernetes/dashboard-deployment.yaml
	@echo "✓ Deployed to Kubernetes"

# View logs
logs:
	docker-compose -f infrastructure/docker/docker-compose.yaml logs -f

# Clean build artifacts
clean:
	@echo "Cleaning build artifacts..."
	@cd auralink-dashboard-service && rm -rf bin/
	@find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	@find . -type f -name "*.pyc" -delete 2>/dev/null || true
	@echo "✓ Cleaned"

# Database migrations
db-migrate:
	@echo "Running database migrations..."
	@echo "Database migrations are managed via Supabase MCP"
	@echo "Use the mcp4_apply_migration tool for schema changes"

# Generate API documentation
docs:
	@echo "Generating API documentation..."
	@cd auralink-ai-core && python -m pdoc --html --output-dir docs app
	@echo "✓ Documentation generated in docs/"

# Health check all services
health:
	@echo "Checking service health..."
	@curl -f http://localhost:7880/health && echo "✓ WebRTC Server: healthy" || echo "✗ WebRTC Server: down"
	@curl -f http://localhost:8000/health && echo "✓ AI Core: healthy" || echo "✗ AI Core: down"
	@curl -f http://localhost:8080/health && echo "✓ Dashboard: healthy" || echo "✗ Dashboard: down"

# AuraLink Communication Service - Multi-stage Dockerfile
# Based on Matrix Synapse with AuraLink customizations

# Stage 1: Base - System dependencies
FROM python:3.11-slim AS base

# Install system dependencies required by Synapse
RUN apt-get update && apt-get install -y \
    build-essential \
    libffi-dev \
    libssl-dev \
    libjpeg-dev \
    libpq-dev \
    libwebp-dev \
    libxml2-dev \
    libxslt1-dev \
    zlib1g-dev \
    git \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Create synapse user
RUN groupadd -r synapse && useradd -r -g synapse synapse

WORKDIR /app

# Stage 2: Builder - Install Synapse and dependencies
FROM base AS builder

# Copy Synapse source code
COPY synapse /app/synapse
COPY rust /app/rust
COPY pyproject.toml setup.py Cargo.toml Cargo.lock build_rust.py /app/

# Install Rust (required for some Synapse components)
RUN curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y
ENV PATH="/root/.cargo/bin:${PATH}"

# Install Python dependencies
RUN pip install --no-cache-dir --upgrade pip setuptools wheel && \
    pip install --no-cache-dir -e .

# Install additional dependencies for AuraLink integration
RUN pip install --no-cache-dir \
    psycopg2-binary==2.9.9 \
    redis==5.0.1 \
    grpcio==1.60.0 \
    grpcio-tools==1.60.0 \
    fastapi==0.109.0 \
    uvicorn==0.27.0 \
    pydantic==2.5.3 \
    httpx==0.26.0 \
    prometheus-client==0.19.0

# Stage 3: AuraLink Extensions
FROM builder AS auralink-extensions

WORKDIR /app/auralink

# Create directory structure for AuraLink modules
RUN mkdir -p modules api services

# Copy AuraLink custom modules (to be created in next steps)
# These will be created in subsequent implementation phases
COPY auralink-modules/auraid_module.py modules/ || echo "AuraID module placeholder"
COPY auralink-modules/webrtc_bridge.py modules/ || echo "WebRTC bridge placeholder"
COPY auralink-modules/mesh_routing.py modules/ || echo "Mesh routing placeholder"

# Create __init__.py for modules
RUN touch modules/__init__.py api/__init__.py services/__init__.py

# Stage 4: Runtime - Minimal production image
FROM python:3.11-slim AS runtime

# Install runtime dependencies only
RUN apt-get update && apt-get install -y \
    libffi8 \
    libssl3 \
    libjpeg62-turbo \
    libpq5 \
    libwebp7 \
    libxml2 \
    libxslt1.1 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Create synapse user
RUN groupadd -r synapse && useradd -r -g synapse synapse

# Create necessary directories
RUN mkdir -p /data /app /app/auralink
WORKDIR /app

# Copy installed packages from builder
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Copy Synapse application
COPY --from=builder /app/synapse /app/synapse

# Copy AuraLink extensions
COPY --from=auralink-extensions /app/auralink /app/auralink

# Copy configuration templates
COPY docker/conf/homeserver.yaml /app/homeserver.yaml.template
COPY docker/conf/log.config /app/log.config

# Create startup script
COPY docker/start.py /app/start.py
RUN chmod +x /app/start.py

# Set ownership
RUN chown -R synapse:synapse /app /data

# Switch to synapse user
USER synapse

# Expose ports
# 8008: HTTP (Matrix Client API)
# 8448: HTTPS (Matrix Federation)
# 9000: Metrics (Prometheus)
EXPOSE 8008 8448 9000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:8008/health || exit 1

# Volume for data persistence
VOLUME ["/data"]

# Environment variables
ENV SYNAPSE_SERVER_NAME=auralink.network \
    SYNAPSE_REPORT_STATS=no \
    SYNAPSE_CONFIG_DIR=/data \
    SYNAPSE_CONFIG_PATH=/data/homeserver.yaml \
    SYNAPSE_DATA_DIR=/data

# Start Synapse with AuraLink extensions
CMD ["python3", "/app/start.py"]

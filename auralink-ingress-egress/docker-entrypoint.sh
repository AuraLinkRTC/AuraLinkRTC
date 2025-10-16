#!/bin/bash
set -e

# AuraLink Ingress-Egress Service Entrypoint Script

# Function to log messages
log() {
    echo "[$(date +'%Y-%m-%d %H:%M:%S')] $*"
}

# Function to wait for service
wait_for_service() {
    local host=$1
    local port=$2
    local service_name=$3
    local max_attempts=30
    local attempt=0

    log "Waiting for $service_name at $host:$port..."
    
    while [ $attempt -lt $max_attempts ]; do
        if nc -z "$host" "$port" 2>/dev/null; then
            log "$service_name is available"
            return 0
        fi
        
        attempt=$((attempt + 1))
        log "Waiting for $service_name... (attempt $attempt/$max_attempts)"
        sleep 2
    done
    
    log "WARNING: $service_name not available after $max_attempts attempts"
    return 1
}

# Parse database URL to extract host and port
parse_db_url() {
    if [ -n "$DATABASE_URL" ]; then
        # Extract host and port from JDBC URL
        # Format: jdbc:postgresql://host:port/database
        DB_HOST=$(echo "$DATABASE_URL" | sed -n 's/.*:\/\/\([^:]*\):.*/\1/p')
        DB_PORT=$(echo "$DATABASE_URL" | sed -n 's/.*:\([0-9]*\)\/.*/\1/p')
        export DB_HOST
        export DB_PORT
    else
        DB_HOST="${DB_HOST:-postgres}"
        DB_PORT="${DB_PORT:-5432}"
    fi
}

# Wait for required services
wait_for_dependencies() {
    log "Checking service dependencies..."
    
    # Parse database connection
    parse_db_url
    
    # Wait for PostgreSQL
    if [ -n "$DB_HOST" ] && [ -n "$DB_PORT" ]; then
        wait_for_service "$DB_HOST" "$DB_PORT" "PostgreSQL" || true
    fi
    
    # Wait for Redis
    REDIS_HOST="${REDIS_HOST:-redis}"
    REDIS_PORT="${REDIS_PORT:-6379}"
    wait_for_service "$REDIS_HOST" "$REDIS_PORT" "Redis" || true
    
    log "Dependency check complete"
}

# Generate bridge ID if not provided
generate_bridge_id() {
    if [ -z "$BRIDGE_ID" ]; then
        BRIDGE_ID="bridge-$(hostname)-$(date +%s)"
        export BRIDGE_ID
        log "Generated bridge ID: $BRIDGE_ID"
    else
        log "Using provided bridge ID: $BRIDGE_ID"
    fi
}

# Display configuration
display_config() {
    log "=== AuraLink Ingress-Egress Service Configuration ==="
    log "Environment: ${AURALINK_ENV:-production}"
    log "Region: ${AURALINK_REGION:-us-west-2}"
    log "Bridge ID: $BRIDGE_ID"
    log "Log Level: ${LOG_LEVEL:-INFO}"
    log ""
    log "Feature Flags:"
    log "  AIC Protocol: ${ENABLE_AIC:-true}"
    log "  SIP Gateway: ${ENABLE_SIP:-true}"
    log "  RTMP Streaming: ${ENABLE_RTMP:-true}"
    log "  Recording: ${ENABLE_RECORDING:-true}"
    log "  Mesh Routing: ${ENABLE_MESH:-false}"
    log "  AuraID: ${ENABLE_AURAID:-true}"
    log ""
    log "Service Endpoints:"
    log "  Dashboard: ${DASHBOARD_SERVICE_URL:-http://auralink-dashboard:8080}"
    log "  AI Core: ${AI_CORE_GRPC_URL:-auralink-ai-core:50051}"
    log "  WebRTC Server: ${WEBRTC_SERVER_URL:-http://auralink-webrtc:7880}"
    log "====================================================="
}

# Start the service
start_service() {
    log "Starting AuraLink Ingress-Egress Service..."
    
    # Build Java command
    JAVA_CMD="java $JAVA_OPTS \
        -Djava.util.logging.config.file=/etc/auralink/config/logging.properties \
        -Dconfig.file=$CONFIG_FILE \
        -jar /app/jvb.jar \
        --apis=rest"
    
    log "Executing: $JAVA_CMD"
    exec $JAVA_CMD
}

# Main execution
main() {
    case "$1" in
        start)
            wait_for_dependencies
            generate_bridge_id
            display_config
            start_service
            ;;
        bash|sh)
            exec /bin/bash
            ;;
        *)
            log "Usage: $0 {start|bash}"
            log "Running command: $*"
            exec "$@"
            ;;
    esac
}

# Execute main function
main "$@"

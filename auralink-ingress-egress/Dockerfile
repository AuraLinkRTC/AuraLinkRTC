# AuraLink Ingress-Egress Service Dockerfile
# Multi-stage build for optimized image size

# Stage 1: Build stage
FROM maven:3.9-eclipse-temurin-17 AS builder

WORKDIR /build

# Copy pom files first for better caching
COPY pom.xml .
COPY rtp/pom.xml rtp/
COPY jitsi-media-transform/pom.xml jitsi-media-transform/
COPY jvb/pom.xml jvb/

# Download dependencies
RUN mvn dependency:go-offline -B

# Copy source code
COPY rtp/ rtp/
COPY jitsi-media-transform/ jitsi-media-transform/
COPY jvb/ jvb/
COPY auralink-integration/ auralink-integration/

# Build the application
RUN mvn clean package -DskipTests -B

# Stage 2: Runtime stage
FROM eclipse-temurin:17-jre-alpine

# Install required packages
RUN apk add --no-cache \
    bash \
    curl \
    tzdata \
    && rm -rf /var/cache/apk/*

# Create application user
RUN addgroup -S auralink && adduser -S auralink -G auralink

# Set working directory
WORKDIR /app

# Copy built artifacts from builder stage
COPY --from=builder /build/jvb/target/jvb-*.jar /app/jvb.jar
COPY --from=builder /build/auralink-integration/target/auralink-integration-*.jar /app/auralink-integration.jar

# Copy configuration files
COPY --chown=auralink:auralink auralink-integration/auralink.conf /etc/auralink/auralink.conf
COPY --chown=auralink:auralink config/ /etc/auralink/config/

# Create log directory
RUN mkdir -p /var/log/auralink && chown -R auralink:auralink /var/log/auralink

# Create data directory for temporary files
RUN mkdir -p /var/lib/auralink && chown -R auralink:auralink /var/lib/auralink

# Switch to application user
USER auralink

# Expose ports
# 8080: HTTP API and health checks
# 9090: Prometheus metrics
# 10000: RTP/UDP for media
EXPOSE 8080 9090 10000/udp

# Environment variables with defaults
ENV JAVA_OPTS="-Xms512m -Xmx2048m -XX:+UseG1GC -XX:+UseStringDeduplication" \
    AURALINK_ENV="production" \
    LOG_LEVEL="INFO" \
    CONFIG_FILE="/etc/auralink/auralink.conf"

# Health check
HEALTHCHECK --interval=30s --timeout=5s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:8080/health || exit 1

# Launch script
COPY --chown=auralink:auralink docker-entrypoint.sh /app/
RUN chmod +x /app/docker-entrypoint.sh

ENTRYPOINT ["/app/docker-entrypoint.sh"]
CMD ["start"]

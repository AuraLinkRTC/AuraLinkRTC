package org.jitsi.auralink.integration.metrics

import io.prometheus.client.*
import io.prometheus.client.exporter.HTTPServer
import io.prometheus.client.hotspot.DefaultExports
import org.jitsi.auralink.integration.config.AuraLinkConfig
import org.slf4j.LoggerFactory
import java.io.IOException

/**
 * Prometheus metrics exporter for AuraLink Ingress-Egress Service
 * Exposes custom metrics and standard JVM metrics
 */
class PrometheusMetricsExporter(private val config: AuraLinkConfig) {
    
    private val logger = LoggerFactory.getLogger(PrometheusMetricsExporter::class.java)
    private var httpServer: HTTPServer? = null
    
    // Bridge metrics
    val bridgeStatus = Gauge.build()
        .name("auralink_ingress_egress_bridge_status")
        .help("Bridge operational status (1=online, 0=offline)")
        .labelNames("bridge_id", "region", "environment")
        .register()
    
    val bridgeLoad = Gauge.build()
        .name("auralink_ingress_egress_bridge_load")
        .help("Current bridge load (percentage)")
        .labelNames("bridge_id")
        .register()
    
    val bridgeCapacity = Gauge.build()
        .name("auralink_ingress_egress_bridge_capacity")
        .help("Maximum bridge capacity (participants)")
        .labelNames("bridge_id")
        .register()
    
    // Conference metrics
    val activeConferences = Gauge.build()
        .name("auralink_ingress_egress_active_conferences")
        .help("Number of active conferences")
        .labelNames("bridge_id")
        .register()
    
    val conferenceDuration = Summary.build()
        .name("auralink_ingress_egress_conference_duration_seconds")
        .help("Conference duration in seconds")
        .labelNames("bridge_id", "room_name")
        .register()
    
    val conferencesCreated = Counter.build()
        .name("auralink_ingress_egress_conferences_created_total")
        .help("Total number of conferences created")
        .labelNames("bridge_id")
        .register()
    
    val conferencesEnded = Counter.build()
        .name("auralink_ingress_egress_conferences_ended_total")
        .help("Total number of conferences ended")
        .labelNames("bridge_id")
        .register()
    
    // Participant metrics
    val activeParticipants = Gauge.build()
        .name("auralink_ingress_egress_active_participants")
        .help("Number of active participants")
        .labelNames("bridge_id")
        .register()
    
    val participantsJoined = Counter.build()
        .name("auralink_ingress_egress_participants_joined_total")
        .help("Total number of participants joined")
        .labelNames("bridge_id", "join_source")
        .register()
    
    val participantsLeft = Counter.build()
        .name("auralink_ingress_egress_participants_left_total")
        .help("Total number of participants left")
        .labelNames("bridge_id")
        .register()
    
    val participantDuration = Summary.build()
        .name("auralink_ingress_egress_participant_duration_seconds")
        .help("Participant session duration in seconds")
        .labelNames("bridge_id")
        .register()
    
    // Media quality metrics
    val packetLoss = Gauge.build()
        .name("auralink_ingress_egress_packet_loss_percentage")
        .help("Packet loss percentage")
        .labelNames("bridge_id", "conference_id")
        .register()
    
    val jitter = Gauge.build()
        .name("auralink_ingress_egress_jitter_milliseconds")
        .help("Jitter in milliseconds")
        .labelNames("bridge_id", "conference_id")
        .register()
    
    val rtt = Gauge.build()
        .name("auralink_ingress_egress_rtt_milliseconds")
        .help("Round-trip time in milliseconds")
        .labelNames("bridge_id", "conference_id")
        .register()
    
    val bandwidth = Gauge.build()
        .name("auralink_ingress_egress_bandwidth_kbps")
        .help("Bandwidth usage in kbps")
        .labelNames("bridge_id", "conference_id", "direction")
        .register()
    
    // AIC Protocol metrics (Phase 3)
    val aicCompressionRatio = Gauge.build()
        .name("auralink_ingress_egress_aic_compression_ratio")
        .help("AIC compression ratio (0-1, higher is better)")
        .labelNames("bridge_id", "conference_id")
        .register()
    
    val aicLatency = Histogram.build()
        .name("auralink_ingress_egress_aic_latency_milliseconds")
        .help("AIC processing latency in milliseconds")
        .buckets(1.0, 2.0, 5.0, 10.0, 20.0, 50.0, 100.0)
        .labelNames("bridge_id")
        .register()
    
    val aicErrors = Counter.build()
        .name("auralink_ingress_egress_aic_errors_total")
        .help("Total AIC processing errors")
        .labelNames("bridge_id", "error_type")
        .register()
    
    // External bridge metrics (Phase 4)
    val sipCalls = Gauge.build()
        .name("auralink_ingress_egress_sip_calls_active")
        .help("Number of active SIP calls")
        .labelNames("bridge_id")
        .register()
    
    val sipCallsTotal = Counter.build()
        .name("auralink_ingress_egress_sip_calls_total")
        .help("Total SIP calls initiated")
        .labelNames("bridge_id", "status")
        .register()
    
    val rtmpStreams = Gauge.build()
        .name("auralink_ingress_egress_rtmp_streams_active")
        .help("Number of active RTMP streams")
        .labelNames("bridge_id", "destination")
        .register()
    
    val rtmpStreamsTotal = Counter.build()
        .name("auralink_ingress_egress_rtmp_streams_total")
        .help("Total RTMP streams started")
        .labelNames("bridge_id", "destination", "status")
        .register()
    
    val recordings = Gauge.build()
        .name("auralink_ingress_egress_recordings_active")
        .help("Number of active recordings")
        .labelNames("bridge_id")
        .register()
    
    val recordingsTotal = Counter.build()
        .name("auralink_ingress_egress_recordings_total")
        .help("Total recordings started")
        .labelNames("bridge_id", "status")
        .register()
    
    // Database metrics
    val databasePoolActive = Gauge.build()
        .name("auralink_ingress_egress_database_pool_active")
        .help("Active database connections")
        .register()
    
    val databasePoolIdle = Gauge.build()
        .name("auralink_ingress_egress_database_pool_idle")
        .help("Idle database connections")
        .register()
    
    val databasePoolWaiters = Gauge.build()
        .name("auralink_ingress_egress_database_pool_waiters")
        .help("Threads waiting for database connections")
        .register()
    
    // Redis metrics
    val redisPoolActive = Gauge.build()
        .name("auralink_ingress_egress_redis_pool_active")
        .help("Active Redis connections")
        .register()
    
    val redisPoolIdle = Gauge.build()
        .name("auralink_ingress_egress_redis_pool_idle")
        .help("Idle Redis connections")
        .register()
    
    // Dashboard Service integration metrics
    val dashboardRequests = Counter.build()
        .name("auralink_ingress_egress_dashboard_requests_total")
        .help("Total requests to Dashboard Service")
        .labelNames("endpoint", "status")
        .register()
    
    val dashboardLatency = Histogram.build()
        .name("auralink_ingress_egress_dashboard_latency_milliseconds")
        .help("Dashboard Service request latency")
        .buckets(10.0, 25.0, 50.0, 100.0, 250.0, 500.0, 1000.0)
        .labelNames("endpoint")
        .register()
    
    val heartbeatsSent = Counter.build()
        .name("auralink_ingress_egress_heartbeats_sent_total")
        .help("Total heartbeats sent to Dashboard")
        .labelNames("bridge_id", "status")
        .register()
    
    /**
     * Initialize metrics exporter
     */
    fun initialize() {
        if (!config.metrics.enabled) {
            logger.info("Metrics export disabled")
            return
        }
        
        try {
            logger.info("Starting Prometheus metrics exporter on port ${config.metrics.prometheusPort}")
            
            // Register default JVM metrics
            DefaultExports.initialize()
            
            // Start HTTP server
            httpServer = HTTPServer(config.metrics.prometheusPort)
            
            // Initialize bridge status
            bridgeStatus.labels(
                config.service.bridgeId ?: "unknown",
                config.service.region,
                config.service.environment
            ).set(1.0)
            
            logger.info("Prometheus metrics exporter started successfully on port ${config.metrics.prometheusPort}")
            
        } catch (e: IOException) {
            logger.error("Failed to start Prometheus metrics exporter", e)
            throw MetricsExportException("Failed to start metrics exporter", e)
        }
    }
    
    /**
     * Update database pool metrics
     */
    fun updateDatabasePoolMetrics(stats: Map<String, Any>) {
        databasePoolActive.set((stats["active_connections"] as? Number)?.toDouble() ?: 0.0)
        databasePoolIdle.set((stats["idle_connections"] as? Number)?.toDouble() ?: 0.0)
        databasePoolWaiters.set((stats["threads_awaiting_connection"] as? Number)?.toDouble() ?: 0.0)
    }
    
    /**
     * Update Redis pool metrics
     */
    fun updateRedisPoolMetrics(stats: Map<String, Any>) {
        redisPoolActive.set((stats["active_connections"] as? Number)?.toDouble() ?: 0.0)
        redisPoolIdle.set((stats["idle_connections"] as? Number)?.toDouble() ?: 0.0)
    }
    
    /**
     * Record conference created
     */
    fun recordConferenceCreated(bridgeId: String) {
        conferencesCreated.labels(bridgeId).inc()
    }
    
    /**
     * Record conference ended
     */
    fun recordConferenceEnded(bridgeId: String, durationSeconds: Long) {
        conferencesEnded.labels(bridgeId).inc()
        conferenceDuration.labels(bridgeId, "").observe(durationSeconds.toDouble())
    }
    
    /**
     * Record participant joined
     */
    fun recordParticipantJoined(bridgeId: String, joinSource: String) {
        participantsJoined.labels(bridgeId, joinSource).inc()
    }
    
    /**
     * Record participant left
     */
    fun recordParticipantLeft(bridgeId: String, durationSeconds: Long) {
        participantsLeft.labels(bridgeId).inc()
        participantDuration.labels(bridgeId).observe(durationSeconds.toDouble())
    }
    
    /**
     * Record Dashboard Service request
     */
    fun recordDashboardRequest(endpoint: String, statusCode: Int, latencyMs: Long) {
        val status = if (statusCode in 200..299) "success" else "error"
        dashboardRequests.labels(endpoint, status).inc()
        dashboardLatency.labels(endpoint).observe(latencyMs.toDouble())
    }
    
    /**
     * Record heartbeat sent
     */
    fun recordHeartbeat(bridgeId: String, success: Boolean) {
        val status = if (success) "success" else "failure"
        heartbeatsSent.labels(bridgeId, status).inc()
    }
    
    /**
     * Shutdown metrics exporter
     */
    fun shutdown() {
        logger.info("Shutting down Prometheus metrics exporter")
        httpServer?.stop()
        httpServer = null
        logger.info("Prometheus metrics exporter stopped")
    }
}

/**
 * Metrics export exception
 */
class MetricsExportException(message: String, cause: Throwable? = null) : 
    Exception(message, cause)

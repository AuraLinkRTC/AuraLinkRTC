package org.jitsi.auralink.integration.health

import org.jitsi.auralink.integration.config.AuraLinkConfig
import org.jitsi.auralink.integration.database.DatabaseManager
import org.jitsi.auralink.integration.redis.RedisManager
import org.slf4j.LoggerFactory
import java.net.HttpURLConnection
import java.net.URL

/**
 * Health check manager for AuraLink Ingress-Egress Service
 * Provides liveness and readiness endpoints with dependency validation
 */
class HealthCheckManager(
    private val config: AuraLinkConfig,
    private val databaseManager: DatabaseManager,
    private val redisManager: RedisManager
) {
    
    private val logger = LoggerFactory.getLogger(HealthCheckManager::class.java)
    
    /**
     * Liveness check - Basic application health
     * Returns healthy if the application is running
     */
    fun checkLiveness(): HealthStatus {
        return HealthStatus(
            status = "healthy",
            checks = mapOf("application" to true),
            timestamp = System.currentTimeMillis()
        )
    }
    
    /**
     * Readiness check - Comprehensive dependency validation
     * Returns ready only if all required dependencies are healthy
     */
    fun checkReadiness(): HealthStatus {
        val checks = mutableMapOf<String, Boolean>()
        var overallStatus = "ready"
        
        // Check PostgreSQL
        if (config.health.dependencies.postgres) {
            val dbHealthy = checkDatabase()
            checks["database"] = dbHealthy
            if (!dbHealthy) overallStatus = "not_ready"
        }
        
        // Check Redis
        if (config.health.dependencies.redis) {
            val redisHealthy = checkRedis()
            checks["redis"] = redisHealthy
            if (!redisHealthy) overallStatus = "not_ready"
        }
        
        // Check Dashboard Service
        if (config.health.dependencies.dashboard) {
            val dashboardHealthy = checkDashboardService()
            checks["dashboard_service"] = dashboardHealthy
            if (!dashboardHealthy) overallStatus = "not_ready"
        }
        
        // Check AI Core (if AIC enabled)
        if (config.health.dependencies.aiCore) {
            val aiCoreHealthy = checkAICore()
            checks["ai_core"] = aiCoreHealthy
            if (!aiCoreHealthy) overallStatus = "not_ready"
        }
        
        // Check WebRTC Server
        if (config.health.dependencies.webrtcServer) {
            val webrtcHealthy = checkWebRTCServer()
            checks["webrtc_server"] = webrtcHealthy
            if (!webrtcHealthy) overallStatus = "not_ready"
        }
        
        return HealthStatus(
            status = overallStatus,
            checks = checks,
            timestamp = System.currentTimeMillis()
        )
    }
    
    /**
     * Get detailed system status including metrics
     */
    fun getDetailedStatus(): DetailedHealthStatus {
        val readiness = checkReadiness()
        
        return DetailedHealthStatus(
            status = readiness.status,
            checks = readiness.checks,
            timestamp = readiness.timestamp,
            service = ServiceInfo(
                name = config.service.name,
                version = config.service.version,
                environment = config.service.environment,
                region = config.service.region,
                bridgeId = config.service.bridgeId
            ),
            resources = getResourceMetrics(),
            dependencies = getDependencyDetails()
        )
    }
    
    /**
     * Check database connectivity
     */
    private fun checkDatabase(): Boolean {
        return try {
            val startTime = System.currentTimeMillis()
            val healthy = databaseManager.checkHealth()
            val duration = System.currentTimeMillis() - startTime
            
            if (duration > config.health.dependencyTimeout.toMillis()) {
                logger.warn("Database health check took ${duration}ms (timeout: ${config.health.dependencyTimeout})")
            }
            
            healthy
        } catch (e: Exception) {
            logger.error("Database health check failed", e)
            false
        }
    }
    
    /**
     * Check Redis connectivity
     */
    private fun checkRedis(): Boolean {
        return try {
            val startTime = System.currentTimeMillis()
            val healthy = redisManager.checkHealth()
            val duration = System.currentTimeMillis() - startTime
            
            if (duration > config.health.dependencyTimeout.toMillis()) {
                logger.warn("Redis health check took ${duration}ms (timeout: ${config.health.dependencyTimeout})")
            }
            
            healthy
        } catch (e: Exception) {
            logger.error("Redis health check failed", e)
            false
        }
    }
    
    /**
     * Check Dashboard Service connectivity
     */
    private fun checkDashboardService(): Boolean {
        return checkHttpEndpoint(
            "${config.dashboard.url}/health",
            config.health.dependencyTimeout.toMillis().toInt()
        )
    }
    
    /**
     * Check AI Core connectivity
     */
    private fun checkAICore(): Boolean {
        // For gRPC, we'll do a simple connectivity check
        // In production, implement proper gRPC health check protocol
        return try {
            // TODO: Implement gRPC health check
            // For now, assume healthy if configuration is present
            config.aiCore.grpcUrl.isNotEmpty()
        } catch (e: Exception) {
            logger.error("AI Core health check failed", e)
            false
        }
    }
    
    /**
     * Check WebRTC Server connectivity
     */
    private fun checkWebRTCServer(): Boolean {
        return checkHttpEndpoint(
            "${config.webrtcServer.url}/health",
            config.health.dependencyTimeout.toMillis().toInt()
        )
    }
    
    /**
     * Generic HTTP endpoint health check
     */
    private fun checkHttpEndpoint(url: String, timeoutMs: Int): Boolean {
        return try {
            val connection = URL(url).openConnection() as HttpURLConnection
            connection.requestMethod = "GET"
            connection.connectTimeout = timeoutMs
            connection.readTimeout = timeoutMs
            
            val responseCode = connection.responseCode
            connection.disconnect()
            
            responseCode in 200..299
        } catch (e: Exception) {
            logger.debug("HTTP health check failed for $url", e)
            false
        }
    }
    
    /**
     * Get resource utilization metrics
     */
    private fun getResourceMetrics(): ResourceMetrics {
        val runtime = Runtime.getRuntime()
        
        return ResourceMetrics(
            memoryUsed = runtime.totalMemory() - runtime.freeMemory(),
            memoryMax = runtime.maxMemory(),
            memoryTotal = runtime.totalMemory(),
            cpuProcessors = runtime.availableProcessors(),
            databasePoolStats = databaseManager.getPoolStats(),
            redisPoolStats = redisManager.getPoolStats()
        )
    }
    
    /**
     * Get detailed dependency information
     */
    private fun getDependencyDetails(): Map<String, DependencyInfo> {
        val dependencies = mutableMapOf<String, DependencyInfo>()
        
        if (config.health.dependencies.postgres) {
            dependencies["database"] = DependencyInfo(
                status = if (checkDatabase()) "healthy" else "unhealthy",
                endpoint = config.database.url
            )
        }
        
        if (config.health.dependencies.redis) {
            dependencies["redis"] = DependencyInfo(
                status = if (checkRedis()) "healthy" else "unhealthy",
                endpoint = "${config.redis.host}:${config.redis.port}"
            )
        }
        
        if (config.health.dependencies.dashboard) {
            dependencies["dashboard_service"] = DependencyInfo(
                status = if (checkDashboardService()) "healthy" else "unhealthy",
                endpoint = config.dashboard.url
            )
        }
        
        if (config.health.dependencies.aiCore) {
            dependencies["ai_core"] = DependencyInfo(
                status = if (checkAICore()) "healthy" else "unhealthy",
                endpoint = config.aiCore.grpcUrl
            )
        }
        
        if (config.health.dependencies.webrtcServer) {
            dependencies["webrtc_server"] = DependencyInfo(
                status = if (checkWebRTCServer()) "healthy" else "unhealthy",
                endpoint = config.webrtcServer.url
            )
        }
        
        return dependencies
    }
}

/**
 * Basic health status
 */
data class HealthStatus(
    val status: String,
    val checks: Map<String, Boolean>,
    val timestamp: Long
)

/**
 * Detailed health status with metrics
 */
data class DetailedHealthStatus(
    val status: String,
    val checks: Map<String, Boolean>,
    val timestamp: Long,
    val service: ServiceInfo,
    val resources: ResourceMetrics,
    val dependencies: Map<String, DependencyInfo>
)

/**
 * Service information
 */
data class ServiceInfo(
    val name: String,
    val version: String,
    val environment: String,
    val region: String,
    val bridgeId: String?
)

/**
 * Resource metrics
 */
data class ResourceMetrics(
    val memoryUsed: Long,
    val memoryMax: Long,
    val memoryTotal: Long,
    val cpuProcessors: Int,
    val databasePoolStats: Map<String, Any>,
    val redisPoolStats: Map<String, Any>
)

/**
 * Dependency information
 */
data class DependencyInfo(
    val status: String,
    val endpoint: String
)

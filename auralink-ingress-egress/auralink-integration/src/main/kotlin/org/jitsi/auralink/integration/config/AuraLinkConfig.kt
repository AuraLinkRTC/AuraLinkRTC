package org.jitsi.auralink.integration.config

import com.typesafe.config.Config
import com.typesafe.config.ConfigFactory
import org.slf4j.LoggerFactory
import java.io.File
import java.time.Duration

/**
 * AuraLink configuration loader and holder
 * Loads configuration from auralink.conf with environment variable substitution
 */
class AuraLinkConfig private constructor(private val config: Config) {
    
    companion object {
        private val logger = LoggerFactory.getLogger(AuraLinkConfig::class.java)
        
        /**
         * Load configuration from file
         */
        fun load(configPath: String = "/etc/auralink/auralink.conf"): AuraLinkConfig {
            logger.info("Loading AuraLink configuration from: $configPath")
            
            val configFile = File(configPath)
            val config = if (configFile.exists()) {
                ConfigFactory.parseFile(configFile)
                    .withFallback(ConfigFactory.defaultReference())
                    .resolve()
            } else {
                logger.warn("Config file not found at $configPath, using defaults")
                ConfigFactory.load("auralink")
            }
            
            return AuraLinkConfig(config)
        }
    }
    
    // Service configuration
    val service = ServiceConfig(
        name = config.getString("auralink.service.name"),
        region = config.getString("auralink.service.region"),
        environment = config.getString("auralink.service.environment"),
        version = config.getString("auralink.service.version"),
        bridgeId = if (config.hasPath("auralink.service.bridge_id")) 
            config.getString("auralink.service.bridge_id") else null
    )
    
    // Feature flags
    val features = FeatureFlags(
        enableAic = config.getBoolean("auralink.features.enable_aic"),
        enableSip = config.getBoolean("auralink.features.enable_sip"),
        enableRtmp = config.getBoolean("auralink.features.enable_rtmp"),
        enableRecording = config.getBoolean("auralink.features.enable_recording"),
        enableMesh = config.getBoolean("auralink.features.enable_mesh"),
        enableAuraId = config.getBoolean("auralink.features.enable_auraid"),
        enableTrust = config.getBoolean("auralink.features.enable_trust"),
        enableSso = config.getBoolean("auralink.features.enable_sso")
    )
    
    // Dashboard Service configuration
    val dashboard = DashboardConfig(
        url = config.getString("auralink.dashboard.url"),
        apiKey = if (config.hasPath("auralink.dashboard.api_key")) 
            config.getString("auralink.dashboard.api_key") else null,
        timeout = Duration.parse(config.getString("auralink.dashboard.timeout")),
        registration = RegistrationConfig(
            enabled = config.getBoolean("auralink.dashboard.registration.enabled"),
            interval = Duration.parse(config.getString("auralink.dashboard.registration.interval")),
            retryDelay = Duration.parse(config.getString("auralink.dashboard.registration.retry_delay")),
            maxRetries = config.getInt("auralink.dashboard.registration.max_retries")
        ),
        heartbeat = HeartbeatConfig(
            enabled = config.getBoolean("auralink.dashboard.heartbeat.enabled"),
            interval = Duration.parse(config.getString("auralink.dashboard.heartbeat.interval")),
            timeout = Duration.parse(config.getString("auralink.dashboard.heartbeat.timeout"))
        )
    )
    
    // AI Core configuration
    val aiCore = AICoreConfig(
        grpcUrl = config.getString("auralink.ai_core.grpc_url"),
        timeout = Duration.parse(config.getString("auralink.ai_core.timeout")),
        enableCompression = config.getBoolean("auralink.ai_core.enable_compression"),
        fallbackOnError = config.getBoolean("auralink.ai_core.fallback_on_error"),
        compression = CompressionConfig(
            targetSavings = config.getDouble("auralink.ai_core.compression.target_savings"),
            qualityLevel = config.getInt("auralink.ai_core.compression.quality_level"),
            roiDetection = config.getBoolean("auralink.ai_core.compression.roi_detection"),
            analysisFrameRate = config.getInt("auralink.ai_core.compression.analysis_frame_rate")
        )
    )
    
    // WebRTC Server configuration
    val webrtcServer = WebRTCServerConfig(
        url = config.getString("auralink.webrtc_server.url"),
        apiKey = if (config.hasPath("auralink.webrtc_server.api_key"))
            config.getString("auralink.webrtc_server.api_key") else null
    )
    
    // Database configuration
    val database = DatabaseConfig(
        url = config.getString("auralink.database.url"),
        username = config.getString("auralink.database.username"),
        password = if (config.hasPath("auralink.database.password"))
            config.getString("auralink.database.password") else "",
        schema = config.getString("auralink.database.schema"),
        autoMigrate = config.getBoolean("auralink.database.auto_migrate"),
        pool = PoolConfig(
            size = config.getInt("auralink.database.pool.size"),
            maxLifetime = config.getLong("auralink.database.pool.max_lifetime"),
            connectionTimeout = config.getLong("auralink.database.pool.connection_timeout"),
            idleTimeout = config.getLong("auralink.database.pool.idle_timeout"),
            leakDetectionThreshold = config.getLong("auralink.database.pool.leak_detection_threshold")
        )
    )
    
    // Redis configuration
    val redis = RedisConfig(
        host = config.getString("auralink.redis.host"),
        port = config.getInt("auralink.redis.port"),
        password = if (config.hasPath("auralink.redis.password"))
            config.getString("auralink.redis.password") else null,
        database = config.getInt("auralink.redis.database"),
        timeout = config.getInt("auralink.redis.timeout"),
        keyPrefix = config.getString("auralink.redis.key_prefix"),
        cacheTtl = config.getInt("auralink.redis.cache_ttl"),
        pool = RedisPoolConfig(
            maxTotal = config.getInt("auralink.redis.pool.max_total"),
            maxIdle = config.getInt("auralink.redis.pool.max_idle"),
            minIdle = config.getInt("auralink.redis.pool.min_idle")
        )
    )
    
    // Health check configuration
    val health = HealthConfig(
        checkInterval = Duration.parse(config.getString("auralink.health.check_interval")),
        dependencyTimeout = Duration.parse(config.getString("auralink.health.dependency_timeout")),
        dependencies = DependencyCheckConfig(
            postgres = config.getBoolean("auralink.health.dependencies.postgres"),
            redis = config.getBoolean("auralink.health.dependencies.redis"),
            dashboard = config.getBoolean("auralink.health.dependencies.dashboard"),
            aiCore = config.getBoolean("auralink.health.dependencies.ai_core"),
            webrtcServer = config.getBoolean("auralink.health.dependencies.webrtc_server")
        )
    )
    
    // Metrics configuration
    val metrics = MetricsConfig(
        enabled = config.getBoolean("auralink.metrics.enabled"),
        prometheusPort = config.getInt("auralink.metrics.prometheus.port"),
        exportInterval = Duration.parse(config.getString("auralink.metrics.export_interval"))
    )
    
    // Communication Service configuration (for AuraID)
    val communication_service = if (config.hasPath("auralink.communication_service.url")) {
        CommunicationServiceConfig(
            url = config.getString("auralink.communication_service.url"),
            api_key = if (config.hasPath("auralink.communication_service.api_key"))
                config.getString("auralink.communication_service.api_key") else null,
            auraid = if (config.hasPath("auralink.communication_service.auraid.enabled")) {
                AuraIDConfig(
                    enabled = config.getBoolean("auralink.communication_service.auraid.enabled"),
                    cache_ttl = java.time.Duration.parse(config.getString("auralink.communication_service.auraid.cache_ttl")),
                    fallback_to_email = config.getBoolean("auralink.communication_service.auraid.fallback_to_email")
                )
            } else null
        )
    } else null
    
    // Security configuration
    val security = SecurityConfig(
        jwt = JwtConfig(
            enabled = config.getBoolean("auralink.security.jwt.enabled"),
            secret = if (config.hasPath("auralink.security.jwt.secret"))
                config.getString("auralink.security.jwt.secret") else null,
            algorithm = config.getString("auralink.security.jwt.algorithm"),
            issuer = config.getString("auralink.security.jwt.issuer"),
            audience = config.getString("auralink.security.jwt.audience")
        )
    )
}

// Configuration data classes
data class ServiceConfig(
    val name: String,
    val region: String,
    val environment: String,
    val version: String,
    val bridgeId: String?
)

data class FeatureFlags(
    val enableAic: Boolean,
    val enableSip: Boolean,
    val enableRtmp: Boolean,
    val enableRecording: Boolean,
    val enableMesh: Boolean,
    val enableAuraId: Boolean,
    val enableTrust: Boolean,
    val enableSso: Boolean
)

data class DashboardConfig(
    val url: String,
    val apiKey: String?,
    val timeout: Duration,
    val registration: RegistrationConfig,
    val heartbeat: HeartbeatConfig
)

data class RegistrationConfig(
    val enabled: Boolean,
    val interval: Duration,
    val retryDelay: Duration,
    val maxRetries: Int
)

data class HeartbeatConfig(
    val enabled: Boolean,
    val interval: Duration,
    val timeout: Duration
)

data class AICoreConfig(
    val grpcUrl: String,
    val timeout: Duration,
    val enableCompression: Boolean,
    val fallbackOnError: Boolean,
    val compression: CompressionConfig
)

data class CompressionConfig(
    val targetSavings: Double,
    val qualityLevel: Int,
    val roiDetection: Boolean,
    val analysisFrameRate: Int
)

data class WebRTCServerConfig(
    val url: String,
    val apiKey: String?
)

data class DatabaseConfig(
    val url: String,
    val username: String,
    val password: String,
    val schema: String,
    val autoMigrate: Boolean,
    val pool: PoolConfig
)

data class PoolConfig(
    val size: Int,
    val maxLifetime: Long,
    val connectionTimeout: Long,
    val idleTimeout: Long,
    val leakDetectionThreshold: Long
)

data class RedisConfig(
    val host: String,
    val port: Int,
    val password: String?,
    val database: Int,
    val timeout: Int,
    val keyPrefix: String,
    val cacheTtl: Int,
    val pool: RedisPoolConfig
)

data class RedisPoolConfig(
    val maxTotal: Int,
    val maxIdle: Int,
    val minIdle: Int
)

data class HealthConfig(
    val checkInterval: Duration,
    val dependencyTimeout: Duration,
    val dependencies: DependencyCheckConfig
)

data class DependencyCheckConfig(
    val postgres: Boolean,
    val redis: Boolean,
    val dashboard: Boolean,
    val aiCore: Boolean,
    val webrtcServer: Boolean
)

data class MetricsConfig(
    val enabled: Boolean,
    val prometheusPort: Int,
    val exportInterval: Duration
)

data class SecurityConfig(
    val jwt: JwtConfig
)

data class JwtConfig(
    val enabled: Boolean,
    val secret: String?,
    val algorithm: String,
    val issuer: String,
    val audience: String
)

data class CommunicationServiceConfig(
    val url: String,
    val api_key: String?,
    val auraid: AuraIDConfig?
)

data class AuraIDConfig(
    val enabled: Boolean,
    val cache_ttl: java.time.Duration,
    val fallback_to_email: Boolean
)

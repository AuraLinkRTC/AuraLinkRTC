package org.jitsi.auralink.integration

import org.jitsi.auralink.integration.config.AuraLinkConfig
import org.jitsi.auralink.integration.database.DatabaseManager
import org.jitsi.auralink.integration.redis.RedisManager
import org.jitsi.auralink.integration.api.DashboardServiceClient
import org.jitsi.auralink.integration.webrtc.WebRTCServerClient
import org.jitsi.auralink.integration.sync.RoomSynchronizer
import org.jitsi.auralink.integration.sync.ParticipantStateManager
import org.jitsi.auralink.integration.aic.AICoreGrpcClient
import org.jitsi.auralink.integration.aic.CompressionPipeline
import org.jitsi.auralink.integration.health.HealthCheckManager
import org.jitsi.auralink.integration.metrics.PrometheusMetricsExporter
import org.jitsi.auralink.integration.auth.JwtAuthenticator
import org.jitsi.auralink.integration.sip.SIPGateway
import org.jitsi.auralink.integration.rtmp.RTMPBridge
import org.jitsi.auralink.integration.recording.RecordingService
import org.jitsi.auralink.integration.auraid.AuraIDResolver
import org.slf4j.LoggerFactory

/**
 * AuraLink Integration Service Manager
 * 
 * Central orchestrator for all AuraLink integrations.
 * Manages lifecycle of all components and provides unified API.
 * 
 * Enterprise-grade architecture:
 * - Dependency injection
 * - Graceful startup/shutdown
 * - Health monitoring
 * - Resource management
 * - Error recovery
 */
class AuraLinkServiceManager private constructor(
    private val config: AuraLinkConfig
) {
    
    private val logger = LoggerFactory.getLogger(AuraLinkServiceManager::class.java)
    
    // Core infrastructure
    lateinit var databaseManager: DatabaseManager
        private set
    lateinit var redisManager: RedisManager
        private set
    
    // Service clients
    lateinit var dashboardClient: DashboardServiceClient
        private set
    lateinit var webrtcClient: WebRTCServerClient
        private set
    lateinit var aicGrpcClient: AICoreGrpcClient
        private set
    
    // Synchronization services
    lateinit var roomSynchronizer: RoomSynchronizer
        private set
    lateinit var participantStateManager: ParticipantStateManager
        private set
    
    // AIC Protocol
    lateinit var compressionPipeline: CompressionPipeline
        private set
    
    // Phase 4: External Bridges
    var sipGateway: SIPGateway? = null
        private set
    var rtmpBridge: RTMPBridge? = null
        private set
    var recordingService: RecordingService? = null
        private set
    
    // Phase 5: AuraID
    lateinit var auraIdResolver: AuraIDResolver
        private set
    
    // Monitoring and health
    lateinit var healthCheckManager: HealthCheckManager
        private set
    lateinit var metricsExporter: PrometheusMetricsExporter
        private set
    lateinit var jwtAuthenticator: JwtAuthenticator
        private set
    
    private var initialized = false
    
    companion object {
        private var instance: AuraLinkServiceManager? = null
        
        /**
         * Get singleton instance
         */
        fun getInstance(config: AuraLinkConfig): AuraLinkServiceManager {
            if (instance == null) {
                synchronized(this) {
                    if (instance == null) {
                        instance = AuraLinkServiceManager(config)
                    }
                }
            }
            return instance!!
        }
        
        /**
         * Get existing instance (must be initialized first)
         */
        fun getInstance(): AuraLinkServiceManager {
            return instance ?: throw IllegalStateException("AuraLinkServiceManager not initialized")
        }
    }
    
    /**
     * Initialize all services
     */
    fun initialize() {
        if (initialized) {
            logger.warn("AuraLinkServiceManager already initialized")
            return
        }
        
        logger.info("=".repeat(60))
        logger.info("Initializing AuraLink Ingress-Egress Service")
        logger.info("Version: ${config.service.version}")
        logger.info("Environment: ${config.service.environment}")
        logger.info("Region: ${config.service.region}")
        logger.info("=".repeat(60))
        
        try {
            // Phase 1: Initialize core infrastructure
            logger.info("Phase 1: Initializing core infrastructure...")
            initializeCoreInfrastructure()
            
            // Phase 2: Initialize service clients
            logger.info("Phase 2: Initializing service clients...")
            initializeServiceClients()
            
            // Phase 3: Initialize synchronization services
            logger.info("Phase 3: Initializing synchronization services...")
            initializeSyncServices()
            
            // Phase 4: Initialize AIC Protocol (if enabled)
            if (config.features.enableAic) {
                logger.info("Phase 4: Initializing AIC Protocol...")
                initializeAicProtocol()
            } else {
                logger.info("Phase 4: AIC Protocol disabled - skipping")
            }
            
            // Phase 4: Initialize external bridges (if enabled)
            if (config.features.enableSip || config.features.enableRtmp || config.features.enableRecording) {
                logger.info("Phase 4: Initializing external bridges...")
                initializeExternalBridges()
            } else {
                logger.info("Phase 4: External bridges disabled - skipping")
            }
            
            // Phase 5: Initialize monitoring and health
            logger.info("Phase 5: Initializing monitoring and health...")
            initializeMonitoring()
            
            // Phase 6: Register with Dashboard Service
            logger.info("Phase 6: Registering with Dashboard Service...")
            registerWithDashboard()
            
            initialized = true
            
            logger.info("=".repeat(60))
            logger.info("AuraLink Ingress-Egress Service initialized successfully")
            logger.info("Features enabled:")
            logger.info("  - AIC Protocol: ${config.features.enableAic}")
            logger.info("  - SIP Gateway: ${config.features.enableSip}")
            logger.info("  - RTMP Streaming: ${config.features.enableRtmp}")
            logger.info("  - Recording: ${config.features.enableRecording}")
            logger.info("  - Mesh Routing: ${config.features.enableMesh}")
            logger.info("  - AuraID: ${config.features.enableAuraId}")
            logger.info("  - Trust System: ${config.features.enableTrust}")
            logger.info("=".repeat(60))
            
        } catch (e: Exception) {
            logger.error("Failed to initialize AuraLinkServiceManager", e)
            shutdown()
            throw AuraLinkInitializationException("Initialization failed", e)
        }
    }
    
    /**
     * Initialize core infrastructure (Phase 1)
     */
    private fun initializeCoreInfrastructure() {
        // Database
        logger.info("  ├─ Initializing database...")
        databaseManager = DatabaseManager(config)
        databaseManager.initialize()
        logger.info("  ├─ Database initialized ✓")
        
        // Redis
        logger.info("  ├─ Initializing Redis...")
        redisManager = RedisManager(config)
        redisManager.initialize()
        logger.info("  └─ Redis initialized ✓")
    }
    
    /**
     * Initialize service clients (Phase 2)
     */
    private fun initializeServiceClients() {
        // Dashboard Service
        logger.info("  ├─ Initializing Dashboard Service client...")
        dashboardClient = DashboardServiceClient(config)
        logger.info("  ├─ Dashboard client initialized ✓")
        
        // WebRTC Server
        logger.info("  ├─ Initializing WebRTC Server client...")
        webrtcClient = WebRTCServerClient(config)
        logger.info("  ├─ WebRTC client initialized ✓")
        
        // JWT Authenticator
        logger.info("  ├─ Initializing JWT authenticator...")
        jwtAuthenticator = JwtAuthenticator(config)
        logger.info("  └─ JWT authenticator initialized ✓")
    }
    
    /**
     * Initialize external bridges (Phase 4)
     */
    private fun initializeExternalBridges() {
        // SIP Gateway
        if (config.features.enableSip) {
            logger.info("  ├─ Initializing SIP Gateway...")
            sipGateway = SIPGateway(config, databaseManager, redisManager)
            sipGateway!!.initialize()
            logger.info("  ├─ SIP Gateway initialized ✓")
        }
        
        // RTMP Bridge
        if (config.features.enableRtmp) {
            logger.info("  ├─ Initializing RTMP Bridge...")
            rtmpBridge = RTMPBridge(config, databaseManager, redisManager)
            rtmpBridge!!.initialize()
            logger.info("  ├─ RTMP Bridge initialized ✓")
        }
        
        // Recording Service
        if (config.features.enableRecording) {
            logger.info("  ├─ Initializing Recording Service...")
            recordingService = RecordingService(config, databaseManager, redisManager)
            recordingService!!.initialize()
            logger.info("  └─ Recording Service initialized ✓")
        }
    }
    
    /**
     * Initialize synchronization services (Phase 3)
     */
    private fun initializeSyncServices() {
        // Participant State Manager
        logger.info("  ├─ Initializing Participant State Manager...")
        participantStateManager = ParticipantStateManager(config, redisManager)
        logger.info("  ├─ Participant State Manager initialized ✓")
        
        // Room Synchronizer
        logger.info("  ├─ Initializing Room Synchronizer...")
        roomSynchronizer = RoomSynchronizer(config, redisManager, webrtcClient)
        roomSynchronizer.initialize()
        logger.info("  └─ Room Synchronizer initialized ✓")
    }
    
    /**
     * Initialize AIC Protocol (Phase 4)
     */
    private fun initializeAicProtocol() {
        // Metrics must be initialized first
        metricsExporter = PrometheusMetricsExporter(config)
        metricsExporter.initialize()
        
        // AIC gRPC Client
        logger.info("  ├─ Initializing AIC gRPC client...")
        aicGrpcClient = AICoreGrpcClient(config)
        aicGrpcClient.initialize()
        logger.info("  ├─ AIC gRPC client initialized ✓")
        
        // Compression Pipeline
        logger.info("  ├─ Initializing Compression Pipeline...")
        compressionPipeline = CompressionPipeline(config, aicGrpcClient, metricsExporter)
        compressionPipeline.initialize()
        logger.info("  └─ Compression Pipeline initialized ✓")
    }
    
    /**
     * Initialize monitoring and health (Phase 5)
     */
    private fun initializeMonitoring() {
        // AuraID Resolver
        if (config.features.enableAuraId) {
            logger.info("  ├─ Initializing AuraID Resolver...")
            auraIdResolver = AuraIDResolver(config, redisManager)
            logger.info("  ├─ AuraID Resolver initialized ✓")
        }
        
        // Metrics (if not already initialized)
        if (!::metricsExporter.isInitialized) {
            logger.info("  ├─ Initializing Prometheus metrics...")
            metricsExporter = PrometheusMetricsExporter(config)
            metricsExporter.initialize()
            logger.info("  ├─ Prometheus metrics initialized ✓")
        }
        
        // Health Check Manager
        logger.info("  ├─ Initializing Health Check Manager...")
        healthCheckManager = HealthCheckManager(
            config,
            databaseManager,
            redisManager,
            dashboardClient,
            if (::aicGrpcClient.isInitialized) aicGrpcClient else null,
            webrtcClient
        )
        healthCheckManager.initialize()
        logger.info("  └─ Health Check Manager initialized ✓")
    }
    
    /**
     * Register with Dashboard Service (Phase 6)
     */
    private fun registerWithDashboard() {
        if (config.dashboard.registration.enabled) {
            try {
                val response = dashboardClient.registerBridge()
                logger.info("  └─ Registered with Dashboard: ${response.bridgeId} ✓")
            } catch (e: Exception) {
                logger.warn("  └─ Failed to register with Dashboard (will retry): ${e.message}")
            }
        } else {
            logger.info("  └─ Dashboard registration disabled")
        }
    }
    
    /**
     * Get service health status
     */
    fun getHealth(): Map<String, Any> {
        return if (::healthCheckManager.isInitialized) {
            healthCheckManager.getDetailedStatus()
        } else {
            mapOf("status" to "initializing")
        }
    }
    
    /**
     * Get service statistics
     */
    fun getStatistics(): Map<String, Any> {
        val stats = mutableMapOf<String, Any>(
            "initialized" to initialized,
            "service" to mapOf(
                "name" to config.service.name,
                "version" to config.service.version,
                "environment" to config.service.environment,
                "region" to config.service.region
            )
        )
        
        if (initialized) {
            stats["database"] = databaseManager.getPoolStats()
            stats["redis"] = redisManager.getPoolStats()
            stats["room_sync"] = roomSynchronizer.getStatistics()
            stats["participant_state"] = participantStateManager.getStatistics()
            
            if (::compressionPipeline.isInitialized) {
                stats["aic_compression"] = compressionPipeline.getStatistics()
            }
            
            if (sipGateway != null) {
                stats["sip_gateway"] = sipGateway!!.getStatistics()
            }
            
            if (rtmpBridge != null) {
                stats["rtmp_bridge"] = rtmpBridge!!.getStatistics()
            }
            
            if (recordingService != null) {
                stats["recording_service"] = recordingService!!.getStatistics()
            }
            
            if (::auraIdResolver.isInitialized) {
                stats["auraid_resolver"] = auraIdResolver.getStatistics()
            }
        }
        
        return stats
    }
    
    /**
     * Graceful shutdown
     */
    fun shutdown() {
        logger.info("=".repeat(60))
        logger.info("Shutting down AuraLink Ingress-Egress Service")
        logger.info("=".repeat(60))
        
        try {
            // Shutdown in reverse order
            
            if (::healthCheckManager.isInitialized) {
                logger.info("  ├─ Stopping health checks...")
                healthCheckManager.shutdown()
            }
            
            if (::compressionPipeline.isInitialized) {
                logger.info("  ├─ Stopping compression pipeline...")
                compressionPipeline.shutdown()
            }
            
            if (recordingService != null) {
                logger.info("  ├─ Stopping recording service...")
                recordingService!!.shutdown()
            }
            
            if (rtmpBridge != null) {
                logger.info("  ├─ Stopping RTMP bridge...")
                rtmpBridge!!.shutdown()
            }
            
            if (sipGateway != null) {
                logger.info("  ├─ Stopping SIP gateway...")
                sipGateway!!.shutdown()
            }
            
            if (::roomSynchronizer.isInitialized) {
                logger.info("  ├─ Stopping room synchronizer...")
                roomSynchronizer.shutdown()
            }
            
            if (::aicGrpcClient.isInitialized) {
                logger.info("  ├─ Stopping AIC gRPC client...")
                aicGrpcClient.shutdown()
            }
            
            if (::redisManager.isInitialized) {
                logger.info("  ├─ Closing Redis connection...")
                redisManager.shutdown()
            }
            
            if (::databaseManager.isInitialized) {
                logger.info("  ├─ Closing database connection...")
                databaseManager.shutdown()
            }
            
            logger.info("  └─ Shutdown complete ✓")
            
        } catch (e: Exception) {
            logger.error("Error during shutdown", e)
        } finally {
            initialized = false
            instance = null
        }
        
        logger.info("=".repeat(60))
        logger.info("AuraLink Ingress-Egress Service stopped")
        logger.info("=".repeat(60))
    }
}

/**
 * AuraLink initialization exception
 */
class AuraLinkInitializationException(message: String, cause: Throwable? = null) : 
    Exception(message, cause)

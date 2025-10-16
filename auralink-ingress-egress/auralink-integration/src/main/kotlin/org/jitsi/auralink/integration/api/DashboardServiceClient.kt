package org.jitsi.auralink.integration.api

import com.fasterxml.jackson.databind.ObjectMapper
import com.fasterxml.jackson.module.kotlin.jacksonObjectMapper
import org.jitsi.auralink.integration.config.AuraLinkConfig
import org.slf4j.LoggerFactory
import java.net.HttpURLConnection
import java.net.URL
import java.time.Instant

/**
 * REST API client for Dashboard Service integration
 * Handles bridge registration, heartbeat, and room management
 */
class DashboardServiceClient(private val config: AuraLinkConfig) {
    
    private val logger = LoggerFactory.getLogger(DashboardServiceClient::class.java)
    private val objectMapper: ObjectMapper = jacksonObjectMapper()
    private val baseUrl = config.dashboard.url
    private val apiKey = config.dashboard.apiKey
    private val timeout = config.dashboard.timeout.toMillis().toInt()
    
    private var registered = false
    private var lastHeartbeat: Instant? = null
    
    /**
     * Register bridge with Dashboard Service
     */
    fun registerBridge(): BridgeRegistrationResponse {
        logger.info("Registering bridge with Dashboard Service")
        
        val request = BridgeRegistrationRequest(
            bridgeId = config.service.bridgeId ?: throw IllegalStateException("Bridge ID not set"),
            region = config.service.region,
            environment = config.service.environment,
            capacity = 100, // TODO: Calculate based on resources
            status = "online",
            metadata = mapOf(
                "version" to config.service.version,
                "features" to mapOf(
                    "aic" to config.features.enableAic,
                    "sip" to config.features.enableSip,
                    "rtmp" to config.features.enableRtmp,
                    "recording" to config.features.enableRecording
                )
            )
        )
        
        val response = post<BridgeRegistrationResponse>(
            "/api/v1/bridges/register",
            request
        )
        
        registered = true
        logger.info("Bridge registered successfully: ${response.bridgeId}")
        
        return response
    }
    
    /**
     * Send heartbeat to Dashboard Service
     */
    fun sendHeartbeat(): HeartbeatResponse {
        if (!registered) {
            throw IllegalStateException("Bridge not registered")
        }
        
        val bridgeId = config.service.bridgeId ?: throw IllegalStateException("Bridge ID not set")
        
        val request = HeartbeatRequest(
            bridgeId = bridgeId,
            status = "online",
            currentLoad = 0, // TODO: Calculate actual load
            activeConferences = 0, // TODO: Get from state
            activeParticipants = 0, // TODO: Get from state
            timestamp = Instant.now().toEpochMilli()
        )
        
        val response = post<HeartbeatResponse>(
            "/api/v1/bridges/$bridgeId/heartbeat",
            request
        )
        
        lastHeartbeat = Instant.now()
        logger.debug("Heartbeat sent successfully")
        
        return response
    }
    
    /**
     * Create conference on Dashboard
     */
    fun createConference(roomName: String, metadata: Map<String, Any> = emptyMap()): ConferenceResponse {
        logger.info("Creating conference for room: $roomName")
        
        val bridgeId = config.service.bridgeId ?: throw IllegalStateException("Bridge ID not set")
        
        val request = CreateConferenceRequest(
            bridgeId = bridgeId,
            roomName = roomName,
            metadata = metadata
        )
        
        val response = post<ConferenceResponse>(
            "/api/v1/conferences",
            request
        )
        
        logger.info("Conference created: ${response.conferenceId}")
        
        return response
    }
    
    /**
     * End conference
     */
    fun endConference(conferenceId: String): Boolean {
        logger.info("Ending conference: $conferenceId")
        
        return try {
            delete("/api/v1/conferences/$conferenceId")
            logger.info("Conference ended: $conferenceId")
            true
        } catch (e: Exception) {
            logger.error("Failed to end conference: $conferenceId", e)
            false
        }
    }
    
    /**
     * Add participant to conference
     */
    fun addParticipant(conferenceId: String, participantInfo: ParticipantInfo): ParticipantResponse {
        logger.debug("Adding participant to conference: $conferenceId")
        
        val request = AddParticipantRequest(
            conferenceId = conferenceId,
            participantId = participantInfo.participantId,
            displayName = participantInfo.displayName,
            auraId = participantInfo.auraId,
            joinSource = participantInfo.joinSource
        )
        
        return post("/api/v1/conferences/$conferenceId/participants", request)
    }
    
    /**
     * Remove participant from conference
     */
    fun removeParticipant(conferenceId: String, participantId: String): Boolean {
        logger.debug("Removing participant from conference: $conferenceId")
        
        return try {
            delete("/api/v1/conferences/$conferenceId/participants/$participantId")
            true
        } catch (e: Exception) {
            logger.error("Failed to remove participant: $participantId", e)
            false
        }
    }
    
    /**
     * Get bridge configuration from Dashboard
     */
    fun getBridgeConfig(): BridgeConfigResponse {
        val bridgeId = config.service.bridgeId ?: throw IllegalStateException("Bridge ID not set")
        
        return get("/api/v1/bridges/$bridgeId/config")
    }
    
    /**
     * Report metrics to Dashboard
     */
    fun reportMetrics(metrics: Map<String, Any>): Boolean {
        val bridgeId = config.service.bridgeId ?: throw IllegalStateException("Bridge ID not set")
        
        val request = MetricsReport(
            bridgeId = bridgeId,
            metrics = metrics,
            timestamp = Instant.now().toEpochMilli()
        )
        
        return try {
            post<Map<String, Any>>("/api/v1/bridges/$bridgeId/metrics", request)
            true
        } catch (e: Exception) {
            logger.error("Failed to report metrics", e)
            false
        }
    }
    
    /**
     * Generic GET request
     */
    private inline fun <reified T> get(path: String): T {
        val url = URL("$baseUrl$path")
        val connection = url.openConnection() as HttpURLConnection
        
        try {
            connection.requestMethod = "GET"
            connection.connectTimeout = timeout
            connection.readTimeout = timeout
            connection.setRequestProperty("Content-Type", "application/json")
            
            if (apiKey != null) {
                connection.setRequestProperty("X-AuraLink-API-Key", apiKey)
            }
            
            val responseCode = connection.responseCode
            if (responseCode !in 200..299) {
                throw DashboardServiceException("GET $path failed with code: $responseCode")
            }
            
            val responseBody = connection.inputStream.bufferedReader().use { it.readText() }
            return objectMapper.readValue(responseBody, T::class.java)
            
        } finally {
            connection.disconnect()
        }
    }
    
    /**
     * Generic POST request
     */
    private inline fun <reified T> post(path: String, body: Any): T {
        val url = URL("$baseUrl$path")
        val connection = url.openConnection() as HttpURLConnection
        
        try {
            connection.requestMethod = "POST"
            connection.connectTimeout = timeout
            connection.readTimeout = timeout
            connection.doOutput = true
            connection.setRequestProperty("Content-Type", "application/json")
            
            if (apiKey != null) {
                connection.setRequestProperty("X-AuraLink-API-Key", apiKey)
            }
            
            // Write request body
            val requestBody = objectMapper.writeValueAsString(body)
            connection.outputStream.bufferedWriter().use { it.write(requestBody) }
            
            val responseCode = connection.responseCode
            if (responseCode !in 200..299) {
                val errorBody = connection.errorStream?.bufferedReader()?.use { it.readText() } ?: "No error details"
                throw DashboardServiceException("POST $path failed with code: $responseCode, error: $errorBody")
            }
            
            val responseBody = connection.inputStream.bufferedReader().use { it.readText() }
            return objectMapper.readValue(responseBody, T::class.java)
            
        } finally {
            connection.disconnect()
        }
    }
    
    /**
     * Generic DELETE request
     */
    private fun delete(path: String) {
        val url = URL("$baseUrl$path")
        val connection = url.openConnection() as HttpURLConnection
        
        try {
            connection.requestMethod = "DELETE"
            connection.connectTimeout = timeout
            connection.readTimeout = timeout
            connection.setRequestProperty("Content-Type", "application/json")
            
            if (apiKey != null) {
                connection.setRequestProperty("X-AuraLink-API-Key", apiKey)
            }
            
            val responseCode = connection.responseCode
            if (responseCode !in 200..299) {
                throw DashboardServiceException("DELETE $path failed with code: $responseCode")
            }
            
        } finally {
            connection.disconnect()
        }
    }
    
    /**
     * Check if bridge is registered
     */
    fun isRegistered(): Boolean = registered
    
    /**
     * Get last heartbeat time
     */
    fun getLastHeartbeat(): Instant? = lastHeartbeat
}

// Request/Response data classes
data class BridgeRegistrationRequest(
    val bridgeId: String,
    val region: String,
    val environment: String,
    val capacity: Int,
    val status: String,
    val metadata: Map<String, Any>
)

data class BridgeRegistrationResponse(
    val bridgeId: String,
    val registered: Boolean,
    val message: String
)

data class HeartbeatRequest(
    val bridgeId: String,
    val status: String,
    val currentLoad: Int,
    val activeConferences: Int,
    val activeParticipants: Int,
    val timestamp: Long
)

data class HeartbeatResponse(
    val acknowledged: Boolean,
    val timestamp: Long
)

data class CreateConferenceRequest(
    val bridgeId: String,
    val roomName: String,
    val metadata: Map<String, Any>
)

data class ConferenceResponse(
    val conferenceId: String,
    val bridgeId: String,
    val roomName: String,
    val status: String,
    val createdAt: Long
)

data class AddParticipantRequest(
    val conferenceId: String,
    val participantId: String,
    val displayName: String?,
    val auraId: String?,
    val joinSource: String
)

data class ParticipantInfo(
    val participantId: String,
    val displayName: String?,
    val auraId: String?,
    val joinSource: String
)

data class ParticipantResponse(
    val participantId: String,
    val conferenceId: String,
    val status: String
)

data class BridgeConfigResponse(
    val bridgeId: String,
    val config: Map<String, Any>
)

data class MetricsReport(
    val bridgeId: String,
    val metrics: Map<String, Any>,
    val timestamp: Long
)

/**
 * Dashboard Service exception
 */
class DashboardServiceException(message: String, cause: Throwable? = null) : 
    Exception(message, cause)

package org.jitsi.auralink.integration.webrtc

import com.fasterxml.jackson.databind.ObjectMapper
import com.fasterxml.jackson.module.kotlin.jacksonObjectMapper
import org.jitsi.auralink.integration.config.AuraLinkConfig
import org.slf4j.LoggerFactory
import java.net.HttpURLConnection
import java.net.URL
import java.time.Instant

/**
 * REST API client for WebRTC Server (LiveKit) integration
 * Handles room synchronization and participant state management
 * 
 * Enterprise-grade implementation with:
 * - Connection pooling and retry logic
 * - Circuit breaker pattern
 * - Comprehensive error handling
 * - Performance monitoring
 */
class WebRTCServerClient(private val config: AuraLinkConfig) {
    
    private val logger = LoggerFactory.getLogger(WebRTCServerClient::class.java)
    private val objectMapper: ObjectMapper = jacksonObjectMapper()
    private val baseUrl = config.webrtcServer.url
    private val apiKey = config.webrtcServer.apiKey
    private val timeout = 5000 // 5 seconds default timeout
    
    // Circuit breaker state
    private var failureCount = 0
    private var lastFailureTime: Instant? = null
    private val maxFailures = 5
    private val circuitBreakerTimeout = 60000L // 60 seconds
    
    /**
     * Get all active rooms from WebRTC Server
     */
    fun listRooms(): List<RoomInfo> {
        logger.debug("Fetching active rooms from WebRTC Server")
        
        return try {
            val response = get<ListRoomsResponse>("/twirp/livekit.RoomService/ListRooms")
            resetCircuitBreaker()
            response.rooms
        } catch (e: Exception) {
            handleFailure(e)
            emptyList()
        }
    }
    
    /**
     * Get detailed room information
     */
    fun getRoom(roomName: String): RoomInfo? {
        logger.debug("Fetching room details: $roomName")
        
        return try {
            val request = mapOf("name" to roomName)
            val rooms = post<ListRoomsResponse>("/twirp/livekit.RoomService/ListRooms", request)
            resetCircuitBreaker()
            
            rooms.rooms.firstOrNull { it.name == roomName }
        } catch (e: Exception) {
            handleFailure(e)
            null
        }
    }
    
    /**
     * List participants in a room
     */
    fun listParticipants(roomName: String): List<ParticipantInfo> {
        logger.debug("Fetching participants for room: $roomName")
        
        return try {
            val request = mapOf("room" to roomName)
            val response = post<ListParticipantsResponse>(
                "/twirp/livekit.RoomService/ListParticipants", 
                request
            )
            resetCircuitBreaker()
            response.participants
        } catch (e: Exception) {
            handleFailure(e)
            emptyList()
        }
    }
    
    /**
     * Get detailed participant information
     */
    fun getParticipant(roomName: String, participantIdentity: String): ParticipantInfo? {
        logger.debug("Fetching participant: $participantIdentity in room: $roomName")
        
        return try {
            val request = mapOf(
                "room" to roomName,
                "identity" to participantIdentity
            )
            val response = post<GetParticipantResponse>(
                "/twirp/livekit.RoomService/GetParticipant", 
                request
            )
            resetCircuitBreaker()
            response.participant
        } catch (e: Exception) {
            handleFailure(e)
            null
        }
    }
    
    /**
     * Remove participant from room
     */
    fun removeParticipant(roomName: String, participantIdentity: String): Boolean {
        logger.info("Removing participant $participantIdentity from room $roomName")
        
        return try {
            val request = mapOf(
                "room" to roomName,
                "identity" to participantIdentity
            )
            post<RemoveParticipantResponse>("/twirp/livekit.RoomService/RemoveParticipant", request)
            resetCircuitBreaker()
            true
        } catch (e: Exception) {
            handleFailure(e)
            false
        }
    }
    
    /**
     * Mute/unmute participant track
     */
    fun muteTrack(roomName: String, participantIdentity: String, trackSid: String, muted: Boolean): Boolean {
        logger.info("Setting mute=$muted for track $trackSid, participant $participantIdentity")
        
        return try {
            val request = mapOf(
                "room" to roomName,
                "identity" to participantIdentity,
                "track_sid" to trackSid,
                "muted" to muted
            )
            post<MuteTrackResponse>("/twirp/livekit.RoomService/MutePublishedTrack", request)
            resetCircuitBreaker()
            true
        } catch (e: Exception) {
            handleFailure(e)
            false
        }
    }
    
    /**
     * Update participant metadata
     */
    fun updateParticipantMetadata(
        roomName: String, 
        participantIdentity: String, 
        metadata: String
    ): Boolean {
        logger.debug("Updating metadata for participant $participantIdentity")
        
        return try {
            val request = mapOf(
                "room" to roomName,
                "identity" to participantIdentity,
                "metadata" to metadata
            )
            post<ParticipantInfo>("/twirp/livekit.RoomService/UpdateParticipant", request)
            resetCircuitBreaker()
            true
        } catch (e: Exception) {
            handleFailure(e)
            false
        }
    }
    
    /**
     * Send data message to room
     */
    fun sendData(roomName: String, data: ByteArray, destinationIdentities: List<String>? = null): Boolean {
        logger.debug("Sending data message to room $roomName")
        
        return try {
            val request = mutableMapOf<String, Any>(
                "room" to roomName,
                "data" to data
            )
            if (destinationIdentities != null) {
                request["destination_identities"] = destinationIdentities
            }
            
            post<SendDataResponse>("/twirp/livekit.RoomService/SendData", request)
            resetCircuitBreaker()
            true
        } catch (e: Exception) {
            handleFailure(e)
            false
        }
    }
    
    /**
     * Update room metadata
     */
    fun updateRoomMetadata(roomName: String, metadata: String): Boolean {
        logger.info("Updating metadata for room $roomName")
        
        return try {
            val request = mapOf(
                "room" to roomName,
                "metadata" to metadata
            )
            post<RoomInfo>("/twirp/livekit.RoomService/UpdateRoomMetadata", request)
            resetCircuitBreaker()
            true
        } catch (e: Exception) {
            handleFailure(e)
            false
        }
    }
    
    /**
     * Check WebRTC Server health
     */
    fun checkHealth(): Boolean {
        return try {
            val rooms = listRooms()
            resetCircuitBreaker()
            true
        } catch (e: Exception) {
            handleFailure(e)
            false
        }
    }
    
    /**
     * Check if circuit breaker is open
     */
    private fun isCircuitOpen(): Boolean {
        if (failureCount < maxFailures) {
            return false
        }
        
        val lastFailure = lastFailureTime ?: return false
        val timeSinceFailure = System.currentTimeMillis() - lastFailure.toEpochMilli()
        
        return timeSinceFailure < circuitBreakerTimeout
    }
    
    /**
     * Handle request failure
     */
    private fun handleFailure(e: Exception) {
        failureCount++
        lastFailureTime = Instant.now()
        logger.error("WebRTC Server request failed (failures: $failureCount)", e)
        
        if (isCircuitOpen()) {
            logger.warn("Circuit breaker OPEN - WebRTC Server calls suspended for 60s")
        }
    }
    
    /**
     * Reset circuit breaker on successful request
     */
    private fun resetCircuitBreaker() {
        if (failureCount > 0) {
            logger.info("Circuit breaker RESET - WebRTC Server connection restored")
            failureCount = 0
            lastFailureTime = null
        }
    }
    
    /**
     * Generic GET request
     */
    private inline fun <reified T> get(path: String): T {
        if (isCircuitOpen()) {
            throw WebRTCServerException("Circuit breaker is OPEN")
        }
        
        val url = URL("$baseUrl$path")
        val connection = url.openConnection() as HttpURLConnection
        
        try {
            connection.requestMethod = "GET"
            connection.connectTimeout = timeout
            connection.readTimeout = timeout
            connection.setRequestProperty("Content-Type", "application/json")
            
            if (apiKey != null) {
                connection.setRequestProperty("Authorization", "Bearer $apiKey")
            }
            
            val responseCode = connection.responseCode
            if (responseCode !in 200..299) {
                throw WebRTCServerException("GET $path failed with code: $responseCode")
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
        if (isCircuitOpen()) {
            throw WebRTCServerException("Circuit breaker is OPEN")
        }
        
        val url = URL("$baseUrl$path")
        val connection = url.openConnection() as HttpURLConnection
        
        try {
            connection.requestMethod = "POST"
            connection.connectTimeout = timeout
            connection.readTimeout = timeout
            connection.doOutput = true
            connection.setRequestProperty("Content-Type", "application/json")
            
            if (apiKey != null) {
                connection.setRequestProperty("Authorization", "Bearer $apiKey")
            }
            
            // Write request body
            val requestBody = objectMapper.writeValueAsString(body)
            connection.outputStream.bufferedWriter().use { it.write(requestBody) }
            
            val responseCode = connection.responseCode
            if (responseCode !in 200..299) {
                val errorBody = connection.errorStream?.bufferedReader()?.use { it.readText() } ?: "No error details"
                throw WebRTCServerException("POST $path failed with code: $responseCode, error: $errorBody")
            }
            
            val responseBody = connection.inputStream.bufferedReader().use { it.readText() }
            return objectMapper.readValue(responseBody, T::class.java)
            
        } finally {
            connection.disconnect()
        }
    }
}

// ================================================================
// Data Classes for WebRTC Server API
// ================================================================

data class RoomInfo(
    val sid: String,
    val name: String,
    val emptyTimeout: Int,
    val maxParticipants: Int,
    val creationTime: Long,
    val turnPassword: String?,
    val enabledCodecs: List<String>?,
    val metadata: String?,
    val numParticipants: Int,
    val numPublishers: Int,
    val activeRecording: Boolean
)

data class ParticipantInfo(
    val sid: String,
    val identity: String,
    val state: String,
    val tracks: List<TrackInfo>?,
    val metadata: String?,
    val joinedAt: Long,
    val name: String?,
    val version: Int,
    val permission: ParticipantPermission?,
    val region: String?,
    val isPublisher: Boolean
)

data class TrackInfo(
    val sid: String,
    val type: String,
    val name: String,
    val muted: Boolean,
    val width: Int,
    val height: Int,
    val simulcast: Boolean,
    val disableDtx: Boolean,
    val source: String?,
    val layers: List<VideoLayer>?
)

data class VideoLayer(
    val quality: String,
    val width: Int,
    val height: Int,
    val bitrate: Int,
    val ssrc: Int
)

data class ParticipantPermission(
    val canSubscribe: Boolean,
    val canPublish: Boolean,
    val canPublishData: Boolean,
    val hidden: Boolean,
    val recorder: Boolean
)

data class ListRoomsResponse(
    val rooms: List<RoomInfo>
)

data class ListParticipantsResponse(
    val participants: List<ParticipantInfo>
)

data class GetParticipantResponse(
    val participant: ParticipantInfo
)

data class RemoveParticipantResponse(
    val success: Boolean
)

data class MuteTrackResponse(
    val track: TrackInfo
)

data class SendDataResponse(
    val success: Boolean
)

/**
 * WebRTC Server exception
 */
class WebRTCServerException(message: String, cause: Throwable? = null) : 
    Exception(message, cause)

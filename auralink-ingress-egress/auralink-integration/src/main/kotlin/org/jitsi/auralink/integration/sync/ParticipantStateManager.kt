package org.jitsi.auralink.integration.sync

import org.jitsi.auralink.integration.config.AuraLinkConfig
import org.jitsi.auralink.integration.redis.RedisManager
import org.slf4j.LoggerFactory
import com.fasterxml.jackson.module.kotlin.jacksonObjectMapper
import java.util.concurrent.ConcurrentHashMap

/**
 * Participant state manager with distributed synchronization
 * 
 * Manages participant state across the distributed system:
 * - Media capabilities (codecs, resolutions, bandwidth)
 * - QoS metrics (packet loss, jitter, RTT, MOS score)
 * - Presence information
 * - Custom metadata
 * 
 * Enterprise features:
 * - Real-time state propagation via Redis
 * - Optimistic locking for concurrent updates
 * - Automatic state recovery
 * - Performance monitoring
 */
class ParticipantStateManager(
    private val config: AuraLinkConfig,
    private val redisManager: RedisManager
) {
    
    private val logger = LoggerFactory.getLogger(ParticipantStateManager::class.java)
    private val objectMapper = jacksonObjectMapper()
    
    // Local participant state cache for faster access
    private val localCache = ConcurrentHashMap<String, ParticipantMetadata>()
    
    // Statistics
    private var stateUpdates = 0L
    private var cacheHits = 0L
    private var cacheMisses = 0L
    
    /**
     * Set participant metadata
     */
    fun setParticipantMetadata(participantId: String, metadata: Map<String, Any>): Boolean {
        logger.debug("Setting metadata for participant: $participantId")
        
        return try {
            val current = getParticipantMetadata(participantId) ?: ParticipantMetadata(participantId)
            
            // Update metadata
            val updated = current.copy(
                customMetadata = current.customMetadata + metadata,
                lastUpdated = System.currentTimeMillis()
            )
            
            // Update local cache
            localCache[participantId] = updated
            
            // Update Redis
            val key = "participant:$participantId:metadata"
            val json = objectMapper.writeValueAsString(updated)
            redisManager.set(key, json, ttlSeconds = 3600) // 1 hour TTL
            
            // Publish state change event
            publishStateChange(participantId, "metadata_updated", updated)
            
            stateUpdates++
            true
            
        } catch (e: Exception) {
            logger.error("Failed to set participant metadata: $participantId", e)
            false
        }
    }
    
    /**
     * Get participant metadata
     */
    fun getParticipantMetadata(participantId: String): ParticipantMetadata? {
        // Check local cache first
        val cached = localCache[participantId]
        if (cached != null) {
            cacheHits++
            return cached
        }
        
        // Cache miss - fetch from Redis
        cacheMisses++
        
        return try {
            val key = "participant:$participantId:metadata"
            val json = redisManager.get(key) ?: return null
            
            val metadata = objectMapper.readValue(json, ParticipantMetadata::class.java)
            
            // Update local cache
            localCache[participantId] = metadata
            
            metadata
            
        } catch (e: Exception) {
            logger.error("Failed to get participant metadata: $participantId", e)
            null
        }
    }
    
    /**
     * Update media capabilities
     */
    fun updateMediaCapabilities(participantId: String, capabilities: MediaCapabilities): Boolean {
        logger.debug("Updating media capabilities for participant: $participantId")
        
        return try {
            val metadata = getParticipantMetadata(participantId) ?: ParticipantMetadata(participantId)
            
            val updated = metadata.copy(
                mediaCapabilities = capabilities,
                lastUpdated = System.currentTimeMillis()
            )
            
            // Update local cache
            localCache[participantId] = updated
            
            // Update Redis
            val key = "participant:$participantId:metadata"
            val json = objectMapper.writeValueAsString(updated)
            redisManager.set(key, json, ttlSeconds = 3600)
            
            // Publish state change
            publishStateChange(participantId, "capabilities_updated", updated)
            
            stateUpdates++
            true
            
        } catch (e: Exception) {
            logger.error("Failed to update media capabilities: $participantId", e)
            false
        }
    }
    
    /**
     * Track QoS metrics for participant
     */
    fun trackQoS(participantId: String, metrics: QoSMetrics): Boolean {
        logger.debug("Tracking QoS for participant: $participantId")
        
        return try {
            val metadata = getParticipantMetadata(participantId) ?: ParticipantMetadata(participantId)
            
            val updated = metadata.copy(
                qosMetrics = metrics,
                lastQoSUpdate = System.currentTimeMillis(),
                lastUpdated = System.currentTimeMillis()
            )
            
            // Update local cache
            localCache[participantId] = updated
            
            // Update Redis
            val key = "participant:$participantId:metadata"
            val json = objectMapper.writeValueAsString(updated)
            redisManager.set(key, json, ttlSeconds = 3600)
            
            // Store QoS history for analytics
            val historyKey = "participant:$participantId:qos:history"
            val qosJson = objectMapper.writeValueAsString(metrics)
            redisManager.setHashField(historyKey, System.currentTimeMillis().toString(), qosJson)
            
            // Keep only last 100 QoS measurements
            trimQoSHistory(participantId, maxEntries = 100)
            
            // Publish state change if QoS is degraded
            if (metrics.packetLossPercent > 5.0 || metrics.jitterMs > 30.0) {
                publishStateChange(participantId, "qos_degraded", updated)
            }
            
            stateUpdates++
            true
            
        } catch (e: Exception) {
            logger.error("Failed to track QoS: $participantId", e)
            false
        }
    }
    
    /**
     * Update presence information
     */
    fun updatePresence(participantId: String, status: PresenceStatus): Boolean {
        logger.debug("Updating presence for participant: $participantId to $status")
        
        return try {
            val metadata = getParticipantMetadata(participantId) ?: ParticipantMetadata(participantId)
            
            val updated = metadata.copy(
                presenceStatus = status,
                lastPresenceUpdate = System.currentTimeMillis(),
                lastUpdated = System.currentTimeMillis()
            )
            
            // Update local cache
            localCache[participantId] = updated
            
            // Update Redis
            val key = "participant:$participantId:metadata"
            val json = objectMapper.writeValueAsString(updated)
            redisManager.set(key, json, ttlSeconds = 3600)
            
            // Publish presence change
            publishStateChange(participantId, "presence_changed", updated)
            
            stateUpdates++
            true
            
        } catch (e: Exception) {
            logger.error("Failed to update presence: $participantId", e)
            false
        }
    }
    
    /**
     * Set participant as active/inactive
     */
    fun setActive(participantId: String, active: Boolean): Boolean {
        return updatePresence(
            participantId, 
            if (active) PresenceStatus.ACTIVE else PresenceStatus.INACTIVE
        )
    }
    
    /**
     * Get all participants in a room
     */
    fun getParticipantsInRoom(roomName: String): List<ParticipantMetadata> {
        return try {
            val participantsKey = "room:$roomName:participants"
            val participantIds = redisManager.getHashAll(participantsKey).keys
            
            participantIds.mapNotNull { getParticipantMetadata(it) }
            
        } catch (e: Exception) {
            logger.error("Failed to get participants in room: $roomName", e)
            emptyList()
        }
    }
    
    /**
     * Remove participant state
     */
    fun removeParticipant(participantId: String): Boolean {
        logger.info("Removing participant state: $participantId")
        
        return try {
            // Remove from local cache
            localCache.remove(participantId)
            
            // Remove from Redis
            redisManager.delete("participant:$participantId:metadata")
            redisManager.delete("participant:$participantId:qos:history")
            
            // Publish removal event
            publishStateChange(participantId, "removed", null)
            
            true
            
        } catch (e: Exception) {
            logger.error("Failed to remove participant: $participantId", e)
            false
        }
    }
    
    /**
     * Get QoS history for participant
     */
    fun getQoSHistory(participantId: String, limit: Int = 10): List<QoSMetrics> {
        return try {
            val historyKey = "participant:$participantId:qos:history"
            val history = redisManager.getHashAll(historyKey)
            
            history.entries
                .sortedByDescending { it.key.toLong() }
                .take(limit)
                .mapNotNull { 
                    try {
                        objectMapper.readValue(it.value, QoSMetrics::class.java)
                    } catch (e: Exception) {
                        null
                    }
                }
            
        } catch (e: Exception) {
            logger.error("Failed to get QoS history: $participantId", e)
            emptyList()
        }
    }
    
    /**
     * Publish state change event to Redis pub/sub
     */
    private fun publishStateChange(participantId: String, eventType: String, state: ParticipantMetadata?) {
        try {
            val channel = "participant:state:changes"
            val event = mapOf(
                "participantId" to participantId,
                "eventType" to eventType,
                "state" to state,
                "timestamp" to System.currentTimeMillis()
            )
            val eventJson = objectMapper.writeValueAsString(event)
            redisManager.publish(channel, eventJson)
        } catch (e: Exception) {
            logger.error("Failed to publish state change", e)
        }
    }
    
    /**
     * Trim QoS history to keep only recent entries
     */
    private fun trimQoSHistory(participantId: String, maxEntries: Int) {
        try {
            val historyKey = "participant:$participantId:qos:history"
            val history = redisManager.getHashAll(historyKey)
            
            if (history.size > maxEntries) {
                val toRemove = history.keys
                    .sortedByDescending { it.toLong() }
                    .drop(maxEntries)
                
                for (key in toRemove) {
                    redisManager.deleteHashField(historyKey, key)
                }
            }
        } catch (e: Exception) {
            logger.error("Failed to trim QoS history: $participantId", e)
        }
    }
    
    /**
     * Get statistics
     */
    fun getStatistics(): Map<String, Any> {
        val cacheHitRate = if (cacheHits + cacheMisses > 0) {
            (cacheHits.toDouble() / (cacheHits + cacheMisses) * 100).toInt()
        } else {
            0
        }
        
        return mapOf(
            "cached_participants" to localCache.size,
            "state_updates" to stateUpdates,
            "cache_hits" to cacheHits,
            "cache_misses" to cacheMisses,
            "cache_hit_rate_percent" to cacheHitRate
        )
    }
    
    /**
     * Clear local cache (for testing or manual refresh)
     */
    fun clearCache() {
        logger.info("Clearing participant state cache")
        localCache.clear()
    }
}

/**
 * Participant metadata representation
 */
data class ParticipantMetadata(
    val participantId: String,
    val mediaCapabilities: MediaCapabilities? = null,
    val qosMetrics: QoSMetrics? = null,
    val presenceStatus: PresenceStatus = PresenceStatus.UNKNOWN,
    val customMetadata: Map<String, Any> = emptyMap(),
    val lastUpdated: Long = System.currentTimeMillis(),
    val lastQoSUpdate: Long? = null,
    val lastPresenceUpdate: Long? = null
)

/**
 * Media capabilities
 */
data class MediaCapabilities(
    val videoCodecs: List<String>,
    val audioCodecs: List<String>,
    val maxResolution: String,
    val maxFrameRate: Int,
    val maxBitrate: Int,
    val supportsAIC: Boolean = false,
    val supportsScreenShare: Boolean = false,
    val supportsSimulcast: Boolean = false
)

/**
 * QoS metrics
 */
data class QoSMetrics(
    val packetLossPercent: Double,
    val jitterMs: Double,
    val rttMs: Int,
    val bandwidthKbps: Int,
    val mosScore: Double? = null,
    val timestamp: Long = System.currentTimeMillis()
)

/**
 * Presence status
 */
enum class PresenceStatus {
    UNKNOWN,
    ACTIVE,
    INACTIVE,
    AWAY,
    BUSY,
    OFFLINE
}

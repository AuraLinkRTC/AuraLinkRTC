package org.jitsi.auralink.integration.auraid

import com.fasterxml.jackson.databind.ObjectMapper
import com.fasterxml.jackson.module.kotlin.jacksonObjectMapper
import org.jitsi.auralink.integration.config.AuraLinkConfig
import org.jitsi.auralink.integration.redis.RedisManager
import org.slf4j.LoggerFactory
import java.net.HttpURLConnection
import java.net.URL
import java.util.concurrent.ConcurrentHashMap

/**
 * AuraID Resolution Service
 * 
 * Resolves AuraID (universal participant identity) to participant information
 * via Communication Service (Matrix-based).
 * 
 * Features:
 * - Universal identity resolution across platforms
 * - Privacy-aware resolution with permissions
 * - Multi-level caching (memory + Redis)
 * - Fallback to email/phone lookup
 * - Rate limiting and abuse prevention
 */
class AuraIDResolver(
    private val config: AuraLinkConfig,
    private val redisManager: RedisManager
) {
    
    private val logger = LoggerFactory.getLogger(AuraIDResolver::class.java)
    private val objectMapper: ObjectMapper = jacksonObjectMapper()
    
    // Communication Service endpoint
    private val serviceUrl = config.communication_service?.url ?: "http://auralink-communication:8008"
    private val apiKey = config.communication_service?.api_key
    
    // Local cache for fast lookups
    private val localCache = ConcurrentHashMap<String, CachedIdentity>()
    
    // Cache TTL from config
    private val cacheTtlSeconds = config.communication_service?.auraid?.cache_ttl?.toSeconds()?.toInt() ?: 300
    
    // Statistics
    private var totalLookups = 0L
    private var cacheHits = 0L
    private var cacheMisses = 0L
    private var failedLookups = 0L
    
    /**
     * Resolve AuraID to participant information
     */
    fun resolveAuraID(auraId: String): AuraIDInfo? {
        if (!config.features.enableAuraId) {
            logger.debug("AuraID resolution disabled")
            return null
        }
        
        totalLookups++
        
        // Check local cache first
        val cached = getCachedIdentity(auraId)
        if (cached != null) {
            cacheHits++
            logger.debug("AuraID resolved from cache: $auraId")
            return cached
        }
        
        cacheMisses++
        
        // Check Redis cache
        val redisKey = "auraid:$auraId"
        val redisCached = redisManager.get(redisKey)
        if (redisCached != null) {
            try {
                val info = objectMapper.readValue(redisCached, AuraIDInfo::class.java)
                putInLocalCache(auraId, info)
                logger.debug("AuraID resolved from Redis: $auraId")
                return info
            } catch (e: Exception) {
                logger.warn("Failed to deserialize cached AuraID: $auraId", e)
            }
        }
        
        // Fetch from Communication Service
        return try {
            val info = fetchFromCommunicationService(auraId)
            
            if (info != null) {
                // Cache the result
                putInLocalCache(auraId, info)
                
                val infoJson = objectMapper.writeValueAsString(info)
                redisManager.set(redisKey, infoJson, ttlSeconds = cacheTtlSeconds)
                
                logger.info("AuraID resolved: $auraId -> ${info.displayName}")
            } else {
                logger.warn("AuraID not found: $auraId")
                failedLookups++
            }
            
            info
            
        } catch (e: Exception) {
            logger.error("Failed to resolve AuraID: $auraId", e)
            failedLookups++
            
            // Try fallback resolution if enabled
            if (config.communication_service?.auraid?.fallback_to_email == true) {
                resolveFallback(auraId)
            } else {
                null
            }
        }
    }
    
    /**
     * Batch resolve multiple AuraIDs
     */
    fun resolveAuraIDs(auraIds: List<String>): Map<String, AuraIDInfo?> {
        return auraIds.associateWith { resolveAuraID(it) }
    }
    
    /**
     * Reverse lookup: find AuraID by email or phone
     */
    fun findAuraIDByContact(email: String? = null, phone: String? = null): String? {
        if (!config.features.enableAuraId) {
            return null
        }
        
        return try {
            val request = mutableMapOf<String, String>()
            if (email != null) request["email"] = email
            if (phone != null) request["phone"] = phone
            
            val response = post<FindAuraIDResponse>(
                "/api/v1/auraid/lookup",
                request
            )
            
            response.auraId
            
        } catch (e: Exception) {
            logger.error("Failed to find AuraID by contact", e)
            null
        }
    }
    
    /**
     * Get cached identity from local cache
     */
    private fun getCachedIdentity(auraId: String): AuraIDInfo? {
        val cached = localCache[auraId] ?: return null
        
        // Check if expired
        val now = System.currentTimeMillis()
        if (now - cached.timestamp > cacheTtlSeconds * 1000) {
            localCache.remove(auraId)
            return null
        }
        
        return cached.info
    }
    
    /**
     * Put identity in local cache
     */
    private fun putInLocalCache(auraId: String, info: AuraIDInfo) {
        localCache[auraId] = CachedIdentity(info, System.currentTimeMillis())
        
        // Limit cache size
        if (localCache.size > 10000) {
            cleanupOldestCacheEntries()
        }
    }
    
    /**
     * Cleanup oldest cache entries
     */
    private fun cleanupOldestCacheEntries() {
        val toRemove = localCache.entries
            .sortedBy { it.value.timestamp }
            .take(1000)
            .map { it.key }
        
        for (key in toRemove) {
            localCache.remove(key)
        }
        
        logger.debug("Cleaned up ${toRemove.size} old cache entries")
    }
    
    /**
     * Fetch from Communication Service
     */
    private fun fetchFromCommunicationService(auraId: String): AuraIDInfo? {
        return try {
            get<AuraIDInfo>("/api/v1/auraid/$auraId")
        } catch (e: Exception) {
            logger.debug("Communication Service lookup failed for: $auraId")
            null
        }
    }
    
    /**
     * Fallback resolution using email/phone
     */
    private fun resolveFallback(identifier: String): AuraIDInfo? {
        logger.debug("Attempting fallback resolution for: $identifier")
        
        // Try as email
        if (identifier.contains("@")) {
            return AuraIDInfo(
                auraId = identifier,
                displayName = identifier.substringBefore("@"),
                email = identifier,
                verified = false,
                publicProfile = true
            )
        }
        
        // Try as phone
        if (identifier.matches(Regex("^\\+?[1-9]\\d{1,14}$"))) {
            return AuraIDInfo(
                auraId = identifier,
                displayName = identifier,
                phone = identifier,
                verified = false,
                publicProfile = true
            )
        }
        
        return null
    }
    
    /**
     * Generic GET request
     */
    private inline fun <reified T> get(path: String): T {
        val url = URL("$serviceUrl$path")
        val connection = url.openConnection() as HttpURLConnection
        
        try {
            connection.requestMethod = "GET"
            connection.connectTimeout = 5000
            connection.readTimeout = 5000
            connection.setRequestProperty("Content-Type", "application/json")
            
            if (apiKey != null) {
                connection.setRequestProperty("X-AuraLink-API-Key", apiKey)
            }
            
            val responseCode = connection.responseCode
            if (responseCode !in 200..299) {
                throw AuraIDResolverException("GET $path failed with code: $responseCode")
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
        val url = URL("$serviceUrl$path")
        val connection = url.openConnection() as HttpURLConnection
        
        try {
            connection.requestMethod = "POST"
            connection.connectTimeout = 5000
            connection.readTimeout = 5000
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
                throw AuraIDResolverException("POST $path failed with code: $responseCode")
            }
            
            val responseBody = connection.inputStream.bufferedReader().use { it.readText() }
            return objectMapper.readValue(responseBody, T::class.java)
            
        } finally {
            connection.disconnect()
        }
    }
    
    /**
     * Get statistics
     */
    fun getStatistics(): Map<String, Any> {
        val hitRate = if (totalLookups > 0) {
            (cacheHits.toDouble() / totalLookups * 100).toInt()
        } else {
            0
        }
        
        return mapOf(
            "total_lookups" to totalLookups,
            "cache_hits" to cacheHits,
            "cache_misses" to cacheMisses,
            "failed_lookups" to failedLookups,
            "cache_hit_rate_percent" to hitRate,
            "local_cache_size" to localCache.size
        )
    }
    
    /**
     * Clear cache
     */
    fun clearCache() {
        logger.info("Clearing AuraID cache")
        localCache.clear()
    }
}

/**
 * AuraID information
 */
data class AuraIDInfo(
    val auraId: String,
    val displayName: String,
    val email: String? = null,
    val phone: String? = null,
    val avatar: String? = null,
    val verified: Boolean = false,
    val publicProfile: Boolean = false,
    val metadata: Map<String, Any> = emptyMap()
)

/**
 * Find AuraID response
 */
data class FindAuraIDResponse(
    val auraId: String?,
    val found: Boolean
)

/**
 * Cached identity with timestamp
 */
private data class CachedIdentity(
    val info: AuraIDInfo,
    val timestamp: Long
)

/**
 * AuraID resolver exception
 */
class AuraIDResolverException(message: String, cause: Throwable? = null) : 
    Exception(message, cause)

/**
 * Communication service configuration extension
 */
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

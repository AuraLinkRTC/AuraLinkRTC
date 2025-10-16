package org.jitsi.auralink.integration.redis

import org.jitsi.auralink.integration.config.AuraLinkConfig
import org.slf4j.LoggerFactory
import redis.clients.jedis.Jedis
import redis.clients.jedis.JedisPool
import redis.clients.jedis.JedisPoolConfig
import redis.clients.jedis.exceptions.JedisException
import java.time.Duration

/**
 * Redis connection manager for AuraLink Ingress-Egress Service
 * Provides state synchronization and caching capabilities
 */
class RedisManager(private val config: AuraLinkConfig) {
    
    private val logger = LoggerFactory.getLogger(RedisManager::class.java)
    private var jedisPool: JedisPool? = null
    private val keyPrefix = config.redis.keyPrefix
    
    /**
     * Initialize Redis connection pool
     */
    fun initialize() {
        try {
            logger.info("Initializing Redis connection pool")
            
            val poolConfig = JedisPoolConfig().apply {
                maxTotal = config.redis.pool.maxTotal
                maxIdle = config.redis.pool.maxIdle
                minIdle = config.redis.pool.minIdle
                
                // Test on borrow to ensure connection validity
                testOnBorrow = true
                testOnReturn = false
                testWhileIdle = true
                
                // Eviction policy
                minEvictableIdleTime = Duration.ofSeconds(60)
                timeBetweenEvictionRuns = Duration.ofSeconds(30)
                numTestsPerEvictionRun = 3
                
                // Block when pool exhausted
                blockWhenExhausted = true
                maxWait = Duration.ofSeconds(2)
            }
            
            jedisPool = if (config.redis.password != null) {
                JedisPool(
                    poolConfig,
                    config.redis.host,
                    config.redis.port,
                    config.redis.timeout,
                    config.redis.password,
                    config.redis.database
                )
            } else {
                JedisPool(
                    poolConfig,
                    config.redis.host,
                    config.redis.port,
                    config.redis.timeout
                )
            }
            
            // Test connection
            testConnection()
            
            logger.info("Redis connection pool initialized successfully")
        } catch (e: Exception) {
            logger.error("Failed to initialize Redis connection pool", e)
            throw RedisInitializationException("Redis initialization failed", e)
        }
    }
    
    /**
     * Test Redis connectivity
     */
    private fun testConnection() {
        try {
            withRedis { jedis ->
                val response = jedis.ping()
                if (response == "PONG") {
                    logger.info("Redis connection test successful")
                } else {
                    throw RedisConnectionException("Unexpected ping response: $response")
                }
            }
        } catch (e: JedisException) {
            logger.error("Redis connection test failed", e)
            throw RedisConnectionException("Failed to connect to Redis", e)
        }
    }
    
    /**
     * Execute operation with Redis connection from pool
     */
    private fun <T> withRedis(operation: (Jedis) -> T): T {
        val pool = jedisPool ?: throw IllegalStateException("Redis not initialized")
        
        return pool.resource.use { jedis ->
            operation(jedis)
        }
    }
    
    /**
     * Set a key-value pair with optional TTL
     */
    fun set(key: String, value: String, ttlSeconds: Int? = null): Boolean {
        return try {
            withRedis { jedis ->
                val fullKey = keyPrefix + key
                if (ttlSeconds != null) {
                    jedis.setex(fullKey, ttlSeconds.toLong(), value)
                } else {
                    jedis.set(fullKey, value)
                }
                true
            }
        } catch (e: JedisException) {
            logger.error("Failed to set key: $key", e)
            false
        }
    }
    
    /**
     * Get value for a key
     */
    fun get(key: String): String? {
        return try {
            withRedis { jedis ->
                jedis.get(keyPrefix + key)
            }
        } catch (e: JedisException) {
            logger.error("Failed to get key: $key", e)
            null
        }
    }
    
    /**
     * Delete a key
     */
    fun delete(key: String): Boolean {
        return try {
            withRedis { jedis ->
                jedis.del(keyPrefix + key) > 0
            }
        } catch (e: JedisException) {
            logger.error("Failed to delete key: $key", e)
            false
        }
    }
    
    /**
     * Check if key exists
     */
    fun exists(key: String): Boolean {
        return try {
            withRedis { jedis ->
                jedis.exists(keyPrefix + key)
            }
        } catch (e: JedisException) {
            logger.error("Failed to check key existence: $key", e)
            false
        }
    }
    
    /**
     * Set expiration on a key
     */
    fun expire(key: String, seconds: Int): Boolean {
        return try {
            withRedis { jedis ->
                jedis.expire(keyPrefix + key, seconds.toLong()) > 0
            }
        } catch (e: JedisException) {
            logger.error("Failed to set expiration on key: $key", e)
            false
        }
    }
    
    /**
     * Add value to a set
     */
    fun addToSet(setKey: String, value: String): Boolean {
        return try {
            withRedis { jedis ->
                jedis.sadd(keyPrefix + setKey, value) > 0
            }
        } catch (e: JedisException) {
            logger.error("Failed to add to set: $setKey", e)
            false
        }
    }
    
    /**
     * Remove value from a set
     */
    fun removeFromSet(setKey: String, value: String): Boolean {
        return try {
            withRedis { jedis ->
                jedis.srem(keyPrefix + setKey, value) > 0
            }
        } catch (e: JedisException) {
            logger.error("Failed to remove from set: $setKey", e)
            false
        }
    }
    
    /**
     * Get all members of a set
     */
    fun getSetMembers(setKey: String): Set<String> {
        return try {
            withRedis { jedis ->
                jedis.smembers(keyPrefix + setKey)
            }
        } catch (e: JedisException) {
            logger.error("Failed to get set members: $setKey", e)
            emptySet()
        }
    }
    
    /**
     * Add entry to a hash
     */
    fun setHashField(hashKey: String, field: String, value: String): Boolean {
        return try {
            withRedis { jedis ->
                jedis.hset(keyPrefix + hashKey, field, value) >= 0
            }
        } catch (e: JedisException) {
            logger.error("Failed to set hash field: $hashKey.$field", e)
            false
        }
    }
    
    /**
     * Get field from a hash
     */
    fun getHashField(hashKey: String, field: String): String? {
        return try {
            withRedis { jedis ->
                jedis.hget(keyPrefix + hashKey, field)
            }
        } catch (e: JedisException) {
            logger.error("Failed to get hash field: $hashKey.$field", e)
            null
        }
    }
    
    /**
     * Get all fields from a hash
     */
    fun getHashAll(hashKey: String): Map<String, String> {
        return try {
            withRedis { jedis ->
                jedis.hgetAll(keyPrefix + hashKey)
            }
        } catch (e: JedisException) {
            logger.error("Failed to get hash: $hashKey", e)
            emptyMap()
        }
    }
    
    /**
     * Delete field from a hash
     */
    fun deleteHashField(hashKey: String, field: String): Boolean {
        return try {
            withRedis { jedis ->
                jedis.hdel(keyPrefix + hashKey, field) > 0
            }
        } catch (e: JedisException) {
            logger.error("Failed to delete hash field: $hashKey.$field", e)
            false
        }
    }
    
    /**
     * Publish message to a channel
     */
    fun publish(channel: String, message: String): Boolean {
        return try {
            withRedis { jedis ->
                jedis.publish(keyPrefix + channel, message) >= 0
            }
        } catch (e: JedisException) {
            logger.error("Failed to publish to channel: $channel", e)
            false
        }
    }
    
    /**
     * Increment a counter
     */
    fun increment(key: String): Long? {
        return try {
            withRedis { jedis ->
                jedis.incr(keyPrefix + key)
            }
        } catch (e: JedisException) {
            logger.error("Failed to increment key: $key", e)
            null
        }
    }
    
    /**
     * Decrement a counter
     */
    fun decrement(key: String): Long? {
        return try {
            withRedis { jedis ->
                jedis.decr(keyPrefix + key)
            }
        } catch (e: JedisException) {
            logger.error("Failed to decrement key: $key", e)
            null
        }
    }
    
    /**
     * Get keys matching a pattern
     */
    fun getKeys(pattern: String): Set<String> {
        return try {
            withRedis { jedis ->
                jedis.keys(keyPrefix + pattern).map { 
                    it.removePrefix(keyPrefix) 
                }.toSet()
            }
        } catch (e: JedisException) {
            logger.error("Failed to get keys with pattern: $pattern", e)
            emptySet()
        }
    }
    
    /**
     * Check Redis health
     */
    fun checkHealth(): Boolean {
        return try {
            withRedis { jedis ->
                jedis.ping() == "PONG"
            }
        } catch (e: Exception) {
            logger.error("Redis health check failed", e)
            false
        }
    }
    
    /**
     * Get pool statistics
     */
    fun getPoolStats(): Map<String, Any> {
        val pool = jedisPool ?: return emptyMap()
        
        return mapOf(
            "active_connections" to pool.numActive,
            "idle_connections" to pool.numIdle,
            "waiters" to pool.numWaiters,
            "max_total" to pool.maxTotal,
            "max_idle" to pool.maxIdle
        )
    }
    
    /**
     * Clear all keys with the service prefix (use with caution!)
     */
    fun clearAll(): Boolean {
        return try {
            withRedis { jedis ->
                val keys = jedis.keys("$keyPrefix*")
                if (keys.isNotEmpty()) {
                    jedis.del(*keys.toTypedArray())
                }
                true
            }
        } catch (e: JedisException) {
            logger.error("Failed to clear all keys", e)
            false
        }
    }
    
    /**
     * Shutdown Redis connection pool
     */
    fun shutdown() {
        logger.info("Shutting down Redis connection pool")
        jedisPool?.close()
        jedisPool = null
        logger.info("Redis connection pool closed")
    }
}

/**
 * Redis initialization exception
 */
class RedisInitializationException(message: String, cause: Throwable? = null) : 
    Exception(message, cause)

/**
 * Redis connection exception
 */
class RedisConnectionException(message: String, cause: Throwable? = null) : 
    Exception(message, cause)

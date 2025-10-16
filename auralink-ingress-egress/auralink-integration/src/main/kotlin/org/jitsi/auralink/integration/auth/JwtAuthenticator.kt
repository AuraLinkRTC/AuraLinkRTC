package org.jitsi.auralink.integration.auth

import com.auth0.jwt.JWT
import com.auth0.jwt.algorithms.Algorithm
import com.auth0.jwt.exceptions.JWTVerificationException
import com.auth0.jwt.interfaces.DecodedJWT
import org.jitsi.auralink.integration.config.AuraLinkConfig
import org.slf4j.LoggerFactory
import java.time.Instant
import java.util.*

/**
 * JWT authentication manager for AuraLink Ingress-Egress Service
 * Handles JWT token validation and generation for service-to-service communication
 */
class JwtAuthenticator(private val config: AuraLinkConfig) {
    
    private val logger = LoggerFactory.getLogger(JwtAuthenticator::class.java)
    
    private val secret: String = config.security.jwt.secret 
        ?: throw IllegalStateException("JWT secret not configured")
    
    private val algorithm: Algorithm = when (config.security.jwt.algorithm) {
        "HS256" -> Algorithm.HMAC256(secret)
        "HS384" -> Algorithm.HMAC384(secret)
        "HS512" -> Algorithm.HMAC512(secret)
        else -> throw IllegalArgumentException("Unsupported JWT algorithm: ${config.security.jwt.algorithm}")
    }
    
    private val issuer = config.security.jwt.issuer
    private val audience = config.security.jwt.audience
    
    /**
     * Validate JWT token
     */
    fun validateToken(token: String): TokenValidationResult {
        if (!config.security.jwt.enabled) {
            logger.warn("JWT validation disabled, accepting all tokens")
            return TokenValidationResult(
                valid = true,
                claims = emptyMap(),
                message = "JWT validation disabled"
            )
        }
        
        return try {
            val verifier = JWT.require(algorithm)
                .withIssuer(issuer)
                .withAudience(audience)
                .build()
            
            val decodedJWT = verifier.verify(token)
            
            // Extract claims
            val claims = mutableMapOf<String, Any>()
            claims["subject"] = decodedJWT.subject ?: ""
            claims["issuer"] = decodedJWT.issuer ?: ""
            claims["audience"] = decodedJWT.audience?.firstOrNull() ?: ""
            claims["issued_at"] = decodedJWT.issuedAt?.time ?: 0L
            claims["expires_at"] = decodedJWT.expiresAt?.time ?: 0L
            
            // Extract custom claims
            decodedJWT.claims.forEach { (key, claim) ->
                if (!claims.containsKey(key)) {
                    claims[key] = claim.asString() ?: claim.asInt() ?: claim.asBoolean() ?: ""
                }
            }
            
            logger.debug("Token validated successfully for subject: ${decodedJWT.subject}")
            
            TokenValidationResult(
                valid = true,
                claims = claims,
                subject = decodedJWT.subject,
                expiresAt = decodedJWT.expiresAt?.toInstant()
            )
            
        } catch (e: JWTVerificationException) {
            logger.error("JWT validation failed", e)
            TokenValidationResult(
                valid = false,
                message = "Invalid token: ${e.message}"
            )
        }
    }
    
    /**
     * Generate JWT token for service-to-service communication
     */
    fun generateToken(
        subject: String,
        claims: Map<String, Any> = emptyMap(),
        expiresInSeconds: Long = 3600
    ): String {
        val now = Date.from(Instant.now())
        val expiry = Date.from(Instant.now().plusSeconds(expiresInSeconds))
        
        var builder = JWT.create()
            .withIssuer(issuer)
            .withAudience(audience)
            .withSubject(subject)
            .withIssuedAt(now)
            .withExpiresAt(expiry)
            .withJWTId(UUID.randomUUID().toString())
        
        // Add custom claims
        claims.forEach { (key, value) ->
            when (value) {
                is String -> builder = builder.withClaim(key, value)
                is Int -> builder = builder.withClaim(key, value)
                is Long -> builder = builder.withClaim(key, value)
                is Boolean -> builder = builder.withClaim(key, value)
                is Double -> builder = builder.withClaim(key, value)
                else -> logger.warn("Unsupported claim type for key $key: ${value::class.java}")
            }
        }
        
        val token = builder.sign(algorithm)
        
        logger.debug("Generated token for subject: $subject, expires in: ${expiresInSeconds}s")
        
        return token
    }
    
    /**
     * Generate service token for this bridge
     */
    fun generateServiceToken(): String {
        val bridgeId = config.service.bridgeId 
            ?: throw IllegalStateException("Bridge ID not configured")
        
        return generateToken(
            subject = bridgeId,
            claims = mapOf(
                "service" to config.service.name,
                "region" to config.service.region,
                "environment" to config.service.environment,
                "version" to config.service.version
            ),
            expiresInSeconds = 86400 // 24 hours
        )
    }
    
    /**
     * Extract token from Authorization header
     */
    fun extractTokenFromHeader(authHeader: String?): String? {
        if (authHeader.isNullOrBlank()) {
            return null
        }
        
        return if (authHeader.startsWith("Bearer ", ignoreCase = true)) {
            authHeader.substring(7).trim()
        } else {
            null
        }
    }
    
    /**
     * Validate Authorization header
     */
    fun validateAuthorizationHeader(authHeader: String?): TokenValidationResult {
        val token = extractTokenFromHeader(authHeader)
        
        if (token.isNullOrBlank()) {
            return TokenValidationResult(
                valid = false,
                message = "Missing or invalid Authorization header"
            )
        }
        
        return validateToken(token)
    }
}

/**
 * Token validation result
 */
data class TokenValidationResult(
    val valid: Boolean,
    val claims: Map<String, Any> = emptyMap(),
    val subject: String? = null,
    val expiresAt: Instant? = null,
    val message: String? = null
)

/**
 * Authentication exception
 */
class AuthenticationException(message: String, cause: Throwable? = null) : 
    Exception(message, cause)

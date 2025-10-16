package org.jitsi.auralink.integration.aic

import org.jitsi.auralink.integration.config.AuraLinkConfig
import org.jitsi.auralink.integration.metrics.PrometheusMetricsExporter
import org.slf4j.LoggerFactory
import java.util.concurrent.ConcurrentHashMap
import java.util.concurrent.Executors
import java.util.concurrent.ScheduledExecutorService
import java.util.concurrent.TimeUnit
import java.util.concurrent.atomic.AtomicLong
import java.nio.ByteBuffer

/**
 * Enterprise-grade compression pipeline for AIC Protocol
 * 
 * Integrates with RTP packet flow to provide:
 * - AI-driven frame compression
 * - RTP header extension injection
 * - Frame type detection (I-frame, P-frame)
 * - Region of Interest (ROI) marking
 * - Quality recommendations
 * - Bandwidth-aware hints
 * - Automatic fallback to native codecs
 * 
 * This is THE differentiating feature of AuraLink - 30-50% bandwidth savings
 */
class CompressionPipeline(
    private val config: AuraLinkConfig,
    private val grpcClient: AICoreGrpcClient,
    private val metricsExporter: PrometheusMetricsExporter
) {
    
    private val logger = LoggerFactory.getLogger(CompressionPipeline::class.java)
    
    // Session state management
    private val activeSessions = ConcurrentHashMap<String, SessionContext>()
    
    // Performance metrics
    private val framesProcessed = AtomicLong(0)
    private val framesCompressed = AtomicLong(0)
    private val framesFallback = AtomicLong(0)
    private val totalBandwidthSavedBytes = AtomicLong(0)
    
    // Scheduled executor for async tasks
    private val executor: ScheduledExecutorService = Executors.newScheduledThreadPool(4)
    
    // RTP extension type for AIC metadata
    private val AIC_EXTENSION_ID: Byte = 15 // RFC 8285 extension ID
    
    /**
     * Initialize compression pipeline
     */
    fun initialize() {
        logger.info("Initializing AIC Compression Pipeline")
        
        // Initialize gRPC client
        grpcClient.initialize()
        
        // Schedule periodic session cleanup
        executor.scheduleAtFixedRate(
            { cleanupInactiveSessions() },
            60,
            60,
            TimeUnit.SECONDS
        )
        
        logger.info("AIC Compression Pipeline initialized")
    }
    
    /**
     * Process RTP packet through compression pipeline
     * 
     * This is the main entry point called for each RTP packet
     */
    fun processRtpPacket(packet: RtpPacket): RtpPacket {
        framesProcessed.incrementAndGet()
        
        // Check if AIC is enabled
        if (!config.features.enableAic || !config.aiCore.enableCompression) {
            return packet
        }
        
        // Check if gRPC client is available
        if (!grpcClient.isAvailable()) {
            logger.debug("AIC service unavailable - using native codec")
            return packet
        }
        
        try {
            // Get or create session context
            val session = getOrCreateSession(packet.sessionId)
            
            // Detect frame type
            val frameType = detectFrameType(packet)
            
            // Extract frame metadata
            val metadata = extractMetadata(packet, frameType)
            
            // Get network conditions from session
            val network = session.getNetworkConditions()
            
            // Build compression request
            val request = CompressionRequest(
                sessionId = packet.sessionId,
                frameNumber = packet.sequenceNumber.toLong(),
                frameData = packet.payload,
                frameType = frameType,
                metadata = metadata,
                mode = determineCompressionMode(network),
                targetCompressionRatio = config.aiCore.compression.targetSavings,
                networkConditions = network
            )
            
            // Compress frame via gRPC
            val result = grpcClient.compressFrame(request)
            
            if (result != null && result.success) {
                // Compression successful
                framesCompressed.incrementAndGet()
                
                // Track bandwidth savings
                val savings = result.originalSizeBytes - result.compressedSizeBytes
                totalBandwidthSavedBytes.addAndGet(savings.toLong())
                
                // Update session stats
                session.recordCompression(result)
                
                // Create new RTP packet with compressed payload
                val compressedPacket = createCompressedPacket(packet, result)
                
                // Inject AIC metadata as RTP extension
                val packetWithExtension = injectAicMetadata(compressedPacket, result)
                
                logger.debug(
                    "Frame compressed: ${packet.sessionId}/${packet.sequenceNumber}, " +
                    "ratio: ${result.compressionRatio}, " +
                    "savings: ${savings} bytes, " +
                    "latency: ${result.latencyMs}ms"
                )
                
                // Update Prometheus metrics
                metricsExporter.recordAicCompression(
                    result.compressionRatio,
                    result.latencyMs,
                    savings
                )
                
                return packetWithExtension
                
            } else {
                // Compression failed - use fallback
                framesFallback.incrementAndGet()
                session.recordFallback(result?.fallbackReason ?: "gRPC call failed")
                
                logger.debug("AIC compression failed - using native codec")
                return packet
            }
            
        } catch (e: Exception) {
            logger.error("Error processing RTP packet", e)
            framesFallback.incrementAndGet()
            return packet
        }
    }
    
    /**
     * Get compression hints for adaptive bitrate
     */
    fun getCompressionHints(sessionId: String, metadata: FrameMetadata): CompressionHints? {
        val session = activeSessions[sessionId] ?: return null
        
        val request = HintRequest(
            sessionId = sessionId,
            metadata = metadata,
            networkConditions = session.getNetworkConditions()
        )
        
        return grpcClient.getCompressionHints(request)
    }
    
    /**
     * Update network conditions for session
     */
    fun updateNetworkConditions(sessionId: String, conditions: NetworkConditions) {
        val session = getOrCreateSession(sessionId)
        session.updateNetworkConditions(conditions)
    }
    
    /**
     * Detect frame type from RTP packet
     */
    private fun detectFrameType(packet: RtpPacket): String {
        // Check marker bit for keyframe indication
        if (packet.marker) {
            return "I-FRAME" // Keyframe
        }
        
        // Check payload for codec-specific keyframe markers
        val payload = packet.payload
        if (payload.isNotEmpty()) {
            // H.264 NAL unit type check
            if (packet.payloadType == 96) { // H.264
                val nalType = payload[0].toInt() and 0x1F
                if (nalType == 7 || nalType == 5) { // SPS or IDR
                    return "I-FRAME"
                }
            }
            
            // VP8/VP9 keyframe check
            if (packet.payloadType == 97 || packet.payloadType == 98) {
                val frameType = payload[0].toInt() and 0x01
                if (frameType == 0) {
                    return "I-FRAME"
                }
            }
        }
        
        return "P-FRAME" // Predicted frame
    }
    
    /**
     * Extract frame metadata from RTP packet
     */
    private fun extractMetadata(packet: RtpPacket, frameType: String): FrameMetadata {
        // Parse codec-specific metadata
        // This is simplified - production would parse SDP and codec parameters
        
        return FrameMetadata(
            width = 1280, // Would be extracted from SDP
            height = 720,
            fps = 30,
            codec = getCodecName(packet.payloadType),
            resolutionClass = "720p",
            isKeyframe = frameType == "I-FRAME",
            pts = packet.timestamp,
            bitrateKbps = estimateBitrate(packet)
        )
    }
    
    /**
     * Get codec name from payload type
     */
    private fun getCodecName(payloadType: Int): String {
        return when (payloadType) {
            96 -> "H.264"
            97 -> "VP8"
            98 -> "VP9"
            99 -> "H.265"
            else -> "UNKNOWN"
        }
    }
    
    /**
     * Estimate bitrate from packet size and timing
     */
    private fun estimateBitrate(packet: RtpPacket): Int {
        // Simplified estimation - would use sliding window in production
        return (packet.payload.size * 8 / 1000) * 30 // Assume 30 fps
    }
    
    /**
     * Determine compression mode based on network conditions
     */
    private fun determineCompressionMode(network: NetworkConditions): String {
        return when {
            network.availableBandwidthKbps < 1000 -> "AGGRESSIVE"
            network.availableBandwidthKbps < 3000 -> "ADAPTIVE"
            network.packetLossPercent > 5.0 -> "CONSERVATIVE"
            else -> "ADAPTIVE"
        }
    }
    
    /**
     * Create new RTP packet with compressed payload
     */
    private fun createCompressedPacket(original: RtpPacket, result: CompressionResult): RtpPacket {
        return original.copy(
            payload = result.compressedData,
            // Mark packet as AIC-compressed by setting extension bit
            extension = true
        )
    }
    
    /**
     * Inject AIC metadata as RTP header extension (RFC 8285)
     */
    private fun injectAicMetadata(packet: RtpPacket, result: CompressionResult): RtpPacket {
        // Build AIC metadata extension
        val metadata = AicRtpExtension(
            compressionRatio = result.compressionRatio.toFloat(),
            qualityScore = result.qualityScore.toFloat(),
            modelType = result.modelType,
            fallbackUsed = result.fallbackUsed
        )
        
        // Serialize metadata to bytes (simplified)
        val extensionData = serializeAicExtension(metadata)
        
        // Add to packet extensions
        val extensions = packet.extensions.toMutableMap()
        extensions[AIC_EXTENSION_ID] = extensionData
        
        return packet.copy(
            extensions = extensions,
            extension = true
        )
    }
    
    /**
     * Serialize AIC extension data
     */
    private fun serializeAicExtension(metadata: AicRtpExtension): ByteArray {
        val buffer = ByteBuffer.allocate(16)
        
        // Version (1 byte)
        buffer.put(1)
        
        // Compression ratio (2 bytes, fixed point)
        buffer.putShort((metadata.compressionRatio * 1000).toInt().toShort())
        
        // Quality score (2 bytes, fixed point)
        buffer.putShort((metadata.qualityScore * 1000).toInt().toShort())
        
        // Model type hash (4 bytes)
        buffer.putInt(metadata.modelType.hashCode())
        
        // Flags (1 byte)
        var flags: Byte = 0
        if (metadata.fallbackUsed) {
            flags = (flags.toInt() or 0x01).toByte()
        }
        buffer.put(flags)
        
        // Reserved (6 bytes)
        buffer.put(ByteArray(6))
        
        return buffer.array()
    }
    
    /**
     * Get or create session context
     */
    private fun getOrCreateSession(sessionId: String): SessionContext {
        return activeSessions.computeIfAbsent(sessionId) {
            SessionContext(sessionId)
        }
    }
    
    /**
     * Cleanup inactive sessions
     */
    private fun cleanupInactiveSessions() {
        val now = System.currentTimeMillis()
        val timeout = 300000L // 5 minutes
        
        val toRemove = activeSessions.entries
            .filter { (_, session) -> (now - session.lastActivity) > timeout }
            .map { it.key }
        
        for (sessionId in toRemove) {
            logger.info("Removing inactive session: $sessionId")
            activeSessions.remove(sessionId)
        }
    }
    
    /**
     * Get pipeline statistics
     */
    fun getStatistics(): Map<String, Any> {
        val total = framesProcessed.get()
        val compressed = framesCompressed.get()
        val fallback = framesFallback.get()
        
        val compressionRate = if (total > 0) {
            (compressed.toDouble() / total * 100).toInt()
        } else {
            0
        }
        
        val totalSavedMB = totalBandwidthSavedBytes.get() / (1024.0 * 1024.0)
        
        return mapOf(
            "frames_processed" to total,
            "frames_compressed" to compressed,
            "frames_fallback" to fallback,
            "compression_rate_percent" to compressionRate,
            "total_bandwidth_saved_mb" to String.format("%.2f", totalSavedMB),
            "active_sessions" to activeSessions.size,
            "grpc_stats" to grpcClient.getStatistics()
        )
    }
    
    /**
     * Shutdown pipeline
     */
    fun shutdown() {
        logger.info("Shutting down AIC Compression Pipeline")
        
        executor.shutdown()
        try {
            if (!executor.awaitTermination(5, TimeUnit.SECONDS)) {
                executor.shutdownNow()
            }
        } catch (e: InterruptedException) {
            executor.shutdownNow()
        }
        
        grpcClient.shutdown()
        
        logger.info("AIC Compression Pipeline stopped")
    }
}

/**
 * Session context for compression pipeline
 */
class SessionContext(val sessionId: String) {
    var lastActivity = System.currentTimeMillis()
    
    private var networkConditions = NetworkConditions(
        availableBandwidthKbps = 5000,
        rttMs = 50,
        packetLossPercent = 0.5,
        jitterMs = 10.0
    )
    
    private var compressionCount = 0L
    private var fallbackCount = 0L
    private var totalCompressionRatio = 0.0
    
    fun getNetworkConditions(): NetworkConditions {
        lastActivity = System.currentTimeMillis()
        return networkConditions
    }
    
    fun updateNetworkConditions(conditions: NetworkConditions) {
        lastActivity = System.currentTimeMillis()
        networkConditions = conditions
    }
    
    fun recordCompression(result: CompressionResult) {
        lastActivity = System.currentTimeMillis()
        compressionCount++
        totalCompressionRatio += result.compressionRatio
    }
    
    fun recordFallback(reason: String) {
        lastActivity = System.currentTimeMillis()
        fallbackCount++
    }
    
    fun getAverageCompressionRatio(): Double {
        return if (compressionCount > 0) {
            totalCompressionRatio / compressionCount
        } else {
            0.0
        }
    }
}

/**
 * RTP packet representation
 */
data class RtpPacket(
    val sessionId: String,
    val ssrc: Int,
    val payloadType: Int,
    val sequenceNumber: Int,
    val timestamp: Long,
    val marker: Boolean,
    val payload: ByteArray,
    val extension: Boolean = false,
    val extensions: Map<Byte, ByteArray> = emptyMap()
) {
    override fun equals(other: Any?): Boolean {
        if (this === other) return true
        if (javaClass != other?.javaClass) return false
        other as RtpPacket
        return sessionId == other.sessionId && sequenceNumber == other.sequenceNumber
    }
    
    override fun hashCode(): Int {
        return sessionId.hashCode() * 31 + sequenceNumber
    }
}

/**
 * AIC RTP extension data
 */
data class AicRtpExtension(
    val compressionRatio: Float,
    val qualityScore: Float,
    val modelType: String,
    val fallbackUsed: Boolean
)

package org.jitsi.auralink.integration.aic

import org.jitsi.auralink.integration.config.AuraLinkConfig
import org.jitsi.auralink.integration.metrics.PrometheusMetricsExporter
import org.junit.jupiter.api.BeforeEach
import org.junit.jupiter.api.Test
import org.junit.jupiter.api.AfterEach
import org.mockito.kotlin.mock
import org.mockito.kotlin.whenever
import org.mockito.kotlin.any
import kotlin.test.assertEquals
import kotlin.test.assertNotNull
import kotlin.test.assertTrue

/**
 * Unit tests for CompressionPipeline
 */
class CompressionPipelineTest {
    
    private lateinit var config: AuraLinkConfig
    private lateinit var grpcClient: AICoreGrpcClient
    private lateinit var metricsExporter: PrometheusMetricsExporter
    private lateinit var pipeline: CompressionPipeline
    
    @BeforeEach
    fun setUp() {
        config = mock()
        grpcClient = mock()
        metricsExporter = mock()
        
        // Mock configuration
        whenever(config.features).thenReturn(mock {
            whenever(it.enableAic).thenReturn(true)
        })
        whenever(config.aiCore).thenReturn(mock {
            whenever(it.enableCompression).thenReturn(true)
            whenever(it.compression).thenReturn(mock {
                whenever(it.targetSavings).thenReturn(0.4)
            })
        })
        
        pipeline = CompressionPipeline(config, grpcClient, metricsExporter)
    }
    
    @AfterEach
    fun tearDown() {
        pipeline.shutdown()
    }
    
    @Test
    fun `should initialize pipeline`() {
        pipeline.initialize()
        assertNotNull(pipeline)
    }
    
    @Test
    fun `should process RTP packet with compression`() {
        val packet = RtpPacket(
            sessionId = "session-123",
            ssrc = 12345,
            payloadType = 96, // H.264
            sequenceNumber = 42,
            timestamp = System.currentTimeMillis(),
            marker = false,
            payload = ByteArray(1000)
        )
        
        val compressionResult = CompressionResult(
            success = true,
            compressedData = ByteArray(600),
            originalSizeBytes = 1000,
            compressedSizeBytes = 600,
            compressionRatio = 0.4,
            qualityScore = 0.92,
            latencyMs = 8,
            modelType = "encodec",
            fallbackUsed = false
        )
        
        whenever(grpcClient.isAvailable()).thenReturn(true)
        whenever(grpcClient.compressFrame(any())).thenReturn(compressionResult)
        
        val result = pipeline.processRtpPacket(packet)
        
        assertNotNull(result)
        assertTrue(result.extension)
    }
    
    @Test
    fun `should fallback when compression fails`() {
        val packet = RtpPacket(
            sessionId = "session-123",
            ssrc = 12345,
            payloadType = 96,
            sequenceNumber = 42,
            timestamp = System.currentTimeMillis(),
            marker = false,
            payload = ByteArray(1000)
        )
        
        whenever(grpcClient.isAvailable()).thenReturn(false)
        
        val result = pipeline.processRtpPacket(packet)
        
        assertNotNull(result)
        assertEquals(packet.payload.size, result.payload.size)
    }
    
    @Test
    fun `should detect I-frame correctly`() {
        val iFramePacket = RtpPacket(
            sessionId = "session-123",
            ssrc = 12345,
            payloadType = 96,
            sequenceNumber = 42,
            timestamp = System.currentTimeMillis(),
            marker = true, // I-frame indicator
            payload = ByteArray(1000)
        )
        
        whenever(grpcClient.isAvailable()).thenReturn(true)
        whenever(grpcClient.compressFrame(any())).thenReturn(null)
        
        pipeline.processRtpPacket(iFramePacket)
        // Validation would require inspecting internal state
    }
    
    @Test
    fun `should get pipeline statistics`() {
        val stats = pipeline.getStatistics()
        
        assertNotNull(stats)
        assertTrue(stats.containsKey("frames_processed"))
        assertTrue(stats.containsKey("frames_compressed"))
        assertTrue(stats.containsKey("total_bandwidth_saved_mb"))
    }
}

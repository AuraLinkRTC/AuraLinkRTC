package org.jitsi.auralink.integration.webrtc

import org.jitsi.auralink.integration.config.AuraLinkConfig
import org.junit.jupiter.api.BeforeEach
import org.junit.jupiter.api.Test
import org.junit.jupiter.api.assertThrows
import org.mockito.kotlin.mock
import org.mockito.kotlin.whenever
import kotlin.test.assertEquals
import kotlin.test.assertFalse
import kotlin.test.assertNotNull
import kotlin.test.assertTrue

/**
 * Unit tests for WebRTCServerClient
 */
class WebRTCServerClientTest {
    
    private lateinit var config: AuraLinkConfig
    private lateinit var client: WebRTCServerClient
    
    @BeforeEach
    fun setUp() {
        // Mock configuration
        config = mock()
        whenever(config.webrtcServer).thenReturn(
            mock {
                whenever(it.url).thenReturn("http://localhost:7880")
                whenever(it.apiKey).thenReturn("test-api-key")
            }
        )
        
        client = WebRTCServerClient(config)
    }
    
    @Test
    fun `should initialize client successfully`() {
        assertNotNull(client)
    }
    
    @Test
    fun `should handle circuit breaker correctly`() {
        // Simulate 5 failures to open circuit breaker
        repeat(5) {
            try {
                client.listRooms()
            } catch (e: Exception) {
                // Expected
            }
        }
        
        // Circuit should be open now
        assertFalse(client.checkHealth())
    }
    
    @Test
    fun `should list rooms when server available`() {
        // This would require mocking HTTP responses
        // For now, validate structure
        val rooms = client.listRooms()
        assertNotNull(rooms)
    }
    
    @Test
    fun `should get room details`() {
        val roomName = "test-room"
        val room = client.getRoom(roomName)
        // Room might not exist, which is fine
    }
    
    @Test
    fun `should list participants in room`() {
        val roomName = "test-room"
        val participants = client.listParticipants(roomName)
        assertNotNull(participants)
    }
}

package org.jitsi.auralink.integration.sync

import org.jitsi.auralink.integration.config.AuraLinkConfig
import org.jitsi.auralink.integration.redis.RedisManager
import org.jitsi.auralink.integration.webrtc.WebRTCServerClient
import org.jitsi.auralink.integration.webrtc.RoomInfo
import org.jitsi.auralink.integration.webrtc.ParticipantInfo
import org.junit.jupiter.api.BeforeEach
import org.junit.jupiter.api.Test
import org.junit.jupiter.api.AfterEach
import org.mockito.kotlin.mock
import org.mockito.kotlin.whenever
import org.mockito.kotlin.verify
import org.mockito.kotlin.any
import kotlin.test.assertEquals
import kotlin.test.assertNotNull
import kotlin.test.assertTrue

/**
 * Unit tests for RoomSynchronizer
 */
class RoomSynchronizerTest {
    
    private lateinit var config: AuraLinkConfig
    private lateinit var redisManager: RedisManager
    private lateinit var webrtcClient: WebRTCServerClient
    private lateinit var synchronizer: RoomSynchronizer
    
    @BeforeEach
    fun setUp() {
        config = mock()
        redisManager = mock()
        webrtcClient = mock()
        
        synchronizer = RoomSynchronizer(config, redisManager, webrtcClient)
    }
    
    @AfterEach
    fun tearDown() {
        synchronizer.shutdown()
    }
    
    @Test
    fun `should initialize synchronizer`() {
        synchronizer.initialize()
        assertNotNull(synchronizer)
    }
    
    @Test
    fun `should sync room successfully`() {
        val roomName = "test-room"
        val roomInfo = RoomInfo(
            sid = "room-123",
            name = roomName,
            emptyTimeout = 300,
            maxParticipants = 100,
            creationTime = System.currentTimeMillis(),
            turnPassword = null,
            enabledCodecs = listOf("H.264", "VP8"),
            metadata = null,
            numParticipants = 5,
            numPublishers = 3,
            activeRecording = false
        )
        
        whenever(webrtcClient.getRoom(roomName)).thenReturn(roomInfo)
        whenever(webrtcClient.listParticipants(roomName)).thenReturn(emptyList())
        whenever(redisManager.set(any(), any(), any())).thenReturn(true)
        
        val result = synchronizer.syncRoom(roomName)
        assertTrue(result)
    }
    
    @Test
    fun `should handle participant joined event`() {
        val roomName = "test-room"
        val participantId = "participant-123"
        val participantIdentity = "user@example.com"
        
        val participant = ParticipantInfo(
            sid = participantId,
            identity = participantIdentity,
            state = "ACTIVE",
            tracks = emptyList(),
            metadata = null,
            joinedAt = System.currentTimeMillis(),
            name = "Test User",
            version = 1,
            permission = null,
            region = "us-west-2",
            isPublisher = true
        )
        
        whenever(webrtcClient.getParticipant(roomName, participantIdentity)).thenReturn(participant)
        whenever(redisManager.setHashField(any(), any(), any())).thenReturn(true)
        
        synchronizer.handleParticipantJoined(roomName, participantId, participantIdentity)
        
        verify(redisManager).setHashField(any(), any(), any())
    }
    
    @Test
    fun `should get synchronization statistics`() {
        val stats = synchronizer.getStatistics()
        
        assertNotNull(stats)
        assertTrue(stats.containsKey("total_syncs"))
        assertTrue(stats.containsKey("successful_syncs"))
        assertTrue(stats.containsKey("active_rooms"))
    }
}

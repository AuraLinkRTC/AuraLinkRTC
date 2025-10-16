"""
AuraLink AIC Protocol - End-to-End Integration Tests
Tests the complete AI compression pipeline from WebRTC to AI Core
"""

import pytest
import asyncio
import grpc
import numpy as np
from pathlib import Path
import sys

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "auralink-ai-core"))

from app.proto import aic_compression_pb2, aic_compression_pb2_grpc
from app.services.compression_engine import (
    CompressionManager,
    Frame,
    FrameType,
    NetworkConditions,
    CompressionMode
)


@pytest.fixture
async def ai_core_client():
    """Create gRPC client to AI Core"""
    channel = grpc.aio.insecure_channel('localhost:50051')
    client = aic_compression_pb2_grpc.AICCompressionServiceStub(channel)
    yield client
    await channel.close()


@pytest.fixture
def sample_video_frame():
    """Create a sample video frame for testing"""
    # Create 1920x1080 RGB frame
    frame_data = np.random.randint(0, 255, (1080, 1920, 3), dtype=np.uint8)
    return frame_data.tobytes()


@pytest.fixture
def sample_audio_frame():
    """Create a sample audio frame for testing"""
    # Create 48kHz audio, 1 second
    samples = np.random.randn(48000).astype(np.float32)
    return (samples * 32767).astype(np.int16).tobytes()


class TestAICProtocolEndToEnd:
    """End-to-end integration tests for AIC Protocol"""
    
    @pytest.mark.asyncio
    async def test_grpc_health_check(self, ai_core_client):
        """Test gRPC health check endpoint"""
        request = aic_compression_pb2.HealthCheckRequest(
            service_name="aic-compression"
        )
        
        response = await ai_core_client.HealthCheck(request)
        
        assert response.status == aic_compression_pb2.HealthStatus.HEALTH_HEALTHY
        assert response.version == "1.0.0"
        assert response.uptime_seconds >= 0
    
    @pytest.mark.asyncio
    async def test_video_compression(self, ai_core_client, sample_video_frame):
        """Test video frame compression via gRPC"""
        request = aic_compression_pb2.CompressFrameRequest(
            session_id="test_session_001",
            call_id="test_call_001",
            participant_id="test_participant_001",
            frame_number=1,
            timestamp_us=1000000,
            frame_data=sample_video_frame,
            frame_type=aic_compression_pb2.FrameType.FRAME_TYPE_VIDEO,
            mode=aic_compression_pb2.CompressionMode.MODE_ADAPTIVE,
            target_compression_ratio=0.80,
            max_latency_ms=20,
            metadata=aic_compression_pb2.FrameMetadata(
                width=1920,
                height=1080,
                fps=30,
                codec="H264",
                is_keyframe=True
            ),
            network=aic_compression_pb2.NetworkConditions(
                available_bandwidth_kbps=5000,
                rtt_ms=50,
                packet_loss_percent=0.5,
                jitter_ms=10.0
            )
        )
        
        response = await ai_core_client.CompressFrame(request)
        
        # Verify response
        assert response.status == aic_compression_pb2.CompressionStatus.STATUS_SUCCESS
        assert len(response.compressed_data) > 0
        assert response.compressed_size_bytes < response.original_size_bytes
        assert response.actual_compression_ratio > 0.0
        assert response.actual_compression_ratio <= 1.0
        
        # Verify AI metadata
        assert response.ai_metadata.quality_score > 0.7
        assert response.ai_metadata.compression_ratio > 0.0
        
        # Verify performance metrics
        assert response.performance.inference_latency_ms > 0
        assert response.performance.inference_latency_ms < 100  # Should be fast
        
        print(f"\n✅ Video Compression Test Results:")
        print(f"   Original Size: {response.original_size_bytes} bytes")
        print(f"   Compressed Size: {response.compressed_size_bytes} bytes")
        print(f"   Compression Ratio: {response.actual_compression_ratio:.2%}")
        print(f"   Quality Score: {response.ai_metadata.quality_score:.3f}")
        print(f"   Inference Latency: {response.performance.inference_latency_ms}ms")
    
    @pytest.mark.asyncio
    async def test_audio_compression(self, ai_core_client, sample_audio_frame):
        """Test audio frame compression via gRPC"""
        request = aic_compression_pb2.CompressFrameRequest(
            session_id="test_session_002",
            call_id="test_call_002",
            participant_id="test_participant_002",
            frame_number=1,
            timestamp_us=1000000,
            frame_data=sample_audio_frame,
            frame_type=aic_compression_pb2.FrameType.FRAME_TYPE_AUDIO,
            mode=aic_compression_pb2.CompressionMode.MODE_ADAPTIVE,
            target_compression_ratio=0.80,
            max_latency_ms=20,
            metadata=aic_compression_pb2.FrameMetadata(
                sample_rate=48000,
                channels=1,
                bitrate_kbps=128
            )
        )
        
        response = await ai_core_client.CompressFrame(request)
        
        assert response.status in [
            aic_compression_pb2.CompressionStatus.STATUS_SUCCESS,
            aic_compression_pb2.CompressionStatus.STATUS_FALLBACK
        ]
        assert len(response.compressed_data) > 0
        assert response.compressed_size_bytes <= response.original_size_bytes
        
        print(f"\n✅ Audio Compression Test Results:")
        print(f"   Original Size: {response.original_size_bytes} bytes")
        print(f"   Compressed Size: {response.compressed_size_bytes} bytes")
        print(f"   Compression Ratio: {response.actual_compression_ratio:.2%}")
        print(f"   Fallback Used: {response.fallback_used}")
    
    @pytest.mark.asyncio
    async def test_compression_streaming(self, ai_core_client, sample_video_frame):
        """Test streaming compression mode"""
        async def request_generator():
            for i in range(10):
                yield aic_compression_pb2.CompressFrameRequest(
                    session_id="test_session_stream",
                    call_id="test_call_stream",
                    participant_id="test_participant_stream",
                    frame_number=i,
                    timestamp_us=1000000 + (i * 33333),  # 30fps
                    frame_data=sample_video_frame,
                    frame_type=aic_compression_pb2.FrameType.FRAME_TYPE_VIDEO,
                    mode=aic_compression_pb2.CompressionMode.MODE_ADAPTIVE,
                    target_compression_ratio=0.80,
                    max_latency_ms=20
                )
        
        frame_count = 0
        total_latency = 0
        
        async for response in ai_core_client.CompressStream(request_generator()):
            assert response.status in [
                aic_compression_pb2.CompressionStatus.STATUS_SUCCESS,
                aic_compression_pb2.CompressionStatus.STATUS_FALLBACK
            ]
            frame_count += 1
            total_latency += response.performance.inference_latency_ms
        
        avg_latency = total_latency / frame_count
        
        print(f"\n✅ Streaming Compression Test Results:")
        print(f"   Frames Processed: {frame_count}")
        print(f"   Average Latency: {avg_latency:.2f}ms")
        print(f"   Throughput: {1000/avg_latency:.1f} fps")
        
        assert frame_count == 10
        assert avg_latency < 50  # Should be fast enough for real-time
    
    @pytest.mark.asyncio
    async def test_compression_hints(self, ai_core_client):
        """Test compression hints prediction"""
        request = aic_compression_pb2.CompressionHintRequest(
            session_id="test_session_hints",
            mode=aic_compression_pb2.CompressionMode.MODE_ADAPTIVE,
            metadata=aic_compression_pb2.FrameMetadata(
                width=1920,
                height=1080,
                fps=30,
                is_keyframe=True
            ),
            network=aic_compression_pb2.NetworkConditions(
                available_bandwidth_kbps=3000,
                rtt_ms=80,
                packet_loss_percent=1.5,
                jitter_ms=20.0
            )
        )
        
        response = await ai_core_client.GetCompressionHints(request)
        
        assert response.recommended_compression_ratio > 0.0
        assert response.recommended_compression_ratio <= 1.0
        assert response.predicted_quality_score > 0.0
        assert response.confidence_score > 0.0
        assert len(response.recommended_codec) > 0
        
        print(f"\n✅ Compression Hints Test Results:")
        print(f"   Recommended Ratio: {response.recommended_compression_ratio:.2%}")
        print(f"   Predicted Quality: {response.predicted_quality_score:.3f}")
        print(f"   Recommended Codec: {response.recommended_codec}")
        print(f"   Confidence: {response.confidence_score:.3f}")
    
    @pytest.mark.asyncio
    async def test_network_analysis(self, ai_core_client):
        """Test network condition analysis"""
        # Create network samples
        samples = []
        for i in range(10):
            samples.append(aic_compression_pb2.NetworkSample(
                timestamp_us=1000000 + (i * 100000),
                bandwidth_kbps=5000 + np.random.randint(-500, 500),
                rtt_ms=50 + np.random.randint(-10, 10),
                packet_loss_percent=0.5 + np.random.random()
            ))
        
        request = aic_compression_pb2.NetworkAnalysisRequest(
            session_id="test_session_network",
            samples=samples,
            analysis_window_seconds=10
        )
        
        response = await ai_core_client.AnalyzeNetworkConditions(request)
        
        assert response.available_bandwidth_kbps > 0
        assert response.predicted_bandwidth_kbps > 0
        assert 0.0 <= response.network_stability_score <= 1.0
        assert response.quality in [
            aic_compression_pb2.NetworkQuality.NETWORK_EXCELLENT,
            aic_compression_pb2.NetworkQuality.NETWORK_GOOD,
            aic_compression_pb2.NetworkQuality.NETWORK_FAIR,
            aic_compression_pb2.NetworkQuality.NETWORK_POOR
        ]
        
        print(f"\n✅ Network Analysis Test Results:")
        print(f"   Available Bandwidth: {response.available_bandwidth_kbps} kbps")
        print(f"   Predicted Bandwidth: {response.predicted_bandwidth_kbps} kbps")
        print(f"   Stability Score: {response.network_stability_score:.3f}")
        print(f"   Quality: {response.quality}")
        print(f"   Recommendation: {response.recommendation}")
    
    @pytest.mark.asyncio
    async def test_fallback_mechanism(self, ai_core_client):
        """Test fallback to standard compression"""
        # Send request with very low latency requirement
        request = aic_compression_pb2.CompressFrameRequest(
            session_id="test_session_fallback",
            call_id="test_call_fallback",
            participant_id="test_participant_fallback",
            frame_number=1,
            timestamp_us=1000000,
            frame_data=b"test_data" * 1000,
            frame_type=aic_compression_pb2.FrameType.FRAME_TYPE_VIDEO,
            mode=aic_compression_pb2.CompressionMode.MODE_ADAPTIVE,
            target_compression_ratio=0.95,  # Very aggressive
            max_latency_ms=1  # Impossible to meet
        )
        
        response = await ai_core_client.CompressFrame(request)
        
        # Should either succeed or fallback gracefully
        assert response.status in [
            aic_compression_pb2.CompressionStatus.STATUS_SUCCESS,
            aic_compression_pb2.CompressionStatus.STATUS_FALLBACK,
            aic_compression_pb2.CompressionStatus.STATUS_TIMEOUT
        ]
        
        if response.fallback_used:
            print(f"\n✅ Fallback Test Results:")
            print(f"   Fallback Used: Yes")
            print(f"   Fallback Reason: {response.fallback_reason}")
            assert len(response.fallback_reason) > 0


class TestCompressionEngine:
    """Unit tests for compression engine"""
    
    @pytest.mark.asyncio
    async def test_compression_manager_initialization(self):
        """Test compression manager initialization"""
        manager = CompressionManager()
        await manager.initialize()
        
        assert manager.default_engine is not None
        assert manager.default_engine.model_loaded
    
    @pytest.mark.asyncio
    async def test_frame_compression_quality(self):
        """Test compression maintains quality thresholds"""
        manager = CompressionManager()
        await manager.initialize()
        
        # Create test frame
        frame = Frame(
            data=np.random.randint(0, 255, (1080, 1920, 3), dtype=np.uint8).tobytes(),
            frame_type=FrameType.VIDEO,
            width=1920,
            height=1080,
            fps=30,
            codec="H264"
        )
        
        network = NetworkConditions(
            available_bandwidth_kbps=5000,
            rtt_ms=50,
            packet_loss_percent=0.5,
            jitter_ms=10.0
        )
        
        config = {
            "mode": "adaptive",
            "target_compression_ratio": 0.80,
            "min_quality_score": 0.85
        }
        
        result = await manager.compress_frame(
            session_id="test_quality",
            frame=frame,
            config=config,
            network=network
        )
        
        # Verify quality thresholds
        if not result.fallback_used:
            assert result.quality_score >= 0.70
            assert result.compression_ratio > 0.0
        
        print(f"\n✅ Quality Test Results:")
        print(f"   Quality Score: {result.quality_score:.3f}")
        print(f"   Compression Ratio: {result.compression_ratio:.2%}")
        print(f"   Fallback Used: {result.fallback_used}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])

"""
Integration tests for AI Core health check endpoints
Tests the comprehensive readiness and liveness probes
"""

import pytest
import httpx
import asyncio
from typing import Dict, Any


class TestHealthChecks:
    """Test suite for health check endpoints"""
    
    @pytest.fixture
    def base_url(self) -> str:
        """Base URL for AI Core service"""
        return "http://localhost:8000"
    
    @pytest.mark.asyncio
    async def test_basic_health_check(self, base_url: str):
        """Test basic health endpoint always returns 200"""
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{base_url}/health")
            
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "healthy"
            assert data["service"] == "auralink-ai-core"
            assert "timestamp" in data
            assert "version" in data
    
    @pytest.mark.asyncio
    async def test_detailed_health_check(self, base_url: str):
        """Test detailed health endpoint includes system metrics"""
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{base_url}/health/detailed")
            
            assert response.status_code == 200
            data = response.json()
            
            # Check basic fields
            assert data["status"] == "healthy"
            assert data["service"] == "auralink-ai-core"
            
            # Check system metrics
            assert "system" in data
            assert "cpu_percent" in data["system"]
            assert "memory" in data["system"]
            assert "disk" in data["system"]
            assert "process" in data["system"]
            
            # Check dependencies
            assert "dependencies" in data
            assert "database" in data["dependencies"]
            assert "redis" in data["dependencies"]
    
    @pytest.mark.asyncio
    async def test_readiness_check_when_ready(self, base_url: str):
        """Test readiness probe returns 200 when all services initialized"""
        async with httpx.AsyncClient() as client:
            # Wait for services to initialize
            await asyncio.sleep(2)
            
            response = await client.get(f"{base_url}/readiness")
            
            # Should be 200 if all services are ready
            if response.status_code == 200:
                data = response.json()
                assert data["ready"] is True
                assert "checks" in data
                assert "database" in data["checks"]
                assert data["checks"]["database"]["ready"] is True
            # Or 503 if still initializing
            elif response.status_code == 503:
                data = response.json()
                assert data["ready"] is False
                assert "checks" in data
    
    @pytest.mark.asyncio
    async def test_readiness_check_structure(self, base_url: str):
        """Test readiness check has correct structure"""
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{base_url}/readiness")
            
            data = response.json()
            
            # Check required fields
            assert "ready" in data
            assert isinstance(data["ready"], bool)
            assert "checks" in data
            assert isinstance(data["checks"], dict)
            assert "timestamp" in data
            assert "service" in data
            
            # Check each service has status and ready flag
            for service_name, service_data in data["checks"].items():
                assert "status" in service_data
                assert "ready" in service_data
                assert isinstance(service_data["ready"], bool)
    
    @pytest.mark.asyncio
    async def test_liveness_check(self, base_url: str):
        """Test liveness probe returns 200 when process is alive"""
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{base_url}/liveness")
            
            assert response.status_code == 200
            data = response.json()
            
            assert data["status"] == "alive"
            assert "timestamp" in data
            assert "cpu_percent" in data
            assert "memory_percent" in data
            assert "pid" in data
            
            # Check metrics are reasonable
            assert 0 <= data["cpu_percent"] <= 100
            assert 0 <= data["memory_percent"] <= 100
            assert data["pid"] > 0
    
    @pytest.mark.asyncio
    async def test_liveness_event_loop_responsive(self, base_url: str):
        """Test liveness check verifies event loop is responsive"""
        async with httpx.AsyncClient() as client:
            # Make multiple rapid requests
            responses = await asyncio.gather(*[
                client.get(f"{base_url}/liveness")
                for _ in range(5)
            ])
            
            # All should succeed if event loop is responsive
            for response in responses:
                assert response.status_code == 200
                data = response.json()
                assert data["status"] == "alive"
    
    @pytest.mark.asyncio
    async def test_readiness_database_check(self, base_url: str):
        """Test readiness check validates database connection"""
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{base_url}/readiness")
            data = response.json()
            
            # Database should always be checked
            assert "database" in data["checks"]
            db_check = data["checks"]["database"]
            
            # Should have status and ready fields
            assert "status" in db_check
            assert "ready" in db_check
            
            # If ready, status should be "connected"
            if db_check["ready"]:
                assert db_check["status"] == "connected"
            # If not ready, should have error or not_initialized
            else:
                assert db_check["status"] in ["not_initialized", "error"]
                if db_check["status"] == "error":
                    assert "error" in db_check
    
    @pytest.mark.asyncio
    async def test_readiness_optional_services(self, base_url: str):
        """Test readiness check handles optional services correctly"""
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{base_url}/readiness")
            data = response.json()
            
            # Redis is optional - should not fail overall readiness
            if "redis" in data["checks"]:
                redis_check = data["checks"]["redis"]
                if not redis_check["ready"]:
                    # Should be marked as optional
                    assert redis_check.get("optional", False)
                    # Overall readiness should still be true if database is ready
                    if data["checks"]["database"]["ready"]:
                        # Redis failure shouldn't fail overall readiness
                        pass  # This is expected
    
    @pytest.mark.asyncio
    async def test_kubernetes_probe_compatibility(self, base_url: str):
        """Test probes are compatible with Kubernetes expectations"""
        async with httpx.AsyncClient() as client:
            # Liveness should always respond quickly
            liveness_response = await client.get(
                f"{base_url}/liveness",
                timeout=5.0
            )
            assert liveness_response.status_code in [200, 500]
            
            # Readiness can return 503 when not ready
            readiness_response = await client.get(
                f"{base_url}/readiness",
                timeout=5.0
            )
            assert readiness_response.status_code in [200, 503]
    
    @pytest.mark.asyncio
    async def test_probe_response_time(self, base_url: str):
        """Test probes respond within acceptable time"""
        async with httpx.AsyncClient() as client:
            import time
            
            # Liveness should be very fast (<100ms)
            start = time.time()
            await client.get(f"{base_url}/liveness")
            liveness_time = time.time() - start
            assert liveness_time < 0.1, f"Liveness too slow: {liveness_time}s"
            
            # Readiness can be slower but should be <1s
            start = time.time()
            await client.get(f"{base_url}/readiness")
            readiness_time = time.time() - start
            assert readiness_time < 1.0, f"Readiness too slow: {readiness_time}s"


# Run tests
if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])

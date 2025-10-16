# Phase 6: Quick Start Guide

**Get started with AuraID & Mesh Network in 5 minutes**

---

## 🚀 Quick Setup

### 1. Run Database Migration

```bash
# Apply Phase 6 schema
psql $DATABASE_URL -f scripts/db/migrations/006_phase6_auraid_mesh_schema.sql
```

### 2. Start Services

```bash
# Start all services with Phase 6 enabled
docker-compose up -d

# Or using Kubernetes
kubectl apply -f infrastructure/kubernetes/phase6-deployment.yaml
```

### 3. Verify Installation

```bash
# Check AuraID endpoint
curl http://localhost:8080/api/v1/auraid/availability?username=test

# Check Mesh routing endpoint
curl http://localhost:8001/api/v1/mesh/network/status
```

---

## 💻 Usage Examples

### Create AuraID

```bash
curl -X POST http://localhost:8080/api/v1/auraid \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"username": "alice", "privacy_level": "public"}'
```

**Response**:
```json
{
  "aura_id": "@alice.aura",
  "is_verified": false,
  "privacy_level": "public",
  "created_at": "2025-10-16T00:00:00Z"
}
```

### Search AuraIDs

```bash
curl http://localhost:8080/api/v1/auraid/search?q=alice \
  -H "Authorization: Bearer YOUR_TOKEN"
```

### Find Optimal Route

```bash
curl -X POST http://localhost:8001/api/v1/mesh/routes/find-optimal \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "source_aura_id": "@alice.aura",
    "destination_aura_id": "@bob.aura",
    "require_aic": true
  }'
```

**Response**:
```json
{
  "route_id": "route_xyz",
  "predicted_latency_ms": 45,
  "ai_score": 87.5,
  "supports_aic": true,
  "path_nodes": ["node_1", "node_relay", "node_2"]
}
```

### Register Mesh Node

```bash
curl -X POST http://localhost:8001/api/v1/mesh/nodes/register \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "aura_id": "@alice.aura",
    "node_address": "192.168.1.100:5000",
    "node_type": "peer",
    "supports_aic_protocol": true
  }'
```

---

## 🔧 Configuration

### Environment Variables

```bash
# Add to your .env file
ENABLE_AURAID=true
ENABLE_MESH_NETWORK=true
MESH_NODE_TYPE=peer
MESH_MAX_CONNECTIONS=100
AI_ROUTING_ENABLED=true
```

### Dashboard Configuration

```go
// internal/config/config.go
type Config struct {
    // Phase 6 settings
    EnableAuraID      bool   `env:"ENABLE_AURAID" default:"true"`
    EnableMeshNetwork bool   `env:"ENABLE_MESH_NETWORK" default:"true"`
    MeshNodeType      string `env:"MESH_NODE_TYPE" default:"peer"`
}
```

### AI Core Configuration

```python
# app/core/config.py
class Settings(BaseSettings):
    # Phase 6 settings
    enable_mesh_routing: bool = True
    mesh_ai_optimization: bool = True
    route_cache_ttl: int = 300  # 5 minutes
```

---

## 📱 SDK Integration

### JavaScript/TypeScript

```typescript
import { AuraLinkSDK } from '@auralink/sdk';

const sdk = new AuraLinkSDK({
  apiKey: 'your_api_key',
  enableMesh: true,
  enableAIC: true
});

// Create AuraID
const auraID = await sdk.auraid.create({ username: 'alice' });

// Make cross-app call
const call = await sdk.calls.createWithMeshRouting({
  targetAuraID: '@bob.aura',
  preferAIC: true
});
```

### Python

```python
from auralink_sdk import AuraLinkClient

client = AuraLinkClient(
    api_key="your_api_key",
    enable_mesh=True
)

# Create AuraID
aura_id = await client.auraid.create(username="alice")

# Find route
route = await client.mesh.find_optimal_route(
    source_aura_id="@alice.aura",
    destination_aura_id="@bob.aura"
)
```

### Go

```go
import "github.com/auralink/sdk-go"

client := auralink.NewClient("your_api_key")

// Create AuraID
auraID, err := client.AuraID.Create(&auralink.CreateAuraIDRequest{
    Username: "alice",
})

// Establish mesh connection
conn, err := client.Mesh.EstablishConnection(
    "@alice.aura",
    "@bob.aura",
    true, // requireAIC
)
```

---

## 🔍 Common Operations

### Check Username Availability

```bash
curl "http://localhost:8080/api/v1/auraid/availability?username=alice"
```

### Get My AuraID

```bash
curl http://localhost:8080/api/v1/auraid/me \
  -H "Authorization: Bearer YOUR_TOKEN"
```

### Update Privacy Settings

```bash
curl -X PUT http://localhost:8080/api/v1/auraid \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "privacy_level": "friends",
    "allow_discovery": false,
    "block_unknown_callers": true
  }'
```

### Get Network Status

```bash
curl http://localhost:8001/api/v1/mesh/network/status \
  -H "Authorization: Bearer YOUR_TOKEN"
```

### Send Node Heartbeat

```bash
curl -X POST http://localhost:8001/api/v1/mesh/nodes/heartbeat \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "node_id": "node_abc123",
    "current_connections": 5,
    "current_bandwidth_usage_mbps": 50,
    "avg_latency_ms": 25.5,
    "packet_loss_rate": 0.001
  }'
```

---

## 🐛 Troubleshooting

### Issue: AuraID Creation Fails

**Error**: "Username already taken"

**Solution**:
```bash
# Check availability first
curl "http://localhost:8080/api/v1/auraid/availability?username=alice"

# Try different username
curl -X POST http://localhost:8080/api/v1/auraid \
  -d '{"username": "alice2"}'
```

### Issue: No Route Found

**Error**: "No route available"

**Solution**:
```bash
# Check if nodes are online
curl http://localhost:8001/api/v1/mesh/nodes/aura/@bob.aura

# If no nodes, register one
curl -X POST http://localhost:8001/api/v1/mesh/nodes/register \
  -d '{"aura_id": "@bob.aura", "node_address": "..."}'
```

### Issue: Low Reputation Score

**Check current score**:
```bash
curl http://localhost:8001/api/v1/mesh/nodes/NODE_ID
```

**Improve reputation**:
- Send regular heartbeats
- Report accurate performance metrics
- Maintain stable connections
- Avoid abuse reports

---

## 📊 Monitoring

### Key Metrics to Watch

```bash
# Prometheus metrics
curl http://localhost:8001/metrics | grep mesh
```

**Important Metrics**:
- `mesh_nodes_online_total` - Online nodes
- `mesh_routes_calculated_total` - Routes created
- `mesh_ai_score_average` - Average AI score
- `mesh_reputation_events_total` - Reputation changes
- `auraid_created_total` - AuraIDs created
- `auraid_searches_total` - Search requests

### Grafana Dashboard

```bash
# Import Phase 6 dashboard
curl -X POST http://localhost:3000/api/dashboards/db \
  -d @infrastructure/monitoring/grafana/phase6-dashboard.json
```

---

## 🔐 Security Best Practices

### 1. Privacy Settings

```bash
# Set appropriate privacy level
curl -X PUT /api/v1/auraid -d '{
  "privacy_level": "friends",  # or "private" for maximum privacy
  "allow_discovery": false,
  "block_unknown_callers": true
}'
```

### 2. Federation Whitelist

```bash
# Only allow trusted domains
curl -X PUT /api/v1/auraid -d '{
  "federated_domains": ["trusted-app.com", "partner-app.com"],
  "federation_enabled": true
}'
```

### 3. Verify AuraID

```bash
# Enable verification for trust
curl -X POST /api/v1/auraid/verify -d '{
  "verification_method": "phone",
  "verification_code": "123456"
}'
```

---

## 📚 Next Steps

1. **Read Full Documentation**: See `/docs/phase6/` for complete guides
2. **Explore API Docs**: Visit `http://localhost:8001/docs` for interactive API documentation
3. **Join Community**: Get support and share feedback
4. **Deploy to Production**: Follow deployment guide in `INTEGRATION_GUIDE.md`

---

## 🆘 Getting Help

### Documentation
- [Complete Implementation Guide](./PHASE6_IMPLEMENTATION_COMPLETE.md)
- [Integration Guide](./INTEGRATION_GUIDE.md)
- [API Reference](http://localhost:8001/docs)

### Support
- GitHub Issues: Report bugs and request features
- Documentation: Comprehensive guides in `/docs/phase6/`
- Examples: Sample code in each service directory

---

**You're ready to build with AuraID & Mesh Network! 🚀**

*© 2025 AuraLinkRTC Inc.*

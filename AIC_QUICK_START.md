# 🚀 AIC Protocol - Quick Start Guide

## Prerequisites

- Docker with NVIDIA runtime
- Kubernetes cluster with GPU nodes
- Python 3.11+
- Go 1.24+
- Protocol Buffers compiler

## 1. Build Proto Files (1 minute)

```bash
cd /Users/naveen/Desktop/AuraLink1
chmod +x scripts/build/build_aic_protocol.sh
./scripts/build/build_aic_protocol.sh
```

**Expected Output:**
```
✓ Python protobuf files generated
✓ Go protobuf files generated
✓ WebRTC Server binary created
```

## 2. Start AI Core (Development)

```bash
cd auralink-ai-core

# Install dependencies
pip install -r requirements.txt

# Generate proto files
cd ../shared/protos
python -m grpc_tools.protoc \
    -I. \
    --python_out=../../auralink-ai-core/app/proto \
    --grpc_python_out=../../auralink-ai-core/app/proto \
    aic_compression.proto

# Start gRPC server
cd ../../auralink-ai-core
python -m app.services.grpc_server
```

**Expected Output:**
```
INFO:root:Loading REAL neural compression models...
INFO:root:Neural compression models loaded on cuda
INFO:root:AIC gRPC server started on port 50051
```

## 3. Start WebRTC Server (Development)

```bash
cd auralink-webrtc-server

# Generate Go proto files
cd ../shared/protos
protoc --go_out=../../auralink-webrtc-server/pkg/proto/aic \
       --go-grpc_out=../../auralink-webrtc-server/pkg/proto/aic \
       --go_opt=paths=source_relative \
       --go-grpc_opt=paths=source_relative \
       aic_compression.proto

# Build
cd ../../auralink-webrtc-server
go build -o bin/webrtc-server cmd/server/main.go

# Run
./bin/webrtc-server
```

## 4. Run Tests

```bash
cd tests/integration
pytest test_aic_end_to_end.py -v -s
```

## 5. Deploy to Production (Kubernetes)

```bash
# Create namespace
kubectl create namespace auralink

# Deploy storage
kubectl apply -f infrastructure/kubernetes/aic-model-pvc.yaml

# Deploy AI Core
kubectl apply -f infrastructure/kubernetes/ai-core-deployment.yaml

# Verify
kubectl get pods -n auralink
kubectl logs -f -n auralink deployment/auralink-ai-core
```

## 6. Test gRPC Endpoint

```bash
# Health check
grpcurl -plaintext localhost:50051 \
  auralink.aic.v1.AICCompressionService/HealthCheck

# Compress frame (test)
grpcurl -plaintext -d '{
  "session_id": "test",
  "frame_data": "dGVzdA==",
  "frame_type": "FRAME_TYPE_VIDEO",
  "mode": "MODE_ADAPTIVE"
}' localhost:50051 \
  auralink.aic.v1.AICCompressionService/CompressFrame
```

## 7. Monitor Performance

```bash
# AI Core metrics
curl http://localhost:8000/health

# Dashboard metrics
curl http://localhost:3000/api/v1/aic/performance/summary
```

## Architecture

```
WebRTC (Go) → gRPC (port 50051) → AI Core (Python)
                                       ↓
                                  Neural Models
                                       ↓
                                    GPU (CUDA)
```

## Key Files Modified/Created

### Created:
- `model_loader.py` - Production model loading
- `aic-model-pvc.yaml` - Kubernetes storage
- `test_aic_end_to_end.py` - Integration tests
- `AIC_PROTOCOL_IMPLEMENTATION_COMPLETE.md` - Full documentation

### Modified:
- `aic_integration.go` - Fixed imports, added helpers
- `mediatrack.go` - Added SetAICProcessor/GetAICProcessor
- `compression_engine.py` - Removed simulation, added model loader
- `ai-core-deployment.yaml` - Added GPU, gRPC port, volume mounts
- `Dockerfile` - Production-ready with CUDA

## Troubleshooting

### Proto files not found
```bash
# Regenerate
cd shared/protos
./build_aic_protocol.sh
```

### GPU not detected
```bash
# Check CUDA
nvidia-smi

# Check Kubernetes GPU
kubectl describe node | grep nvidia.com/gpu
```

### Models not loading
```bash
# Check model directory
ls -lh /app/models/

# Download EnCodec
pip install encodec
```

## Next Steps

1. ✅ Train custom models (optional - EnCodec works great)
2. ✅ Configure mTLS for gRPC in production
3. ✅ Set up Prometheus metrics
4. ✅ Scale replicas based on load

## Support

See `AIC_PROTOCOL_IMPLEMENTATION_COMPLETE.md` for complete documentation.

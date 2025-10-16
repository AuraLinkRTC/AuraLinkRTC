# 🚀 AuraLink Quick Start Guide

## Prerequisites Verified ✅

- ✅ Supabase Project Active (`mydyucwvdnjbhqigseis`)
- ✅ 56 Database Tables Created
- ✅ Environment Variables Configured (`.env`)
- ✅ Redis Optional (service continues without it)

## Start in 3 Steps

### 1. Install Dependencies (One-time)

```bash
# Python AI Core
cd auralink-ai-core
pip install -r requirements.txt
pip install asyncpg redis

# Go Dashboard (if needed)
cd auralink-dashboard-service
go mod tidy
```

### 2. Start Services

**Option A: Docker Compose (Recommended)**
```bash
docker-compose -f docker-compose.production.yml up -d
```

**Option B: Manual Start**
```bash
# Terminal 1: AI Core
cd auralink-ai-core
python main.py

# Terminal 2: Dashboard
cd auralink-dashboard-service
go run cmd/server/main.go
```

### 3. Verify Everything Works

```bash
# Check AI Core
curl http://localhost:8000/health/detailed | jq

# Check Dashboard
curl http://localhost:8080/health | jq

# Open Grafana
open http://localhost:3000
```

## Expected Output

### AI Core Startup
```
✓ Database connected: PostgreSQL 17.6.1
✓ Database has 56 tables
✓ All critical tables verified
✓ Redis connected: v7.0.0
✓ Phase 4 Services Initialized
✓ Phase 5 Services Initialized
AuraLink AI Core fully initialized - Phase 5 active ✨
```

### Health Check Response
```json
{
  "status": "healthy",
  "service": "auralink-ai-core",
  "dependencies": {
    "database": {
      "status": "healthy",
      "pool": {
        "size": 5,
        "free_size": 5
      }
    },
    "redis": {
      "status": "healthy",
      "connected_clients": 2
    }
  }
}
```

## Troubleshooting

### Database Connection Failed
```bash
# Check Supabase project
echo $SUPABASE_URL
echo $SUPABASE_SERVICE_ROLE_KEY

# Test connection
curl "$SUPABASE_URL/rest/v1/" -H "apikey: $SUPABASE_ANON_KEY"
```

### Redis Connection Failed
Service will continue without Redis (caching disabled).
```bash
# Start Redis manually
docker run -d -p 6379:6379 redis:7-alpine

# Or ignore (optional dependency)
```

### Port Already in Use
```bash
# Check what's using the port
lsof -i :8000  # AI Core
lsof -i :8080  # Dashboard

# Kill process
kill -9 <PID>
```

## Next Steps

1. ✅ Services running
2. 📊 View metrics: `http://localhost:9090` (Prometheus)
3. 📈 View dashboards: `http://localhost:3000` (Grafana)
4. 📖 Read full docs: `docs/phase1/PHASE1_PRODUCTION_READY.md`

## Key Endpoints

| Service | Endpoint | Purpose |
|---------|----------|---------|
| AI Core | `http://localhost:8000/health` | Health check |
| AI Core | `http://localhost:8000/docs` | API documentation |
| AI Core | `http://localhost:8000/metrics` | Prometheus metrics |
| Dashboard | `http://localhost:8080/health` | Health check |
| Prometheus | `http://localhost:9090` | Metrics viewer |
| Grafana | `http://localhost:3000` | Dashboards |

## Summary

**Phase 1 is PRODUCTION READY!**

- ✅ 56 database tables
- ✅ Connection pooling
- ✅ Redis caching
- ✅ Health checks
- ✅ Monitoring

🎉 **You're ready to develop or deploy!**

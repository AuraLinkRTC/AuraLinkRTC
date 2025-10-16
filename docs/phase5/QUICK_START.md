# Phase 5 Quick Start Guide

## 🚀 Get Started in 5 Minutes

This guide will get you up and running with Phase 5 features immediately.

## Step 1: Install Dependencies (1 min)

```bash
cd auralink-ai-core
pip install -r requirements.txt
```

**New Phase 5 Dependencies Installed**:
- langgraph==0.0.28
- crewai==0.28.8
- pyautogen==0.2.18
- prefect==2.16.4
- mcp==0.9.0

## Step 2: Run Database Migration (1 min)

```bash
psql -U postgres -d auralink -f scripts/db/migrations/005_phase5_mcp_agents_schema.sql
```

**What This Creates**:
- 15 new tables for Phase 5
- 3 materialized views for analytics
- Seed data: 4 MCP servers, 4 providers, 20+ LLM models

## Step 3: Start Services (1 min)

```bash
cd auralink-ai-core
python main.py
```

**Services Started**:
- AI Core API on port 8001
- Phase 5 endpoints: `/api/v1/mcp`, `/api/v1/workflows`, `/api/v1/teams`, `/api/v1/llm`

## Step 4: Test MCP Integration (1 min)

```bash
# Get authentication token
TOKEN="your_jwt_token"

# Connect to DeepWiki MCP
curl -X POST http://localhost:8001/api/v1/mcp/connect \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"server_type": "deepwiki"}'

# Response:
# {
#   "connection_id": "conn_abc123",
#   "status": "connected",
#   "server_type": "deepwiki",
#   "capabilities": ["read_wiki", "search_docs", "ask_question"]
# }
```

## Step 5: Create Your First Workflow (1 min)

```bash
# Create agent workflow
curl -X POST http://localhost:8001/api/v1/workflows/agent-workflows \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "agent_id": "your_agent_id",
    "workflow_name": "My First Workflow",
    "workflow_type": "qa",
    "mcp_integrations": ["deepwiki"]
  }'

# Response:
# {
#   "workflow_id": "workflow_123",
#   "workflow_name": "My First Workflow",
#   "workflow_type": "qa"
# }
```

## 🎯 What You Can Do Now

### 1. Query GitHub Repositories
```bash
curl -X POST http://localhost:8001/api/v1/mcp/deepwiki/ask \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "connection_id": "conn_abc123",
    "repo_name": "facebook/react",
    "question": "How does React work?"
  }'
```

### 2. Create Agent Teams
```bash
curl -X POST http://localhost:8001/api/v1/teams \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "team_name": "Research Team",
    "collaboration_mode": "sequential"
  }'
```

### 3. Select Best LLM
```bash
curl http://localhost:8001/api/v1/llm/preferences/best?task_type=chat \
  -H "Authorization: Bearer $TOKEN"
```

### 4. List Available Models
```bash
curl http://localhost:8001/api/v1/llm/models \
  -H "Authorization: Bearer $TOKEN"
```

## 📊 Verify Installation

```bash
# Check API health
curl http://localhost:8001/health

# Check Phase 5 services
curl http://localhost:8001/ \
  -H "Authorization: Bearer $TOKEN"

# View API documentation
open http://localhost:8001/docs
```

## 🎓 Next Steps

1. **Explore MCP Servers**: Try all 4 MCP servers (DeepWiki, Memory, Sequential-Thinking, Supabase)
2. **Create Workflows**: Build custom agent workflows for your use case
3. **Build Teams**: Create multi-agent teams for complex tasks
4. **Optimize Costs**: Configure LLM preferences and track spending
5. **Read Full Docs**: See `PHASE5_IMPLEMENTATION_COMPLETE.md`

## 🔍 Common Commands

### MCP Operations
```bash
# List connections
curl http://localhost:8001/api/v1/mcp/connections \
  -H "Authorization: Bearer $TOKEN"

# Query memory graph
curl -X POST http://localhost:8001/api/v1/mcp/memory/search \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"connection_id": "conn_123", "query": "AI concepts"}'

# Execute SQL on Supabase
curl -X POST http://localhost:8001/api/v1/mcp/supabase/query \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"connection_id": "conn_456", "project_id": "proj_789", "query": "SELECT * FROM users LIMIT 10"}'
```

### Workflow Operations
```bash
# List workflows
curl http://localhost:8001/api/v1/workflows/agent-workflows/agent/{agent_id} \
  -H "Authorization: Bearer $TOKEN"

# Execute workflow
curl -X POST http://localhost:8001/api/v1/workflows/agent-workflows/execute \
  -H "Authorization: Bearer $TOKEN" \
  -d '{
    "workflow_id": "workflow_123",
    "agent_id": "agent_456",
    "input_data": {"question": "What is AI?"}
  }'
```

### Team Operations
```bash
# List teams
curl http://localhost:8001/api/v1/teams \
  -H "Authorization: Bearer $TOKEN"

# Add team member
curl -X POST http://localhost:8001/api/v1/teams/members \
  -H "Authorization: Bearer $TOKEN" \
  -d '{
    "team_id": "team_123",
    "agent_id": "agent_456",
    "role": "researcher"
  }'

# Execute team task
curl -X POST http://localhost:8001/api/v1/crewai/execute \
  -H "Authorization: Bearer $TOKEN" \
  -d '{
    "team_id": "team_123",
    "task_description": "Research AI trends"
  }'
```

### LLM Operations
```bash
# List providers
curl http://localhost:8001/api/v1/llm/providers

# List models
curl http://localhost:8001/api/v1/llm/models

# Set default model
curl -X POST http://localhost:8001/api/v1/llm/preferences/default \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"model_id": "model_gpt4_turbo"}'

# Get cost analysis
curl http://localhost:8001/api/v1/llm/cost/analysis?days=30 \
  -H "Authorization: Bearer $TOKEN"
```

## 🐛 Troubleshooting

**Service won't start**:
```bash
# Check Python version (3.10+)
python --version

# Check dependencies
pip list | grep -E 'langgraph|crewai|prefect'

# Check logs
tail -f logs/auralink-ai-core.log
```

**Database migration fails**:
```bash
# Check PostgreSQL is running
psql -U postgres -c "SELECT version();"

# Check database exists
psql -U postgres -l | grep auralink

# Rerun migration
psql -U postgres -d auralink -f scripts/db/migrations/005_phase5_mcp_agents_schema.sql
```

**API returns 401**:
```bash
# Verify token format
echo $TOKEN

# Token should be JWT format
# Get new token from auth service
```

## 📚 Resources

- **API Docs**: http://localhost:8001/docs
- **Full Documentation**: `PHASE5_IMPLEMENTATION_COMPLETE.md`
- **Integration Guide**: `INTEGRATION_GUIDE.md`
- **Service Code**: `auralink-ai-core/app/services/`

## ✅ Checklist

- [ ] Dependencies installed
- [ ] Database migrated
- [ ] Service started
- [ ] MCP connection tested
- [ ] Workflow created
- [ ] Team created
- [ ] LLM models listed
- [ ] API documentation viewed

---

**🎉 Congratulations!** You've successfully set up Phase 5. Start building intelligent AI agents with MCP integration, multi-agent collaboration, and advanced workflow orchestration.

*For advanced features and production deployment, see the complete documentation.*

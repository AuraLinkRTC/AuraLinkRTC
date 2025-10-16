# Phase 5 Integration Guide

## 🔗 Connecting Phase 5 with Existing System

This guide explains how Phase 5 integrates with the existing AuraLinkRTC system and how to use the new features.

## Prerequisites

Before using Phase 5 features, ensure:
- ✅ Phase 1-4 are deployed and running
- ✅ Database migrations are applied
- ✅ AI Core service is running on port 8001
- ✅ Environment variables are configured

## System Integration Points

### 1. Database Layer
Phase 5 adds 15 new tables that integrate with existing Phase 4 tables:

```sql
-- Integration with Phase 4
agent_workflows → ai_agents (agent_id)
workflow_executions → ai_agents (agent_id)
team_members → ai_agents (agent_id)
agent_mcp_interactions → ai_agents (agent_id)
user_mcp_connections → users (user_id)
```

### 2. Service Layer
Phase 5 services integrate with Phase 4 services:

```python
# LangGraph uses existing services
LangGraphAgentService(
    db_pool=db_pool,
    ai_provider_service=ai_provider_service,  # Phase 4
    memory_service=memory_service,            # Phase 4
    mcp_service=mcp_service,                  # Phase 5 NEW
    speech_service=speech_service,            # Phase 4
    translation_service=translation_service   # Phase 4
)
```

### 3. API Layer
Phase 5 adds new endpoints that complement existing APIs:

```
Existing APIs (Phase 4):
├── /api/v1/agents          # Agent management
├── /api/v1/memory          # Memory operations
├── /api/v1/speech          # STT/TTS
└── /api/v1/translation     # Translation

New APIs (Phase 5):
├── /api/v1/mcp             # MCP integration
├── /api/v1/workflows       # Workflow management
├── /api/v1/teams           # Team collaboration
└── /api/v1/llm             # LLM selection
```

## Usage Scenarios

### Scenario 1: AI Agent with MCP Integration

**Use Case**: Create an AI agent that can query GitHub repos during calls

```python
import requests

# 1. Create agent (Phase 4)
agent = requests.post(
    "http://localhost:8001/api/v1/agents",
    headers={"Authorization": f"Bearer {token}"},
    json={
        "name": "GitHub Assistant",
        "model": "gpt-4",
        "memory_enabled": True
    }
).json()

# 2. Connect to DeepWiki MCP (Phase 5)
connection = requests.post(
    "http://localhost:8001/api/v1/mcp/connect",
    headers={"Authorization": f"Bearer {token}"},
    json={"server_type": "deepwiki"}
).json()

# 3. Create workflow (Phase 5)
workflow = requests.post(
    "http://localhost:8001/api/v1/workflows/agent-workflows",
    headers={"Authorization": f"Bearer {token}"},
    json={
        "agent_id": agent["agent_id"],
        "workflow_name": "GitHub Q&A",
        "workflow_type": "qa",
        "mcp_integrations": ["deepwiki"]
    }
).json()

# 4. Execute workflow
result = requests.post(
    "http://localhost:8001/api/v1/workflows/agent-workflows/execute",
    headers={"Authorization": f"Bearer {token}"},
    json={
        "workflow_id": workflow["workflow_id"],
        "agent_id": agent["agent_id"],
        "input_data": {
            "question": "How does React Hooks work?"
        }
    }
).json()

print(f"Answer: {result['output']}")
```

### Scenario 2: Multi-Agent Research Team

**Use Case**: Create a team of AI agents to research and write reports

```python
# 1. Create agents with different specializations
researcher = create_agent("Research Agent", "gpt-4")
writer = create_agent("Content Writer", "claude-3-opus")
reviewer = create_agent("Quality Reviewer", "gpt-4-turbo")

# 2. Create team
team = requests.post(
    "http://localhost:8001/api/v1/teams",
    headers={"Authorization": f"Bearer {token}"},
    json={
        "team_name": "Research Team",
        "collaboration_mode": "sequential"
    }
).json()

# 3. Add members with roles
requests.post(
    "http://localhost:8001/api/v1/teams/members",
    headers={"Authorization": f"Bearer {token}"},
    json={
        "team_id": team["team_id"],
        "agent_id": researcher["agent_id"],
        "role": "researcher",
        "execution_order": 1
    }
)

requests.post(
    "http://localhost:8001/api/v1/teams/members",
    headers={"Authorization": f"Bearer {token}"},
    json={
        "team_id": team["team_id"],
        "agent_id": writer["agent_id"],
        "role": "writer",
        "execution_order": 2
    }
)

# 4. Execute team task
result = requests.post(
    "http://localhost:8001/api/v1/crewai/execute",
    headers={"Authorization": f"Bearer {token}"},
    json={
        "team_id": team["team_id"],
        "task_description": "Research AI trends in 2025 and write a report"
    }
).json()

print(f"Report: {result['result']}")
```

### Scenario 3: Intelligent LLM Selection

**Use Case**: Optimize costs by selecting the right model for each task

```python
# 1. Configure user preferences
requests.post(
    "http://localhost:8001/api/v1/llm/preferences/add",
    headers={"Authorization": f"Bearer {token}"},
    json={
        "model_id": "gpt-4-turbo",
        "priority": 100,
        "cost_limit_usd": 100.00
    }
)

# 2. Let system select best model
selection = requests.get(
    "http://localhost:8001/api/v1/llm/preferences/best?task_type=chat",
    headers={"Authorization": f"Bearer {token}"}
).json()

print(f"Selected model: {selection['model_name']}")
print(f"Reason: {selection['selection_reason']}")

# 3. Get cost analysis
analysis = requests.get(
    "http://localhost:8001/api/v1/llm/cost/analysis?days=30",
    headers={"Authorization": f"Bearer {token}"}
).json()

print(f"Total cost: ${analysis['summary']['total_cost_usd']}")
print(f"Total requests: {analysis['summary']['total_requests']}")
```

### Scenario 4: Meeting Summarization with Memory

**Use Case**: Automatically summarize meetings and store in memory

```python
# 1. Create summarization workflow
workflow = requests.post(
    "http://localhost:8001/api/v1/workflows/agent-workflows",
    headers={"Authorization": f"Bearer {token}"},
    json={
        "agent_id": agent_id,
        "workflow_name": "Meeting Summarizer",
        "workflow_type": "summarization",
        "mcp_integrations": ["memory"]
    }
).json()

# 2. Execute after call ends
result = requests.post(
    "http://localhost:8001/api/v1/workflows/agent-workflows/execute",
    headers={"Authorization": f"Bearer {token}"},
    json={
        "workflow_id": workflow["workflow_id"],
        "agent_id": agent_id,
        "input_data": {
            "call_id": call_id,
            "room_id": room_id
        }
    }
).json()

# 3. Summary automatically stored in memory
# Future agents can recall this meeting
memory_result = requests.post(
    "http://localhost:8001/api/v1/memory/recall",
    headers={"Authorization": f"Bearer {token}"},
    json={
        "query": f"meeting in room {room_id}",
        "limit": 5
    }
).json()

print(f"Found {len(memory_result['results'])} memories")
```

## Dashboard Integration

### Frontend Integration
Phase 5 features can be integrated into the dashboard:

```javascript
// Example: MCP Connection UI
async function connectMCP(serverType) {
  const response = await fetch('/api/v1/mcp/connect', {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${token}`,
      'Content-Type': 'application/json'
    },
    body: JSON.stringify({ server_type: serverType })
  });
  
  const connection = await response.json();
  return connection;
}

// Example: Create Team UI
async function createTeam(teamName) {
  const response = await fetch('/api/v1/teams', {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${token}`,
      'Content-Type': 'application/json'
    },
    body: JSON.stringify({
      team_name: teamName,
      collaboration_mode: 'sequential'
    })
  });
  
  return await response.json();
}
```

## WebRTC Integration

### Real-Time Agent Integration
Agents can participate in WebRTC calls:

```python
# 1. Create agent with voice
agent = create_agent("Meeting Assistant", voice_enabled=True)

# 2. Create auto-join workflow
workflow = create_workflow(agent_id, "auto_join")

# 3. Agent automatically joins when room is created
# WebRTC Server → AI Core webhook
# AI Core executes workflow
# Agent joins room and greets participants
```

## Monitoring & Analytics

### Performance Tracking
Monitor Phase 5 features:

```python
# MCP usage stats
mcp_stats = requests.get(
    "http://localhost:8001/api/v1/mcp/usage/stats",
    headers={"Authorization": f"Bearer {token}"}
).json()

# Workflow performance
workflow_stats = requests.get(
    f"http://localhost:8001/api/v1/workflows/agent-workflows/{workflow_id}/stats",
    headers={"Authorization": f"Bearer {token}"}
).json()

# Team performance
team_perf = requests.get(
    f"http://localhost:8001/api/v1/teams/{team_id}/performance",
    headers={"Authorization": f"Bearer {token}"}
).json()

# LLM cost analysis
cost_analysis = requests.get(
    "http://localhost:8001/api/v1/llm/cost/analysis?days=30",
    headers={"Authorization": f"Bearer {token}"}
).json()
```

## Migration from Phase 4

### Upgrading Existing Agents
Existing Phase 4 agents can be enhanced with Phase 5 features:

```python
# 1. Get existing agent
agent = get_agent(agent_id)

# 2. Add MCP capabilities
connection = connect_mcp("deepwiki")

# 3. Create workflows
workflow = create_workflow(
    agent_id=agent["agent_id"],
    workflow_type="qa",
    mcp_integrations=["deepwiki", "memory"]
)

# 4. Agent now has enhanced capabilities
```

### Data Migration
No data migration needed - Phase 5 adds new tables without modifying existing ones.

## Best Practices

### 1. MCP Connection Management
- Connect to MCP servers once per user
- Reuse connections across multiple requests
- Monitor connection health
- Disconnect when no longer needed

### 2. Workflow Design
- Keep workflows focused and modular
- Use appropriate workflow types
- Integrate memory for context
- Monitor execution times

### 3. Team Configuration
- Assign clear roles to team members
- Set appropriate execution orders
- Monitor team performance
- Adjust collaboration modes as needed

### 4. LLM Selection
- Set realistic cost limits
- Monitor usage patterns
- Compare model performance
- Use BYOK for production

## Troubleshooting

### Common Issues

**Issue**: MCP connection fails
```bash
# Check MCP server status
curl http://localhost:8001/api/v1/mcp/connections \
  -H "Authorization: Bearer <token>"

# Reconnect
curl -X POST http://localhost:8001/api/v1/mcp/connect \
  -H "Authorization: Bearer <token>" \
  -d '{"server_type": "deepwiki"}'
```

**Issue**: Workflow execution timeout
```python
# Check workflow status
response = requests.get(
    f"/api/v1/workflows/agent-workflows/{workflow_id}/stats"
)
# Adjust workflow steps or increase timeout
```

**Issue**: Team coordination fails
```python
# Check team members
members = requests.get(f"/api/v1/teams/{team_id}/members")
# Verify all agents are active
# Check execution order
```

## Support & Resources

- **API Documentation**: http://localhost:8001/docs
- **Phase 5 Complete Docs**: `docs/phase5/PHASE5_IMPLEMENTATION_COMPLETE.md`
- **Service Code**: `auralink-ai-core/app/services/`
- **Database Schema**: `scripts/db/migrations/005_phase5_mcp_agents_schema.sql`

---

*For more information, see the complete Phase 5 documentation.*

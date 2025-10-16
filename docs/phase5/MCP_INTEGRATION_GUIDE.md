# 🔌 MCP Integration Guide - Phase 5

**AuraLinkRTC Model Context Protocol Integration**

---

## 📋 Overview

This guide provides comprehensive instructions for integrating and deploying Model Context Protocol (MCP) servers with AuraLinkRTC's AI Core microservice.

### What is MCP?

Model Context Protocol (MCP) is a standardized way for AI applications to connect with external data sources and tools. MCP servers provide specialized capabilities that enhance AI agents with real-time access to:

- **DeepWiki**: GitHub repositories and documentation
- **Memory Graph**: Knowledge graphs for structured memory
- **Sequential Thinking**: Step-by-step reasoning engines
- **Supabase**: Live database queries

---

## 🚀 Quick Start

### 1. Configuration

The MCP configuration is located at `shared/configs/mcp-config.yaml`. Update the endpoint URLs for your MCP servers:

```yaml
mcp_servers:
  deepwiki:
    enabled: true
    endpoint: "https://your-deepwiki-mcp-server.com/v1"
    # ... additional config
```

### 2. Environment Variables

Set up authentication credentials:

```bash
# .env file
DEEPWIKI_MCP_API_KEY=your_deepwiki_key
MEMORY_MCP_API_KEY=your_memory_key
SEQUENTIAL_THINKING_MCP_API_KEY=your_thinking_key
SUPABASE_MCP_API_KEY=your_supabase_key
MCP_ENCRYPTION_KEY=your_encryption_key_for_byok
```

### 3. Database Initialization

The MCP tables are created via the Phase 5 migration:

```bash
psql $DATABASE_URL -f scripts/db/migrations/005_phase5_mcp_agents_schema.sql
```

---

## 🏗️ Architecture

### MCP Service Flow

```
User Request → FastAPI Endpoint → MCP Service → HTTP Client → MCP Server
                    ↓
              Database Logging
                    ↓
            Analytics & Metrics
```

### Components

1. **MCPService** (`app/services/mcp_service.py`)
   - Manages MCP server connections
   - Executes MCP operations
   - Handles authentication and credentials
   - Provides graceful fallbacks

2. **Database Tables**
   - `mcp_servers`: Server registry
   - `user_mcp_connections`: User-specific connections
   - `mcp_operation_logs`: Operation tracking

3. **API Endpoints** (`app/api/mcp.py`)
   - Connection management
   - DeepWiki operations
   - Memory graph operations
   - Sequential thinking
   - Supabase queries

---

## 🔧 Deployment Options

### Option 1: Hosted MCP Services (Recommended)

Use managed MCP services for production:

1. Sign up for MCP service providers
2. Obtain API keys
3. Update `mcp-config.yaml` with endpoints
4. Set environment variables
5. Restart AI Core service

### Option 2: Self-Hosted MCP Servers

Deploy your own MCP servers:

1. **DeepWiki MCP Server**
   ```bash
   # Clone and deploy DeepWiki MCP server
   git clone https://github.com/modelcontextprotocol/deepwiki-server
   cd deepwiki-server
   npm install
   npm run build
   npm start
   ```

2. **Memory MCP Server**
   ```bash
   # Deploy Memory graph MCP server
   docker run -d \
     -p 8081:8081 \
     -e POSTGRES_URL=$DATABASE_URL \
     mcp/memory-server:latest
   ```

3. **Sequential Thinking MCP Server**
   ```bash
   # Deploy thinking MCP server
   docker run -d \
     -p 8082:8082 \
     -e OPENAI_API_KEY=$OPENAI_API_KEY \
     mcp/sequential-thinking:latest
   ```

4. **Supabase MCP Server**
   ```bash
   # Deploy Supabase MCP server
   docker run -d \
     -p 8083:8083 \
     -e SUPABASE_URL=$SUPABASE_URL \
     -e SUPABASE_KEY=$SUPABASE_SERVICE_KEY \
     mcp/supabase-server:latest
   ```

### Option 3: Development Mode with Fallbacks

For development without MCP servers:

```yaml
environment:
  mode: "development"
  development:
    use_mock_servers: false
    fallback_always: true
```

The service will operate with fallback responses for testing.

---

## 📡 MCP Server Implementation

### HTTP API Contract

All MCP servers should implement these endpoints:

#### DeepWiki Server

```
POST /read_wiki
Body: { "repo_name": "owner/repo" }
Response: { "repo": "...", "contents": "...", "structure": [...] }

POST /ask_question
Body: { "repo_name": "owner/repo", "question": "..." }
Response: { "question": "...", "answer": "...", "sources": [...] }
```

#### Memory Server

```
POST /create_entities
Body: { "entities": [...] }
Response: { "created_count": N, "entity_ids": [...] }

POST /search_nodes
Body: { "query": "..." }
Response: { "results": [...] }

GET /read_graph
Response: { "nodes": [...], "edges": [...] }
```

#### Sequential Thinking Server

```
POST /think
Body: { "problem": "...", "max_thoughts": 10 }
Response: { "problem": "...", "thoughts": [...], "conclusion": "..." }
```

#### Supabase Server

```
POST /execute_sql
Body: { "query": "...", "project_id": "..." }
Response: { "rows": [...], "row_count": N }

GET /list_tables
Query: project_id=...
Response: { "tables": [...] }
```

---

## 🔐 Security

### Authentication

MCP connections support multiple auth methods:

- **Bearer Token**: Standard OAuth2 bearer tokens
- **API Key**: Custom API keys
- **OAuth**: Full OAuth2 flow

### Credential Encryption

User API keys are encrypted in the database:

```python
# Credentials are automatically encrypted
await mcp_service.connect_mcp_server(
    user_id=user_id,
    server_type='deepwiki',
    credentials={'api_key': 'user_provided_key'}  # Encrypted before storage
)
```

### Row Level Security

RLS policies ensure users can only access their own MCP connections:

```sql
CREATE POLICY user_mcp_connections_policy ON user_mcp_connections
    FOR ALL
    USING (user_id = current_setting('app.current_user_id')::UUID);
```

---

## 📊 Monitoring & Analytics

### Operation Logging

All MCP operations are logged for analytics:

```sql
SELECT 
    operation_name,
    COUNT(*) AS total_operations,
    AVG(latency_ms) AS avg_latency,
    SUM(cost_usd) AS total_cost
FROM mcp_operation_logs
WHERE created_at > NOW() - INTERVAL '7 days'
GROUP BY operation_name;
```

### Usage Metrics

```python
# Get MCP usage statistics
stats = await mcp_service.get_mcp_usage_stats(
    user_id=user_id,
    connection_id=connection_id
)

# Returns:
# {
#     'total_operations': 1234,
#     'avg_latency_ms': 250,
#     'total_tokens': 50000,
#     'total_cost_usd': 12.50,
#     'successful_operations': 1200,
#     'failed_operations': 34
# }
```

### Materialized Views

Analytics views are auto-updated:

- `mcp_usage_summary`: Server-level usage
- `agent_performance_summary`: Agent performance with MCP
- `llm_comparison_view`: LLM performance metrics

Refresh views:
```sql
SELECT refresh_phase5_analytics();
```

---

## 🧪 Testing

### 1. Test MCP Connection

```bash
curl -X POST http://localhost:8001/api/v1/mcp/connect \
  -H "Authorization: Bearer $JWT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "server_type": "deepwiki",
    "credentials": {"api_key": "test_key"}
  }'
```

### 2. Test DeepWiki Query

```bash
curl -X POST http://localhost:8001/api/v1/mcp/deepwiki/read \
  -H "Authorization: Bearer $JWT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "connection_id": "uuid-here",
    "repo_name": "facebook/react"
  }'
```

### 3. Test Memory Operations

```bash
curl -X POST http://localhost:8001/api/v1/mcp/memory/search \
  -H "Authorization: Bearer $JWT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "connection_id": "uuid-here",
    "query": "WebRTC protocols"
  }'
```

---

## 🔄 Fallback Behavior

The MCP service implements graceful fallbacks:

1. **Primary**: Attempt MCP server connection
2. **Fallback**: If connection fails, return basic response
3. **Logging**: All failures are logged for debugging
4. **User Experience**: Users receive responses even if MCP is unavailable

Example fallback response:
```json
{
  "repo": "facebook/react",
  "contents": "Documentation content...",
  "note": "Using fallback mode - configure MCP server for production"
}
```

---

## 🚨 Troubleshooting

### Common Issues

**1. Connection Timeout**
```
Error: MCP server connection timeout
Solution: Check endpoint URL, increase timeout in mcp-config.yaml
```

**2. Authentication Failed**
```
Error: 401 Unauthorized
Solution: Verify API key in environment variables
```

**3. Rate Limit Exceeded**
```
Error: 429 Too Many Requests
Solution: Adjust rate_limit settings in mcp-config.yaml
```

### Debug Mode

Enable verbose logging:

```yaml
mcp_global:
  log_level: "DEBUG"
  log_all_operations: true
```

### Health Checks

Check MCP server health:

```bash
# Check all connections
curl http://localhost:8001/api/v1/mcp/connections \
  -H "Authorization: Bearer $JWT_TOKEN"

# Check usage stats
curl http://localhost:8001/api/v1/mcp/usage/stats \
  -H "Authorization: Bearer $JWT_TOKEN"
```

---

## 📈 Performance Optimization

### Connection Pooling

Configure in `mcp-config.yaml`:

```yaml
mcp_global:
  max_connections: 50
  connection_timeout: 10
```

### Caching

Enable response caching:

```yaml
mcp_global:
  cache_enabled: true
  cache_ttl: 300  # 5 minutes
```

### Circuit Breaker

Prevent cascading failures:

```yaml
circuit_breaker:
  failure_threshold: 5
  success_threshold: 2
  timeout: 30
```

---

## 🔗 Integration with AI Agents

### LangGraph Integration

```python
# MCP operations in LangGraph workflows
async def _query_mcp(self, state: AgentState) -> AgentState:
    result = await self.mcp.deepwiki_ask_question(
        connection_id=state['mcp_connection_id'],
        repo_name='relevant/repo',
        question=state['user_question']
    )
    state['mcp_results'] = result
    return state
```

### CrewAI Integration

```python
# MCP tools for CrewAI agents
tools = []
if 'mcp_deepwiki' in member['tools']:
    tools.append(create_mcp_deepwiki_tool(mcp_service))
```

### Prefect Integration

```python
# MCP data ingestion workflows
@flow
async def mcp_data_ingestion_flow(connection_id, data_source):
    data = await fetch_from_mcp(connection_id, data_source)
    processed = await process_and_store(data)
    return processed
```

---

## 📝 Best Practices

1. **Always use connection pooling** for high-traffic applications
2. **Enable caching** for frequently accessed data
3. **Monitor usage metrics** to optimize costs
4. **Implement circuit breakers** for production resilience
5. **Use BYOK** for enterprise customers
6. **Enable encryption** for all credentials
7. **Set up alerts** for high latency or error rates
8. **Test fallback modes** before production deployment
9. **Document custom MCP servers** for your team
10. **Keep MCP servers updated** to latest versions

---

## 🎯 Next Steps

1. ✅ Configure MCP endpoints in `mcp-config.yaml`
2. ✅ Set up environment variables
3. ✅ Run database migrations
4. ✅ Test MCP connections
5. ✅ Deploy to production
6. ✅ Monitor usage and optimize
7. ✅ Train team on MCP features

---

## 📚 Additional Resources

- [MCP Specification](https://modelcontextprotocol.io/specification)
- [AuraLink Phase 5 Documentation](./PHASE5_IMPLEMENTATION_COMPLETE.md)
- [AI Agents Guide](../../AuraLinkDocs/coreai.md)
- [API Reference](http://localhost:8001/docs)

---

**Status**: ✅ Production Ready  
**Last Updated**: October 16, 2025  
**Version**: 1.0.0  
**Maintained by**: AuraLinkRTC Engineering Team

---

*© 2025 AuraLinkRTC Inc. All rights reserved.*

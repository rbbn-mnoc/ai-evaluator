# AI Evaluator Implementation Guide

## Overview

The AI Evaluator service has been successfully implemented as a separate, independent service that evaluates issue resolution quality without code duplication.

## Architecture

```
┌─────────────────────┐
│ Redmine Event Source│
│  (Issue Scanner)    │
└──────────┬──────────┘
           │
           ├──(New Issue)──────────► AI Agents (per collector)
           │
           └──(Closed Issue)───┬───► AI Agents (knowledge update)
                               │
                               └───► AI Evaluator (quality assessment)
```

## Key Design Decisions

### ✅ What Was Implemented

1. **Separate Service** (`ai-evaluator`)
   - Independent from `ai-agents`
   - Runs on MNOC AI EC2
   - Uses different AI model (Claude Opus) for unbiased evaluation
   - Async operation - doesn't block issue resolution

2. **Shared Context via MCP**
   - Reuses `redmine-mcp-server` tools
   - No code duplication
   - `ContextBuilder` class provides shared functionality

3. **Evaluation Workflow**
   - Triggered AFTER ai-agents processes closure
   - Fetches original AI analysis from Redmine notes
   - Fetches resolution notes from operators
   - Evaluates 5 metrics (1-10 scale)
   - Stores results back in Redmine

4. **Integration Points**
   - `redmine-event-source` queues evaluations after closure
   - Can be enabled/disabled via `ENABLE_EVALUATIONS` env var
   - Uses basic auth for security

### ❌ What Was NOT Implemented (Alternatives Rejected)

1. **Splitting ai-agents into 2 apps** - Rejected because:
   - Would duplicate context gathering logic
   - Single app with different prompts is simpler
   - No clear benefit

2. **Shared library for all services** - Partially implemented:
   - Created `ContextBuilder` in ai-evaluator
   - Can be extracted to separate package if needed later
   - Current approach avoids premature abstraction

## File Structure

```
ai-evaluator/
├── src/ai_evaluator/
│   ├── __init__.py
│   ├── main.py              # FastAPI service entry point
│   ├── evaluator.py         # Core evaluation agent
│   ├── prompts.py           # Evaluation prompts (different from ai-agents)
│   ├── mcp_client.py        # MCP client for tool calls
│   └── context_builder.py   # Shared context building (reusable)
├── tests/
│   ├── __init__.py
│   └── test_prompts.py
├── Dockerfile
├── docker-compose.yml
├── buildspec.yaml           # CI/CD
├── pyproject.toml
├── .env.example
└── README.md
```

## Evaluation Metrics

Each closed issue receives scores (1-10) for:

1. **Solution Quality** - Was the AI recommendation sound?
2. **Adherence to Solution** - Did operator follow recommendations?
3. **Operator Effort** - Work required (10 = minimal effort)
4. **Automation Potential** - Could this be automated?
5. **Resolution Efficiency** - Overall efficiency score

## Configuration

### Environment Variables

Add to `.env` for `redmine-event-source`:
```env
# Enable/disable evaluations
ENABLE_EVALUATIONS=true
AI_EVALUATOR_URL=http://ai-evaluator:8001/evaluate
AI_EVALUATOR_USERNAME=evaluator
AI_EVALUATOR_PASSWORD=changeme
```

Add to `.env` for `ai-evaluator`:
```env
# Redmine
REDMINE_URL=https://your-redmine.com
REDMINE_API_KEY=your-api-key

# MCP Server
MCP_SERVER_URL=http://redmine-mcp-server:8000
MCP_USERNAME=mcp-user
MCP_PASSWORD=mcp-password

# AI Model
ANTHROPIC_API_KEY=your-anthropic-key
EVALUATION_MODEL=claude-opus-4
MAX_TOKENS=4096

# Service Auth
SERVICE_USERNAME=evaluator
SERVICE_PASSWORD=changeme

# Logging
LOG_LEVEL=INFO
```

## Deployment

### Docker Compose (Production)

The service is already added to:
- `/home/petr/Projects/rbbn-mnoc/mnoc-ai/mnoc-ai/templates/docker-compose.prod.yaml`
- `/home/petr/Projects/rbbn-mnoc/mnoc-ai/mnoc-ai/templates/docker-compose.dev.yaml`

### Build & Deploy

```bash
cd /home/petr/Projects/rbbn-mnoc/mnoc-ai/ai-evaluator

# Build image
docker build -t ai-evaluator:latest .

# Or use docker-compose
docker-compose up --build
```

### CI/CD

AWS CodeBuild is configured via `buildspec.yaml` to:
1. Build Docker image
2. Tag with commit hash
3. Push to ECR: `699576618538.dkr.ecr.eu-central-1.amazonaws.com/prod/mnoc/ai/ai-evaluator`

## API Endpoints

### POST /evaluate
Evaluate a closed issue (called by redmine-event-source).

**Auth**: Basic Auth (SERVICE_USERNAME/SERVICE_PASSWORD)

**Request**:
```json
{
  "issue_id": 123,
  "project_identifier": "project",
  "subject": "Issue subject",
  ...
}
```

**Response**:
```json
{
  "success": true,
  "issue_id": 123,
  "message": "Evaluation completed and stored",
  "evaluation": {
    "metrics": {
      "solution_quality": 8,
      "adherence_to_solution": 7,
      "operator_effort": 6,
      "automation_potential": 9,
      "resolution_efficiency": 7
    },
    "analysis": {...},
    "summary": "..."
  }
}
```

### GET /health
Health check endpoint.

### GET /stats
Statistics endpoint (placeholder for future implementation).

## Code Reuse Strategy

### Shared Context Building

The `ContextBuilder` class in `ai-evaluator/src/ai_evaluator/context_builder.py` provides:

```python
class ContextBuilder:
    async def build_issue_context(issue_data, ...) -> dict
    async def get_resolution_notes(issue_id) -> str
    async def get_ai_analysis(issue_id) -> str
```

**This can be used by both services:**
- ai-evaluator uses it now
- ai-agents can refactor to use it in the future

### No Duplication

- Both services use **same MCP server** for tools
- Both services use **same Redmine API** connection
- Context fetching logic is shared via `ContextBuilder`
- Prompts are different (by design - different purposes)

## Testing

```bash
cd /home/petr/Projects/rbbn-mnoc/mnoc-ai/ai-evaluator

# Run tests
uv pip install pytest pytest-asyncio
python -m pytest tests/
```

## Monitoring

### Logs
```bash
# View evaluator logs
docker logs ai-evaluator -f

# View event source logs (evaluation queuing)
docker logs redmine-event-source -f | grep "evaluation"
```

### Health Checks
```bash
curl http://localhost:8001/health
```

## Future Enhancements

1. **Statistics Dashboard**
   - Implement `/stats` endpoint
   - Track evaluation trends
   - Identify automation opportunities

2. **Evaluation Storage**
   - Currently stores in Redmine custom fields
   - Could add database for analytics
   - Export to BI tools

3. **Automated Actions**
   - Auto-create improvement tickets
   - Flag high-automation-potential issues
   - Training data for ML models

4. **Shared Library** (if needed)
   - Extract `ContextBuilder` to separate package
   - Share between ai-agents and ai-evaluator
   - Only do if duplication becomes a problem

## Troubleshooting

### Evaluations not triggering

Check:
1. `ENABLE_EVALUATIONS=true` in redmine-event-source
2. AI evaluator service is running: `docker ps | grep ai-evaluator`
3. Check logs: `docker logs redmine-event-source | grep evaluation`

### Authentication errors

Verify:
- `SERVICE_USERNAME` and `SERVICE_PASSWORD` match between services
- MCP credentials are correct for fetching context

### Evaluation failures

Check:
1. `ANTHROPIC_API_KEY` is valid
2. Model name is correct (`claude-opus-4`)
3. MCP server is accessible from evaluator
4. Redmine API credentials work

## Summary

✅ **Implemented**: Separate evaluation service with no code duplication
✅ **Architecture**: Reuses MCP server, independent operation
✅ **Integration**: Automatic evaluation after issue closure  
✅ **Metrics**: 5 key metrics (1-10 scale) for quality assessment
✅ **Deployment**: Docker compose ready, CI/CD configured
✅ **Code Reuse**: Shared ContextBuilder, same MCP tools

The solution provides unbiased post-resolution evaluation without duplicating context gathering logic or splitting ai-agents.

# AI Evaluator Service

Post-resolution quality assessment and automation potential evaluation service for MNOC AI.

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        MNOC AI Infrastructure                    │
│                                                                  │
│  ┌──────────────────┐      ┌─────────────────────────────────┐ │
│  │ Redmine Event    │      │ Redmine MCP Server              │ │
│  │ Source           │◄────►│ (Shared Tools)                  │ │
│  │                  │      │ - Zabbix tools                  │ │
│  └─────┬────────────┘      │ - Redmine tools                 │ │
│        │                   │ - Knowledge tools               │ │
│        │                   │ - KEDB tools                    │ │
│        │ New Issue         └──────────▲──────────────────────┘ │
│        ├─────────────────────────►    │                        │
│        │                   ┌──────────┴──────────┐             │
│        │                   │ AI Agents           │             │
│        │                   │ (Per Collector)     │             │
│        │                   │ - Issue Analysis    │             │
│        │ Closed Issue      │ - Recommendations   │             │
│        ├─────────────────► │ - Knowledge Update  │             │
│        │                   └─────────────────────┘             │
│        │                                                        │
│        │ Closed Issue      ┌─────────────────────┐             │
│        └─────────────────► │ AI Evaluator (NEW)  │◄────┐      │
│                            │ - Quality Assessment│     │      │
│                            │ - Automation Check  │     │      │
│                            │ - Metrics (1-10)    │     │      │
│                            └──────────┬──────────┘     │      │
│                                       │                │      │
│                            Reuses MCP Server───────────┘      │
│                            (No Code Duplication)              │
└──────────────────────────────────────────────────────────────┘
```

## Purpose

This service evaluates closed Redmine issues to assess:
- Quality of AI-provided solutions
- How well human operators followed recommendations
- Level of effort required by operators
- Potential for automation
- Overall resolution efficiency

**Storage**: Results are stored in both Redmine (as notes) and ClickHouse (for analytics).

## Architecture

- **Independent service** running on MNOC AI EC2
- Uses **different AI model** (Claude Opus) for unbiased evaluation
- Reuses **MCP server** for context gathering (no code duplication)
- Runs **asynchronously** after issue closure
- Stores evaluations in Redmine custom fields

## Setup

```bash
uv venv
source .venv/bin/activate
uv pip install -e .
```

## Configuration

Copy `.env.example` to `.env` and configure:

```env
REDMINE_URL=https://your-redmine.com
REDMINE_USERNAME=your-username
REDMINE_PASSWORD=your-password
# or
REDMINE_API_KEY=your-api-key

MCP_SERVER_URL=http://redmine-mcp-server:8000
MCP_USERNAME=mcp-user
MCP_PASSWORD=mcp-password

ANTHROPIC_API_KEY=your-anthropic-key
EVALUATION_MODEL=claude-opus-4

# Service configuration
SERVER_HOST=0.0.0.0
SERVER_PORT=8001
POLL_INTERVAL=60

# ClickHouse (optional - for analytics)
CLICKHOUSE_URL=http://clickhouse:8123
CLICKHOUSE_USER=default
CLICKHOUSE_PASSWORD=your-password
CLICKHOUSE_DATABASE=default
```

## Database Setup

### ClickHouse Schema

Create the database schema for analytics:

```bash
cd schema/
clickhouse-client --host your-clickhouse-server --multiquery < clickhouse_schema.sql
```

See [schema/README.md](schema/README.md) for details on:
- Table structure
- Materialized views
- Example queries
- Grafana integration

## Running

Development:
```bash
python src/ai_evaluator/main.py
```

Production (via Docker):
```bash
docker-compose up ai-evaluator
```

## Metrics Output

Each evaluation produces scores (1-10) for:
- `solution_quality`: Was the AI recommendation sound?
- `adherence_to_solution`: Did operator follow the recommendation?
- `operator_effort`: Work required (10 = minimal effort)
- `automation_potential`: Could this be automated?
- `resolution_efficiency`: Overall efficiency score

Results are stored in:
1. **Redmine** - As issue notes for operator visibility
2. **ClickHouse** - For analytics, dashboards, and trend analysis

## Analytics

Query ClickHouse for insights:

```bash
# Get automation candidates
curl -u evaluator:password http://localhost:8001/stats

# Or query ClickHouse directly
clickhouse-client --query="
SELECT issue_id, project_identifier, automation_potential, automation_recommendations
FROM ai_evaluations 
WHERE automation_potential >= 8 
ORDER BY automation_potential DESC LIMIT 10"
```

See [schema/README.md](schema/README.md) for more query examples.

## Integration

Triggered by `redmine-event-source` after issue closure processing.

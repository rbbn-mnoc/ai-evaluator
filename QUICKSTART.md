# Quick Start Guide - AI Evaluator

## Prerequisites

1. Running MNOC AI infrastructure with:
   - `redmine-mcp-server`
   - `redmine-event-source`
   - At least one collector with `ai-agents`

2. Anthropic API key for Claude Opus

## Step 1: Configure Environment

Create `.env` file in `ai-evaluator/`:

```bash
cd /home/petr/Projects/rbbn-mnoc/mnoc-ai/ai-evaluator
cp .env.example .env
```

Edit `.env`:
```env
# Redmine
REDMINE_URL=https://your-redmine.com
REDMINE_API_KEY=your-api-key

# MCP Server
MCP_SERVER_URL=http://redmine-mcp-server:8000
MCP_USERNAME=your-mcp-user
MCP_PASSWORD=your-mcp-password

# AI Model
ANTHROPIC_API_KEY=sk-ant-xxxxxxxxxxxx
EVALUATION_MODEL=claude-opus-4

# Service Auth
SERVICE_USERNAME=evaluator
SERVICE_PASSWORD=generate-secure-password
```

## Step 2: Update redmine-event-source

Edit `.env` for redmine-event-source:

```env
# Add these lines
ENABLE_EVALUATIONS=true
AI_EVALUATOR_URL=http://ai-evaluator:8001/evaluate
AI_EVALUATOR_USERNAME=evaluator
AI_EVALUATOR_PASSWORD=same-password-as-above
```

## Step 3: Deploy

### Option A: Docker Compose (MNOC AI EC2)

```bash
# Update main docker-compose (already done)
cd /home/petr/Projects/rbbn-mnoc/mnoc-ai/mnoc-ai
docker-compose -f templates/docker-compose.prod.yaml up -d ai-evaluator

# Restart event source to pick up new config
docker-compose -f templates/docker-compose.prod.yaml restart redmine-event-source
```

### Option B: Standalone Testing

```bash
cd /home/petr/Projects/rbbn-mnoc/mnoc-ai/ai-evaluator
docker-compose up --build
```

## Step 4: Verify

```bash
# Check health
curl http://localhost:8001/health

# Check logs
docker logs ai-evaluator -f

# Trigger evaluation by closing an issue in Redmine
# Watch logs for:
# - redmine-event-source: "📊 Queued issue #123 for evaluation"
# - ai-evaluator: "Starting evaluation for issue #123"
```

## Step 5: View Results

Check Redmine issue notes for evaluation results showing:
- Metrics (1-10 scores)
- Analysis and recommendations
- Automation potential

## Troubleshooting

**No evaluations happening?**
```bash
# Check if enabled
docker exec redmine-event-source env | grep ENABLE_EVALUATIONS

# Check connectivity
docker exec ai-evaluator curl http://redmine-mcp-server:8000/health
```

**Authentication errors?**
```bash
# Test auth
curl -u evaluator:your-password http://localhost:8001/health
```

**Evaluation fails?**
```bash
# Check logs
docker logs ai-evaluator | grep ERROR

# Verify Anthropic API key
docker exec ai-evaluator env | grep ANTHROPIC_API_KEY
```

## Next Steps

1. Monitor evaluations for first few issues
2. Adjust `EVALUATION_MODEL` if needed (e.g., claude-sonnet-4 for faster/cheaper)
3. Configure Redmine custom fields for storing metrics
4. Set up dashboards for evaluation analytics

## Cost Considerations

- Claude Opus is expensive (~$15 per 1M input tokens)
- For high volume, consider:
  - Using Claude Sonnet instead (cheaper, still good)
  - Sampling evaluations (evaluate 10% of issues)
  - Batch processing during off-hours

To reduce costs, use `.env`:
```env
EVALUATION_MODEL=claude-sonnet-4  # Cheaper alternative
```

Or disable for testing:
```env
ENABLE_EVALUATIONS=false  # In redmine-event-source
```

## Support

See [IMPLEMENTATION_GUIDE.md](IMPLEMENTATION_GUIDE.md) for detailed architecture and troubleshooting.

# AI Evaluator Deployment Configuration

## Architecture Overview

The `ai-evaluator` service runs on **collector-specific EC2 instances**, not on the central MNOC AI server.

### Service Locations

- **redmine-mcp-server**: Central MNOC AI server (172.31.33.44)
- **redmine-event-source**: Central MNOC AI server  
- **ai-agents**: Each collector EC2 instance (project-specific)
- **ai-evaluator**: Each collector EC2 instance (project-specific) ⭐ **NEW**

### Why This Architecture?

1. **Multiple instances**: Each project has its own collector EC2 instance with dedicated ai-agents and ai-evaluator services
2. **Dynamic routing**: `redmine-event-source` builds URLs dynamically using collector hostnames from Route53 DNS:
   - Format: `{collector-name}.{dns-zone}` (e.g., `maas-prod-ribbonit-collector1.prod.mnoc`)
   - Ports: `8001` for ai-agents, `8002` for ai-evaluator
3. **No local URLs**: Docker Compose URLs like `http://ai-evaluator:8001` don't work because services run on different machines

## Port Assignments

### Collector EC2 Instance Ports
- **10051** - zabbix-proxy
- **162/161** - snmptrap (UDP)
- **9005** - sbc-api-proxy
- **8001** - ai-agents ✅
- **8002** - ai-evaluator ✅ (changed from 8001 to avoid conflict)
- **5123** - vector (UDP, localhost only)
- **5124** - vector (TCP, localhost only)
- **5505** - zabbix-alerts

## Deployment Files

### Collector Docker Compose
**Location**: `~/Projects/rbbn-mnoc/collector/mnoc-collector/templates/docker-compose.yaml`

Services added:
- `ai-evaluator` (port 8002)

Configuration:
```yaml
ai-evaluator:
  image: "699576618538.dkr.ecr.eu-central-1.amazonaws.com/${AI_EVALUATOR_ENV}/mnoc/ai/ai-evaluator:latest"
  container_name: ai-evaluator
  ports:
    - "8002:8002"
  environment:
    - SERVER_HOST=0.0.0.0
    - SERVER_PORT=8002
    - CUSTOMER=${PROJECT}
    - MCP_BASE_URL=http://172.31.33.44:8000/mcp/
    - MCP_API_KEY=${MCP_API_KEY}
    - BEDROCK_MODEL_ARN=arn:aws:bedrock:us-west-2:429293155916:inference-profile/us.anthropic.claude-opus-4-20250514-v1:0
    - SERVICE_USERNAME=${AI_EVALUATOR_USERNAME:-evaluator}
    - SERVICE_PASSWORD=${AI_EVALUATOR_PASSWORD:-changeme}
    - CLICKHOUSE_URL=${CLICKHOUSE_URL}
    - CLICKHOUSE_USER=${CLICKHOUSE_USER}
    - CLICKHOUSE_PASSWORD=${CLICKHOUSE_PASSWORD}
    - CLICKHOUSE_DATABASE=${CLICKHOUSE_DATABASE:-mnoc_prod}
  profiles:
    - ai-evaluator
```

### Redmine Event Source
**Location**: `~/Projects/rbbn-mnoc/mnoc-ai/redmine-event-source/src/redmine_event_source/main.py`

Changes:
- Added `AI_EVALUATOR_PORT = 8002` configuration
- Updated `queue_for_evaluation()` to build dynamic URLs like ai-agents
- Removed hardcoded `AI_EVALUATOR_URL` environment variable (builds from collector hostname)

URL building logic:
```python
collector_name = notification.get("collector_name")  # From Redmine custom field 54
hostname = f"{collector_name}.{DNS_ZONE}"  # e.g., maas-prod-ribbonit-collector1.prod.mnoc
evaluator_url = f"http://{hostname}:{AI_EVALUATOR_PORT}/evaluate"
```

### MNOC AI Docker Compose (Removed)
**Locations**:
- `~/Projects/rbbn-mnoc/mnoc-ai/mnoc-ai/templates/docker-compose.prod.yaml`
- `~/Projects/rbbn-mnoc/mnoc-ai/mnoc-ai/templates/docker-compose.dev.yaml`

Changes:
- Removed `ai-evaluator` service (doesn't belong on central server)
- Removed `ai-evaluator-data` volume
- Updated `redmine-event-source` to remove `AI_EVALUATOR_URL` environment variable

## Environment Variables

### Collector .env File
```bash
# AI Evaluator (runs on collector)
AI_EVALUATOR_ENV=prod  # or dev
AI_EVALUATOR_USERNAME=evaluator
AI_EVALUATOR_PASSWORD=changeme

# MCP Server (central)
MCP_API_KEY=your-mcp-api-key

# ClickHouse (central analytics)
CLICKHOUSE_URL=http://clickhouse-server:8123
CLICKHOUSE_USER=default
CLICKHOUSE_PASSWORD=your-password
CLICKHOUSE_DATABASE=mnoc_prod

# AWS Bedrock
AWS_REGION=us-west-2
```

### Redmine Event Source .env File
```bash
# Collector routing
COLLECTOR_CUSTOM_FIELD_ID=54
DNS_ZONE=prod.mnoc
AI_AGENTS_PORT=8001
AI_EVALUATOR_PORT=8002

# Evaluator credentials
AI_EVALUATOR_USERNAME=evaluator
AI_EVALUATOR_PASSWORD=changeme
ENABLE_EVALUATIONS=true
```

## Deployment Steps

### 1. Build and Push Docker Image
```bash
cd ~/Projects/rbbn-mnoc/mnoc-ai/ai-evaluator

# Build (happens automatically via CodeBuild on git push)
# Or manually:
docker build -t ai-evaluator:latest .

# Tag and push to ECR
aws ecr get-login-password --region eu-central-1 | docker login --username AWS --password-stdin 699576618538.dkr.ecr.eu-central-1.amazonaws.com
docker tag ai-evaluator:latest 699576618538.dkr.ecr.eu-central-1.amazonaws.com/prod/mnoc/ai/ai-evaluator:latest
docker push 699576618538.dkr.ecr.eu-central-1.amazonaws.com/prod/mnoc/ai/ai-evaluator:latest
```

### 2. Deploy to Collector EC2 Instances
```bash
# SSH to each collector instance
ssh ec2-user@{collector-hostname}

# Update docker-compose.yaml if needed
cd /opt/mnoc-collector

# Start ai-evaluator service
docker compose --profile ai-evaluator up -d

# Verify it's running
docker ps | grep ai-evaluator
curl -u evaluator:changeme http://localhost:8002/health
```

### 3. Verify Evaluation Flow
1. Close an issue in Redmine
2. Check redmine-event-source logs: should show "📊 Queued issue #{issue_id} for evaluation"
3. Check ai-evaluator logs on the collector: should show evaluation request
4. Verify evaluation stored in ClickHouse:
   ```sql
   SELECT * FROM mnoc_prod.ai_evaluations ORDER BY evaluated_at DESC LIMIT 5;
   ```
5. Check Redmine issue notes for evaluation results

## Monitoring

### Health Checks
```bash
# AI Evaluator health
curl http://{collector-hostname}:8002/health

# Check logs
docker logs ai-evaluator -f --tail 100

# Check stats endpoint
curl -u evaluator:changeme http://{collector-hostname}:8002/stats
```

### Common Issues

**Issue**: Evaluator not receiving requests  
**Solution**: Check collector_name in Redmine custom field 54, verify DNS resolution

**Issue**: Port conflict on 8001  
**Solution**: ai-evaluator now uses port 8002

**Issue**: MCP authentication failure  
**Solution**: Verify MCP_API_KEY matches redmine-mcp-server configuration

**Issue**: ClickHouse connection error  
**Solution**: Check CLICKHOUSE_URL, credentials, and network connectivity

## Scaling

Each new project/collector requires:
1. Deploy collector EC2 instance with docker-compose
2. Enable `ai-evaluator` profile in docker-compose
3. Configure environment variables in .env
4. Watchtower automatically pulls latest image

No changes needed to:
- redmine-event-source (builds URLs dynamically)
- redmine-mcp-server (shared central service)
- ClickHouse (shared central analytics database)

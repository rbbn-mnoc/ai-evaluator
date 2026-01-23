# ClickHouse Integration Summary

## What Was Added

### 1. Database Schema

**File**: [schema/clickhouse_schema.sql](schema/clickhouse_schema.sql)

Created comprehensive schema with:
- **Main table**: `ai_evaluations` - stores all evaluation results
  - Partitioned by month for query performance
  - 2-year TTL for data retention
  - Indexes on key metrics

- **Materialized views**:
  - `ai_evaluations_daily_mv` - daily aggregates
  - `ai_evaluations_project_summary_mv` - monthly summaries

### 2. ClickHouse Client

**File**: [src/ai_evaluator/clickhouse_client.py](../src/ai_evaluator/clickhouse_client.py)

Features:
- Async HTTP client for ClickHouse
- `store_evaluation()` - saves results to database
- `get_automation_candidates()` - top automation opportunities
- `get_quality_trends()` - quality metrics over time
- Automatic metric calculations (overall_score, flags)

### 3. Updated Service

**File**: [src/ai_evaluator/main.py](../src/ai_evaluator/main.py)

Changes:
- Initialize ClickHouse client on startup
- Store evaluations in both Redmine AND ClickHouse
- Enhanced `/stats` endpoint with real data from ClickHouse
- Graceful degradation if ClickHouse unavailable

### 4. Docker Configuration

Updated docker-compose files to include:
```yaml
- CLICKHOUSE_URL=${CLICKHOUSE_URL}
- CLICKHOUSE_USER=${CLICKHOUSE_USER}
- CLICKHOUSE_PASSWORD=${CLICKHOUSE_PASSWORD}
- CLICKHOUSE_DATABASE=${CLICKHOUSE_DATABASE:-default}
```

## Environment Variables

Add to your `.env`:

```env
# ClickHouse (optional - service works without it)
CLICKHOUSE_URL=http://clickhouse:8123
CLICKHOUSE_USER=default
CLICKHOUSE_PASSWORD=your-password
CLICKHOUSE_DATABASE=default
```

## Database Schema Highlights

### Main Table Structure

```sql
CREATE TABLE ai_evaluations (
    issue_id UInt32,
    project_identifier String,
    evaluated_at DateTime,
    
    -- Metrics (1-10)
    solution_quality UInt8,
    adherence_to_solution UInt8,
    operator_effort UInt8,
    automation_potential UInt8,
    resolution_efficiency UInt8,
    
    -- Calculated
    overall_score Float32,
    automation_candidate UInt8,  -- 1 if automation_potential >= 7
    requires_attention UInt8,    -- 1 if any metric < 5
    
    -- Analysis
    automation_recommendations String,
    summary String,
    ...
) ENGINE = MergeTree()
PARTITION BY toYYYYMM(evaluated_at)
ORDER BY (project_identifier, evaluated_at, issue_id)
TTL evaluated_at + INTERVAL 2 YEAR;
```

### Key Features

1. **Partitioning** - By month for fast time-range queries
2. **TTL** - Automatic cleanup after 2 years
3. **Indexes** - On `automation_potential` and `solution_quality`
4. **Materialized Views** - Pre-aggregated data for dashboards

## Usage

### Setup Database

```bash
cd /home/petr/Projects/rbbn-mnoc/mnoc-ai/ai-evaluator/schema
clickhouse-client --host your-clickhouse-server --multiquery < clickhouse_schema.sql
```

### Query Examples

**Top Automation Candidates:**
```sql
SELECT issue_id, project_identifier, automation_potential, automation_recommendations
FROM ai_evaluations
WHERE automation_potential >= 8
ORDER BY automation_potential DESC
LIMIT 20;
```

**Quality Trends:**
```sql
SELECT 
    toStartOfWeek(evaluated_at) AS week,
    avg(solution_quality) AS avg_quality,
    count() AS total
FROM ai_evaluations
WHERE evaluated_at >= now() - INTERVAL 30 DAY
GROUP BY week
ORDER BY week DESC;
```

**Project Performance:**
```sql
SELECT 
    project_identifier,
    count() AS total,
    avg(automation_potential) AS avg_automation,
    countIf(automation_candidate = 1) AS high_potential
FROM ai_evaluations
GROUP BY project_identifier
ORDER BY avg_automation DESC;
```

### Via API

```bash
# Get statistics (uses ClickHouse)
curl -u evaluator:password http://localhost:8001/stats
```

## Benefits

1. **Analytics** - Query evaluation trends, patterns, automation opportunities
2. **Dashboards** - Integrate with Grafana for visualizations
3. **Performance** - Materialized views for fast aggregations
4. **Scalability** - ClickHouse handles millions of rows efficiently
5. **Retention** - Automatic TTL-based cleanup

## Optional Feature

ClickHouse integration is **optional**:
- Service works without it (stores only in Redmine)
- If `CLICKHOUSE_URL` not set, ClickHouse is skipped
- No impact on evaluation functionality
- Only affects analytics/statistics

## Grafana Integration

Create dashboards with panels:

1. **Quality Trends** - Line chart of `avg_solution_quality` over time
2. **Automation Pipeline** - Table of issues with `automation_potential >= 8`
3. **Project Comparison** - Bar chart comparing projects
4. **Alerts** - Notify when quality drops below threshold

Example Grafana query:
```sql
SELECT 
    $__timeGroup(evaluated_at, $__interval) as time,
    avg(solution_quality) AS quality
FROM ai_evaluations
WHERE $__timeFilter(evaluated_at)
  AND project_identifier = '$project'
GROUP BY time
ORDER BY time
```

## Performance

- **Partitioning**: Queries filtered by date are very fast
- **Materialized Views**: Pre-aggregated data, instant results
- **Indexes**: Fast filtering on key metrics
- **Compression**: ZSTD compression on text fields

Expected performance:
- Insert: < 10ms per evaluation
- Query (with date filter): < 100ms
- Aggregations (materialized views): < 50ms

## Maintenance

```sql
-- Check table size
SELECT formatReadableSize(sum(bytes)) AS size, sum(rows) AS rows
FROM system.parts
WHERE table = 'ai_evaluations';

-- Optimize table (merge parts)
OPTIMIZE TABLE ai_evaluations FINAL;

-- Adjust TTL if needed
ALTER TABLE ai_evaluations MODIFY TTL evaluated_at + INTERVAL 3 YEAR;
```

## Files Changed

1. ✅ Created `schema/clickhouse_schema.sql`
2. ✅ Created `schema/README.md`
3. ✅ Created `src/ai_evaluator/clickhouse_client.py`
4. ✅ Updated `src/ai_evaluator/main.py`
5. ✅ Updated `src/ai_evaluator/__init__.py`
6. ✅ Updated `docker-compose.prod.yaml`
7. ✅ Updated `docker-compose.dev.yaml`
8. ✅ Updated `.env.example`
9. ✅ Updated `README.md`

## Summary

ClickHouse integration adds powerful analytics capabilities to the AI Evaluator service:
- Stores all evaluation results in optimized database
- Enables trend analysis and dashboards
- Pre-aggregated views for fast queries
- Optional - service works without it
- Production-ready with TTL, partitioning, and indexes

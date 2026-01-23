# ClickHouse Schema for AI Evaluations

## Overview

This directory contains the ClickHouse database schema for storing AI evaluation results.

## Schema Design

### Main Table: `ai_evaluations`

Stores comprehensive evaluation results with:
- Issue metadata (ID, project, subject, etc.)
- Evaluation metrics (1-10 scores)
- Analysis notes and recommendations
- Resolution metadata
- Partitioned by month for efficient querying
- 2-year TTL for data retention

### Materialized Views

1. **`ai_evaluations_daily_mv`** - Daily aggregates by project and issue type
2. **`ai_evaluations_project_summary_mv`** - Monthly project summaries

## Setup

### 1. Create Database (if needed)

```sql
CREATE DATABASE IF NOT EXISTS default;
```

### 2. Apply Schema

```bash
# From ClickHouse client
clickhouse-client --host your-clickhouse-server --multiquery < clickhouse_schema.sql

# Or via HTTP
cat clickhouse_schema.sql | curl 'http://your-clickhouse-server:8123/' --data-binary @-
```

### 3. Verify Tables

```sql
SHOW TABLES FROM default;

-- Should show:
-- ai_evaluations
-- ai_evaluations_daily_mv
-- ai_evaluations_project_summary_mv
```

## Example Queries

### Top Automation Candidates

```sql
SELECT 
    issue_id,
    project_identifier,
    subject,
    automation_potential,
    automation_recommendations,
    evaluated_at
FROM ai_evaluations
WHERE automation_potential >= 8
ORDER BY automation_potential DESC, evaluated_at DESC
LIMIT 20;
```

### Quality Trends

```sql
SELECT 
    toStartOfWeek(evaluated_at) AS week,
    project_identifier,
    avg(solution_quality) AS avg_quality,
    avg(automation_potential) AS avg_automation,
    count() AS total_issues
FROM ai_evaluations
WHERE evaluated_at >= now() - INTERVAL 30 DAY
GROUP BY week, project_identifier
ORDER BY week DESC, project_identifier;
```

### Issues Requiring Attention

```sql
SELECT 
    issue_id,
    project_identifier,
    subject,
    solution_quality,
    adherence_to_solution,
    operator_effort,
    summary
FROM ai_evaluations
WHERE requires_attention = 1
ORDER BY evaluated_at DESC
LIMIT 50;
```

### Project Performance Dashboard

```sql
SELECT 
    project_identifier,
    count() AS total_evaluations,
    avg(solution_quality) AS avg_solution_quality,
    avg(adherence_to_solution) AS avg_adherence,
    avg(automation_potential) AS avg_automation_potential,
    countIf(automation_candidate = 1) AS high_automation_count,
    countIf(requires_attention = 1) AS needs_attention_count,
    avg(resolution_time_seconds) / 3600 AS avg_resolution_hours
FROM ai_evaluations
WHERE evaluated_at >= now() - INTERVAL 90 DAY
GROUP BY project_identifier
ORDER BY total_evaluations DESC;
```

### Daily Metrics from Materialized View

```sql
SELECT 
    evaluation_date,
    project_identifier,
    issue_type,
    total_evaluations,
    avg_solution_quality,
    avg_automation_potential,
    automation_candidates
FROM ai_evaluations_daily_mv
WHERE evaluation_date >= today() - 30
ORDER BY evaluation_date DESC, project_identifier;
```

## Integration with Grafana

Create dashboards using these queries:

1. **Quality Over Time**: Line chart with `avg_solution_quality` by week
2. **Automation Opportunities**: Bar chart of top automation candidates
3. **Project Comparison**: Table showing all projects with key metrics
4. **Alert on Low Quality**: Alert when `avg_solution_quality < 5`

## Data Retention

- Main table: 2-year TTL
- Materialized views: Follow main table partitions
- Adjust TTL if needed:

```sql
ALTER TABLE ai_evaluations MODIFY TTL evaluated_at + INTERVAL 3 YEAR;
```

## Performance Tips

1. **Use Materialized Views** for dashboards (pre-aggregated)
2. **Filter by Date** first in WHERE clauses (leverages partitioning)
3. **Limit Results** when querying raw data
4. **Use Indexes** already created on `automation_potential` and `solution_quality`

## Backup

```bash
# Export data
clickhouse-client --query="SELECT * FROM ai_evaluations FORMAT CSVWithNames" > evaluations_backup.csv

# Import data
cat evaluations_backup.csv | clickhouse-client --query="INSERT INTO ai_evaluations FORMAT CSVWithNames"
```

## Monitoring

Check table size and row count:

```sql
SELECT 
    table,
    formatReadableSize(sum(bytes)) AS size,
    sum(rows) AS rows,
    max(modification_time) AS latest_modification
FROM system.parts
WHERE database = 'default' 
  AND table LIKE 'ai_evaluations%'
GROUP BY table
ORDER BY table;
```

## Troubleshooting

**Issue: No data appearing**
- Check ai-evaluator logs for ClickHouse connection errors
- Verify `CLICKHOUSE_URL`, `CLICKHOUSE_USER`, `CLICKHOUSE_PASSWORD` env vars
- Test connection: `curl http://clickhouse:8123/ping`

**Issue: Slow queries**
- Add date filter to WHERE clause
- Use materialized views instead of raw table
- Check EXPLAIN for query plan

**Issue: Disk space**
- Reduce TTL interval
- Archive old data
- Use OPTIMIZE TABLE to compact parts

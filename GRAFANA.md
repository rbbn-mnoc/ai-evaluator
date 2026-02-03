# Grafana Dashboard for AI Evaluation Metrics

This guide provides SQL queries and setup instructions for visualizing AI evaluation metrics in Grafana using the ClickHouse data source.

## Prerequisites

1. **ClickHouse Data Source** configured in Grafana
   - URL: `http://172.31.159.42:8123`
   - Database: `mnoc_prod`
   - User: `grafana_user` (read-only recommended)

2. **Data Available**: Evaluations stored in `mnoc_prod.ai_evaluations` table

---

## Dashboard Panels

### 1. Evaluation Count Over Time

**Panel Type:** Time series  
**Description:** Total number of evaluations per day

```sql
SELECT
    toDate(evaluated_at) AS time,
    count() AS evaluations
FROM mnoc_prod.ai_evaluations
WHERE $__timeFilter(evaluated_at)
GROUP BY time
ORDER BY time
```

**Grafana Setup:**
- Visualization: Time series
- Format: Time series
- Legend: "Total Evaluations"
- Y-axis label: "Count"

---

### 2. Average Quality Metrics Over Time

**Panel Type:** Time series (multi-line)  
**Description:** Trend of all quality metrics (1-10 scale)

```sql
SELECT
    toDate(evaluated_at) AS time,
    avg(solution_quality) AS solution_quality,
    avg(adherence_to_solution) AS adherence,
    avg(operator_effort) AS operator_effort,
    avg(automation_potential) AS automation_potential,
    avg(resolution_efficiency) AS efficiency,
    avg(overall_score) AS overall_score
FROM mnoc_prod.ai_evaluations
WHERE $__timeFilter(evaluated_at)
GROUP BY time
ORDER BY time
```

**Grafana Setup:**
- Visualization: Time series
- Format: Time series
- Legend: Show each metric name
- Y-axis: Min=0, Max=10
- Y-axis label: "Score (1-10)"
- Display: Lines with points
- Color scheme: Use different colors for each metric

---

### 3. Current Period Scorecard

**Panel Type:** Stat (multiple stats)  
**Description:** Current average scores for the selected time range

```sql
SELECT
    round(avg(solution_quality), 1) AS solution_quality,
    round(avg(adherence_to_solution), 1) AS adherence,
    round(avg(operator_effort), 1) AS operator_effort,
    round(avg(automation_potential), 1) AS automation_potential,
    round(avg(resolution_efficiency), 1) AS efficiency,
    round(avg(overall_score), 1) AS overall_score
FROM mnoc_prod.ai_evaluations
WHERE $__timeFilter(evaluated_at)
```

**Grafana Setup:**
- Visualization: Stat
- Format: Table
- Create 6 separate panels (one for each metric) or use transformations
- Value: Current value
- Graph mode: None
- Color mode: Background
- Thresholds: 
  - Red: 0-5
  - Yellow: 5-7
  - Green: 7-10
- Unit: None (just number)

---

### 4. Automation Candidates

**Panel Type:** Stat  
**Description:** Number of issues identified as good automation candidates

```sql
SELECT
    countIf(automation_candidate = 1) AS automation_candidates,
    count() AS total_evaluations,
    round((countIf(automation_candidate = 1) / count()) * 100, 1) AS percentage
FROM mnoc_prod.ai_evaluations
WHERE $__timeFilter(evaluated_at)
```

**Grafana Setup:**
- Visualization: Stat
- Display both count and percentage
- Color mode: Value
- Thresholds:
  - Green: >20%
  - Yellow: 10-20%
  - Red: <10%

---

### 5. Issues Requiring Attention

**Panel Type:** Stat  
**Description:** Issues with any metric scoring below 5

```sql
SELECT
    countIf(requires_attention = 1) AS requiring_attention,
    count() AS total_evaluations,
    round((countIf(requires_attention = 1) / count()) * 100, 1) AS percentage
FROM mnoc_prod.ai_evaluations
WHERE $__timeFilter(evaluated_at)
```

**Grafana Setup:**
- Visualization: Stat
- Color mode: Background
- Thresholds (inverted):
  - Green: <5%
  - Yellow: 5-15%
  - Red: >15%

---

### 6. Resolution Time Analysis

**Panel Type:** Time series  
**Description:** Average resolution time trend

```sql
SELECT
    toDate(evaluated_at) AS time,
    round(avg(resolution_time_seconds) / 3600, 2) AS avg_hours,
    round(quantile(0.5)(resolution_time_seconds) / 3600, 2) AS median_hours,
    round(quantile(0.9)(resolution_time_seconds) / 3600, 2) AS p90_hours
FROM mnoc_prod.ai_evaluations
WHERE $__timeFilter(evaluated_at)
GROUP BY time
ORDER BY time
```

**Grafana Setup:**
- Visualization: Time series
- Format: Time series
- Y-axis label: "Hours"
- Legend: "Average", "Median (p50)", "90th Percentile (p90)"
- Unit: Hours (h)

---

### 7. Evaluations by Project

**Panel Type:** Bar chart  
**Description:** Evaluation count and average score by project

```sql
SELECT
    project_identifier,
    count() AS evaluations,
    round(avg(overall_score), 2) AS avg_score
FROM mnoc_prod.ai_evaluations
WHERE $__timeFilter(evaluated_at)
GROUP BY project_identifier
ORDER BY evaluations DESC
LIMIT 10
```

**Grafana Setup:**
- Visualization: Bar chart
- Orientation: Horizontal
- Show values on bars
- Color by value (avg_score)
- Thresholds for color:
  - Red: 0-5
  - Yellow: 5-7
  - Green: 7-10

---

### 8. Evaluations by Issue Type

**Panel Type:** Pie chart  
**Description:** Distribution of evaluations by issue type

```sql
SELECT
    issue_type,
    count() AS count
FROM mnoc_prod.ai_evaluations
WHERE $__timeFilter(evaluated_at)
GROUP BY issue_type
ORDER BY count DESC
```

**Grafana Setup:**
- Visualization: Pie chart
- Display: Donut
- Show legend
- Show percentage
- Value: Count

---

### 9. Score Distribution Heatmap

**Panel Type:** Heatmap  
**Description:** Daily score distribution across all metrics

```sql
SELECT
    toDate(evaluated_at) AS time,
    'Solution Quality' AS metric,
    avg(solution_quality) AS score
FROM mnoc_prod.ai_evaluations
WHERE $__timeFilter(evaluated_at)
GROUP BY time

UNION ALL

SELECT
    toDate(evaluated_at) AS time,
    'Adherence' AS metric,
    avg(adherence_to_solution) AS score
FROM mnoc_prod.ai_evaluations
WHERE $__timeFilter(evaluated_at)
GROUP BY time

UNION ALL

SELECT
    toDate(evaluated_at) AS time,
    'Operator Effort' AS metric,
    avg(operator_effort) AS score
FROM mnoc_prod.ai_evaluations
WHERE $__timeFilter(evaluated_at)
GROUP BY time

UNION ALL

SELECT
    toDate(evaluated_at) AS time,
    'Automation Potential' AS metric,
    avg(automation_potential) AS score
FROM mnoc_prod.ai_evaluations
WHERE $__timeFilter(evaluated_at)
GROUP BY time

UNION ALL

SELECT
    toDate(evaluated_at) AS time,
    'Efficiency' AS metric,
    avg(resolution_efficiency) AS score
FROM mnoc_prod.ai_evaluations
WHERE $__timeFilter(evaluated_at)
GROUP BY time

ORDER BY time, metric
```

**Grafana Setup:**
- Visualization: Heatmap
- X-axis: time
- Y-axis: metric
- Cell value: score
- Color scheme: Green-Yellow-Red (0-10 scale)
- Data format: Time series buckets

---

### 10. Recent Evaluations Table

**Panel Type:** Table  
**Description:** Detailed view of recent evaluations

```sql
SELECT
    evaluated_at AS time,
    issue_id,
    project_identifier AS project,
    substring(subject, 1, 50) AS subject,
    overall_score AS score,
    solution_quality AS quality,
    automation_potential AS automation,
    automation_candidate AS auto_candidate,
    requires_attention AS attention,
    round(resolution_time_seconds / 3600, 1) AS resolution_hours
FROM mnoc_prod.ai_evaluations
WHERE $__timeFilter(evaluated_at)
ORDER BY evaluated_at DESC
LIMIT 50
```

**Grafana Setup:**
- Visualization: Table
- Column alignment: Auto
- Cell display mode: Color background for scores
- Thresholds on score columns:
  - Red: 0-5
  - Yellow: 5-7
  - Green: 7-10
- Make issue_id a link (if Redmine URL configured)
- Page size: 20

---

### 11. Improvement Priority Distribution

**Panel Type:** Bar gauge  
**Description:** Count of evaluations by improvement priority

```sql
SELECT
    improvement_priority,
    count() AS count
FROM mnoc_prod.ai_evaluations
WHERE $__timeFilter(evaluated_at)
GROUP BY improvement_priority
ORDER BY 
    CASE improvement_priority
        WHEN 'high' THEN 1
        WHEN 'medium' THEN 2
        WHEN 'low' THEN 3
    END
```

**Grafana Setup:**
- Visualization: Bar gauge
- Orientation: Horizontal
- Display: Gradient
- Value: Count
- Color by value:
  - High: Red
  - Medium: Yellow
  - Low: Green

---

### 12. Resolution Efficiency vs Automation Potential

**Panel Type:** Scatter plot  
**Description:** Correlation between efficiency and automation potential

```sql
SELECT
    resolution_efficiency AS x,
    automation_potential AS y,
    project_identifier AS series,
    issue_id AS label
FROM mnoc_prod.ai_evaluations
WHERE $__timeFilter(evaluated_at)
AND resolution_efficiency > 0
AND automation_potential > 0
LIMIT 1000
```

**Grafana Setup:**
- Visualization: Scatter plot (XY Chart)
- X-axis: Resolution Efficiency (0-10)
- Y-axis: Automation Potential (0-10)
- Point size: 5
- Series: Group by project
- Tooltip: Show issue_id

---

## Dashboard Layout Suggestion

```
┌─────────────────────────────────────────────────────────────┐
│  Dashboard Title: AI Evaluation Analytics                  │
├───────────┬───────────┬───────────┬───────────┬─────────────┤
│  Panel 3  │  Panel 3  │  Panel 3  │  Panel 4  │   Panel 5   │
│  Solution │ Adherence │ Operator  │ Automation│  Requiring  │
│  Quality  │           │  Effort   │ Candidates│  Attention  │
│   (Stat)  │  (Stat)   │  (Stat)   │   (Stat)  │   (Stat)    │
├───────────────────────────────────┴───────────┴─────────────┤
│                                                               │
│  Panel 1: Evaluation Count Over Time (Time Series)          │
│                                                               │
├───────────────────────────────────────────────────────────────┤
│                                                               │
│  Panel 2: Average Quality Metrics Over Time (Time Series)   │
│                                                               │
├────────────────────────────┬──────────────────────────────────┤
│  Panel 6: Resolution Time  │  Panel 11: Improvement Priority │
│  Analysis (Time Series)    │  Distribution (Bar Gauge)       │
├────────────────────────────┴──────────────────────────────────┤
│  Panel 7: Evaluations    │  Panel 8: Issue Type Distribution │
│  by Project (Bar Chart)  │  (Pie Chart)                      │
├──────────────────────────┴────────────────────────────────────┤
│                                                               │
│  Panel 9: Score Distribution Heatmap                         │
│                                                               │
├───────────────────────────────────────────────────────────────┤
│                                                               │
│  Panel 10: Recent Evaluations Table                          │
│                                                               │
└───────────────────────────────────────────────────────────────┘
```

---

## Creating the Dashboard

### Step 1: Add ClickHouse Data Source

1. Go to **Configuration → Data Sources**
2. Click **Add data source**
3. Select **ClickHouse**
4. Configure:
   - **Name:** `ClickHouse - MNOC Prod`
   - **URL:** `http://172.31.159.42:8123`
   - **Database:** `mnoc_prod`
   - **Username:** `grafana_user` (or your read-only user)
   - **Password:** `<password>`
5. Click **Save & Test**

### Step 2: Create New Dashboard

1. Click **+ → Dashboard**
2. Click **Add new panel**
3. Select **ClickHouse - MNOC Prod** as data source
4. Paste the SQL query from above
5. Configure visualization type and options
6. Set panel title
7. Click **Apply**

### Step 3: Configure Time Range

- Use Grafana's time range picker (top right)
- Recommended default: Last 30 days
- Add quick ranges: 7d, 30d, 90d, 1y

### Step 4: Add Variables (Optional)

Create dashboard variables for filtering:

**Project Variable:**
```sql
SELECT DISTINCT project_identifier
FROM mnoc_prod.ai_evaluations
ORDER BY project_identifier
```

**Issue Type Variable:**
```sql
SELECT DISTINCT issue_type
FROM mnoc_prod.ai_evaluations
ORDER BY issue_type
```

Then use in queries:
```sql
WHERE $__timeFilter(evaluated_at)
AND project_identifier = '$project'
AND issue_type = '$issue_type'
```

### Step 5: Save Dashboard

1. Click **Save dashboard** (disk icon)
2. Name: "AI Evaluation Analytics"
3. Add to folder: "MNOC"
4. Add tags: "ai", "evaluation", "quality"

---

## Troubleshooting

### No Data Showing

1. **Check time range:** Ensure you have evaluations in the selected period
2. **Verify database:** Run `SELECT count() FROM mnoc_prod.ai_evaluations` in ClickHouse
3. **Check permissions:** Ensure Grafana user has SELECT access

### Query Timeout

1. Add `LIMIT` clauses to queries
2. Reduce time range
3. Use materialized views for aggregations

### Slow Queries

1. Ensure proper indexes (already in schema)
2. Use materialized views: `mnoc_prod.ai_evaluations_daily_mv`
3. Add `SETTINGS max_execution_time = 30` to queries

---

## Advanced: Using Materialized Views

For faster dashboard performance, use the pre-aggregated materialized views:

**Daily Metrics (faster than raw table):**
```sql
SELECT
    evaluation_date AS time,
    avg_solution_quality AS solution_quality,
    avg_adherence AS adherence,
    avg_operator_effort AS operator_effort,
    avg_automation_potential AS automation_potential,
    avg_efficiency AS efficiency,
    avg_overall_score AS overall_score
FROM mnoc_prod.ai_evaluations_daily_mv
WHERE $__timeFilter(evaluation_date)
AND project_identifier = '$project'
GROUP BY time, solution_quality, adherence, operator_effort, automation_potential, efficiency, overall_score
ORDER BY time
```

This query is significantly faster for time-series visualizations over long periods.

---

## Alerting (Optional)

Set up Grafana alerts for:

1. **Low Overall Score Alert:**
   - Condition: Average overall_score < 6 for 24 hours
   - Notification: Slack/Email

2. **High Attention Rate Alert:**
   - Condition: Percentage requiring_attention > 20%
   - Notification: Slack/Email

3. **Low Automation Candidate Rate:**
   - Condition: Percentage automation_candidates < 10%
   - Notification: Slack/Email

---

## Export/Import Dashboard

After creating the dashboard, export it:

1. Click **Dashboard settings** (gear icon)
2. Click **JSON Model**
3. Copy JSON
4. Save to `ai-evaluator/grafana-dashboard.json`

To import on another Grafana instance:
1. Click **+ → Import**
2. Paste JSON
3. Select ClickHouse data source
4. Click **Import**

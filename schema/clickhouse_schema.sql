-- ClickHouse Schema for AI Evaluation Results
-- Optimized for analytics and time-series queries

-- Main evaluation results table
CREATE TABLE IF NOT EXISTS ai_evaluations (
    -- Primary identifiers
    evaluation_id UUID DEFAULT generateUUIDv4(),
    issue_id UInt32,
    project_id UInt32,
    project_identifier String,
    
    -- Timestamps
    evaluated_at DateTime DEFAULT now(),
    issue_created_at DateTime,
    issue_closed_at DateTime,
    resolution_time_seconds UInt32,
    
    -- Issue metadata
    subject String,
    description String,
    author String,
    tracker String,
    status String,
    priority String,
    issue_type String,  -- kedb_trap, zabbix_check, manual
    class_id String,
    
    -- AI Model info
    evaluation_model String,
    ai_analysis_model String,  -- Model used for original analysis
    
    -- Evaluation metrics (1-10)
    solution_quality UInt8,
    adherence_to_solution UInt8,
    operator_effort UInt8,
    automation_potential UInt8,
    resolution_efficiency UInt8,
    
    -- Calculated aggregate score
    overall_score Float32,
    
    -- Analysis text
    solution_quality_notes String,
    adherence_notes String,
    operator_effort_notes String,
    automation_recommendations String,
    efficiency_notes String,
    summary String,
    
    -- Priority and flags
    improvement_priority Enum8('low' = 1, 'medium' = 2, 'high' = 3),
    automation_candidate UInt8,  -- 1 if automation_potential >= 7
    requires_attention UInt8,    -- 1 if any metric < 5
    
    -- Resolution metadata
    resolve_method String,
    resolve_by String,
    alarming_state String,
    
    -- Raw data (for debugging)
    raw_response String CODEC(ZSTD(3))
    
) ENGINE = MergeTree()
PARTITION BY toYYYYMM(evaluated_at)
ORDER BY (project_identifier, evaluated_at, issue_id)
TTL evaluated_at + INTERVAL 2 YEAR
SETTINGS index_granularity = 8192;

-- Materialized view for daily aggregates
CREATE MATERIALIZED VIEW IF NOT EXISTS ai_evaluations_daily_mv
ENGINE = SummingMergeTree()
PARTITION BY toYYYYMM(evaluation_date)
ORDER BY (project_identifier, evaluation_date, issue_type)
AS SELECT
    toDate(evaluated_at) AS evaluation_date,
    project_identifier,
    issue_type,
    count() AS total_evaluations,
    avg(solution_quality) AS avg_solution_quality,
    avg(adherence_to_solution) AS avg_adherence,
    avg(operator_effort) AS avg_operator_effort,
    avg(automation_potential) AS avg_automation_potential,
    avg(resolution_efficiency) AS avg_efficiency,
    avg(overall_score) AS avg_overall_score,
    countIf(automation_candidate = 1) AS automation_candidates,
    countIf(requires_attention = 1) AS requiring_attention,
    avg(resolution_time_seconds) AS avg_resolution_time
FROM ai_evaluations
GROUP BY evaluation_date, project_identifier, issue_type;

-- Materialized view for project summaries
CREATE MATERIALIZED VIEW IF NOT EXISTS ai_evaluations_project_summary_mv
ENGINE = SummingMergeTree()
PARTITION BY toYYYYMM(month)
ORDER BY (project_identifier, month)
AS SELECT
    toStartOfMonth(evaluated_at) AS month,
    project_identifier,
    count() AS total_evaluations,
    avg(solution_quality) AS avg_solution_quality,
    avg(adherence_to_solution) AS avg_adherence,
    avg(automation_potential) AS avg_automation_potential,
    countIf(automation_candidate = 1) AS high_automation_potential,
    countIf(improvement_priority = 'high') AS high_priority_improvements,
    topK(5)(class_id) AS top_issue_classes
FROM ai_evaluations
GROUP BY month, project_identifier;

-- Index for faster filtering
CREATE INDEX IF NOT EXISTS idx_automation_potential ON ai_evaluations (automation_potential) TYPE minmax GRANULARITY 4;
CREATE INDEX IF NOT EXISTS idx_solution_quality ON ai_evaluations (solution_quality) TYPE minmax GRANULARITY 4;

-- Example queries for analytics:

-- Top automation candidates
-- SELECT issue_id, project_identifier, subject, automation_potential, automation_recommendations
-- FROM ai_evaluations
-- WHERE automation_potential >= 8
-- ORDER BY automation_potential DESC, evaluated_at DESC
-- LIMIT 20;

-- Quality trends over time
-- SELECT 
--     toStartOfWeek(evaluated_at) AS week,
--     project_identifier,
--     avg(solution_quality) AS avg_quality,
--     count() AS total_issues
-- FROM ai_evaluations
-- GROUP BY week, project_identifier
-- ORDER BY week DESC, project_identifier;

-- Issues requiring attention
-- SELECT issue_id, project_identifier, subject,
--        solution_quality, adherence_to_solution, operator_effort,
--        summary
-- FROM ai_evaluations
-- WHERE requires_attention = 1
-- ORDER BY evaluated_at DESC
-- LIMIT 50;

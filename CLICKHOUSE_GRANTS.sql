-- ClickHouse Permission Grants for AI Evaluator
-- Run these commands on the ClickHouse server to fix permission errors
--
-- Error being fixed:
-- Code: 497. DB::Exception: mnoc_prod_collector: Not enough privileges.
-- To execute this query, it's necessary to have the grant SELECT(...) 
-- ON mnoc_prod.ai_evaluations. (ACCESS_DENIED)

-- Grant INSERT and SELECT permissions on main table
GRANT INSERT, SELECT ON mnoc_prod.ai_evaluations TO mnoc_prod_collector;

-- Optional: Grant SELECT on materialized views for analytics queries
GRANT SELECT ON mnoc_prod.ai_evaluations_daily_mv TO mnoc_prod_collector;
GRANT SELECT ON mnoc_prod.ai_evaluations_project_summary_mv TO mnoc_prod_collector;

-- Verify grants
SHOW GRANTS FOR mnoc_prod_collector;

-- Test INSERT permission
-- Should return "Ok." if successful
SELECT 'Permission check passed' FROM system.one WHERE hasGrant('mnoc_prod_collector', 'INSERT', 'mnoc_prod', 'ai_evaluations', 0);

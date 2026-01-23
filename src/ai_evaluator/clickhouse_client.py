"""ClickHouse client for storing evaluation results."""

import logging
from typing import Optional, Dict, Any
from datetime import datetime
import httpx
from urllib.parse import urljoin

logger = logging.getLogger(__name__)


class ClickHouseClient:
    """Client for storing evaluation results in ClickHouse."""
    
    def __init__(
        self,
        url: str,
        user: str,
        password: str,
        database: str = "default"
    ):
        """
        Initialize ClickHouse client.
        
        Args:
            url: ClickHouse server URL (e.g., http://clickhouse:8123)
            user: Database user
            password: Database password
            database: Database name (default: default)
        """
        self.url = url.rstrip("/")
        self.user = user
        self.password = password
        self.database = database
        self.client = httpx.AsyncClient(timeout=30.0)
        
    async def execute(self, query: str, params: Optional[Dict] = None) -> Dict:
        """
        Execute a ClickHouse query.
        
        Args:
            query: SQL query to execute
            params: Query parameters (optional)
            
        Returns:
            Query result
        """
        try:
            response = await self.client.post(
                urljoin(self.url, "/"),
                params={
                    "user": self.user,
                    "password": self.password,
                    "database": self.database
                },
                data=query.encode("utf-8")
            )
            response.raise_for_status()
            return {"success": True, "data": response.text}
        except httpx.HTTPError as e:
            logger.error(f"ClickHouse query failed: {e}")
            return {"success": False, "error": str(e)}
    
    async def store_evaluation(self, evaluation: Dict[str, Any], issue_data: Dict[str, Any]) -> bool:
        """
        Store evaluation results in ClickHouse.
        
        Args:
            evaluation: Evaluation results from agent
            issue_data: Original issue data
            
        Returns:
            True if stored successfully
        """
        try:
            metrics = evaluation.get("metrics", {})
            analysis = evaluation.get("analysis", {})
            
            # Calculate overall score (average of all metrics)
            metric_values = [
                metrics.get("solution_quality", 0),
                metrics.get("adherence_to_solution", 0),
                metrics.get("operator_effort", 0),
                metrics.get("automation_potential", 0),
                metrics.get("resolution_efficiency", 0)
            ]
            overall_score = sum(metric_values) / len(metric_values) if metric_values else 0
            
            # Determine flags
            automation_candidate = 1 if metrics.get("automation_potential", 0) >= 7 else 0
            requires_attention = 1 if any(v < 5 for v in metric_values) else 0
            
            # Calculate resolution time
            resolution_time = 0
            if issue_data.get("created_on") and issue_data.get("updated_on"):
                try:
                    created = datetime.fromisoformat(issue_data["created_on"].replace("Z", "+00:00"))
                    closed = datetime.fromisoformat(issue_data["updated_on"].replace("Z", "+00:00"))
                    resolution_time = int((closed - created).total_seconds())
                except Exception as e:
                    logger.warning(f"Could not calculate resolution time: {e}")
            
            # Format timestamps for ClickHouse
            evaluated_at = evaluation.get("evaluated_at", datetime.utcnow().isoformat())
            if isinstance(evaluated_at, str):
                evaluated_at = datetime.fromisoformat(evaluated_at.replace("Z", "+00:00")).strftime("%Y-%m-%d %H:%M:%S")
            
            issue_created_at = issue_data.get("created_on", "")
            if issue_created_at:
                issue_created_at = datetime.fromisoformat(issue_created_at.replace("Z", "+00:00")).strftime("%Y-%m-%d %H:%M:%S")
            else:
                issue_created_at = "1970-01-01 00:00:00"
                
            issue_closed_at = issue_data.get("updated_on", "")
            if issue_closed_at:
                issue_closed_at = datetime.fromisoformat(issue_closed_at.replace("Z", "+00:00")).strftime("%Y-%m-%d %H:%M:%S")
            else:
                issue_closed_at = "1970-01-01 00:00:00"
            
            # Prepare INSERT query
            query = f"""
            INSERT INTO ai_evaluations (
                issue_id,
                project_id,
                project_identifier,
                evaluated_at,
                issue_created_at,
                issue_closed_at,
                resolution_time_seconds,
                subject,
                description,
                author,
                tracker,
                status,
                priority,
                issue_type,
                class_id,
                evaluation_model,
                solution_quality,
                adherence_to_solution,
                operator_effort,
                automation_potential,
                resolution_efficiency,
                overall_score,
                solution_quality_notes,
                adherence_notes,
                operator_effort_notes,
                automation_recommendations,
                efficiency_notes,
                summary,
                improvement_priority,
                automation_candidate,
                requires_attention,
                resolve_method,
                resolve_by,
                alarming_state,
                raw_response
            ) VALUES (
                {issue_data.get('issue_id', 0)},
                {issue_data.get('project_id', 0)},
                '{self._escape(issue_data.get('project_identifier', ''))}',
                '{evaluated_at}',
                '{issue_created_at}',
                '{issue_closed_at}',
                {resolution_time},
                '{self._escape(issue_data.get('subject', '')[:500])}',
                '{self._escape(issue_data.get('description', '')[:2000])}',
                '{self._escape(issue_data.get('author', ''))}',
                '{self._escape(issue_data.get('tracker', ''))}',
                '{self._escape(issue_data.get('status', ''))}',
                '{self._escape(issue_data.get('priority', ''))}',
                '{self._escape(issue_data.get('issue_type', ''))}',
                '{self._escape(issue_data.get('class_id', ''))}',
                '{self._escape(evaluation.get('model', ''))}',
                {metrics.get('solution_quality', 0)},
                {metrics.get('adherence_to_solution', 0)},
                {metrics.get('operator_effort', 0)},
                {metrics.get('automation_potential', 0)},
                {metrics.get('resolution_efficiency', 0)},
                {overall_score},
                '{self._escape(analysis.get('solution_quality_notes', '')[:1000])}',
                '{self._escape(analysis.get('adherence_notes', '')[:1000])}',
                '{self._escape(analysis.get('operator_effort_notes', '')[:1000])}',
                '{self._escape(analysis.get('automation_recommendations', '')[:2000])}',
                '{self._escape(analysis.get('efficiency_notes', '')[:1000])}',
                '{self._escape(evaluation.get('summary', '')[:2000])}',
                '{self._escape(evaluation.get('improvement_priority', 'medium'))}',
                {automation_candidate},
                {requires_attention},
                '{self._escape(issue_data.get('issue_resolve_method', ''))}',
                '{self._escape(issue_data.get('issue_resolve_by', ''))}',
                '{self._escape(str(issue_data.get('alarming_state', '')))}',
                '{self._escape(str(evaluation.get('raw_response', ''))[:5000])}'
            )
            """
            
            result = await self.execute(query)
            
            if result.get("success"):
                logger.info(f"Stored evaluation for issue #{issue_data.get('issue_id')} in ClickHouse")
                return True
            else:
                logger.error(f"Failed to store evaluation: {result.get('error')}")
                return False
                
        except Exception as e:
            logger.error(f"Error storing evaluation in ClickHouse: {e}")
            return False
    
    def _escape(self, value: str) -> str:
        """
        Escape string for ClickHouse query.
        
        Args:
            value: String to escape
            
        Returns:
            Escaped string
        """
        if not value:
            return ""
        # Escape single quotes and backslashes
        return str(value).replace("\\", "\\\\").replace("'", "\\'")
    
    async def get_automation_candidates(self, limit: int = 20) -> Dict:
        """
        Get top automation candidates.
        
        Args:
            limit: Maximum number of results
            
        Returns:
            Query results
        """
        query = f"""
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
        LIMIT {limit}
        FORMAT JSONCompact
        """
        return await self.execute(query)
    
    async def get_quality_trends(self, project: Optional[str] = None, days: int = 30) -> Dict:
        """
        Get quality trends over time.
        
        Args:
            project: Project identifier (optional)
            days: Number of days to analyze
            
        Returns:
            Query results
        """
        where_clause = f"AND project_identifier = '{self._escape(project)}'" if project else ""
        
        query = f"""
        SELECT 
            toStartOfWeek(evaluated_at) AS week,
            project_identifier,
            avg(solution_quality) AS avg_quality,
            avg(automation_potential) AS avg_automation,
            count() AS total_issues
        FROM ai_evaluations
        WHERE evaluated_at >= now() - INTERVAL {days} DAY
        {where_clause}
        GROUP BY week, project_identifier
        ORDER BY week DESC, project_identifier
        FORMAT JSONCompact
        """
        return await self.execute(query)
    
    async def close(self):
        """Close HTTP client."""
        await self.client.aclose()

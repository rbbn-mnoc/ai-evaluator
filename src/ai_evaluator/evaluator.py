"""Evaluation agent - performs post-resolution quality assessment."""

import json
import logging
from datetime import datetime
from typing import Optional
from anthropic import AsyncAnthropic

from .prompts import get_evaluation_prompt
from .context_builder import ContextBuilder

logger = logging.getLogger(__name__)


class EvaluationAgent:
    """
    Agent that evaluates resolution quality using a different AI model.
    
    Uses Claude Opus for unbiased evaluation of how issues were resolved,
    assessing both AI recommendation quality and operator performance.
    """
    
    def __init__(
        self,
        mcp_client,
        anthropic_api_key: str,
        model: str = "claude-opus-4",
        max_tokens: int = 4096
    ):
        """
        Initialize evaluation agent.
        
        Args:
            mcp_client: MCP client for fetching context
            anthropic_api_key: Anthropic API key
            model: Model to use for evaluation (default: claude-opus-4)
            max_tokens: Maximum tokens for response
        """
        self.mcp = mcp_client
        self.context_builder = ContextBuilder(mcp_client)
        self.anthropic = AsyncAnthropic(api_key=anthropic_api_key)
        self.model = model
        self.max_tokens = max_tokens
    
    async def evaluate_resolution(self, issue_data: dict) -> dict:
        """
        Evaluate a closed issue's resolution.
        
        Args:
            issue_data: Issue data from redmine-event-source
            
        Returns:
            Evaluation results with metrics and analysis
        """
        issue_id = issue_data["issue_id"]
        logger.info(f"Starting evaluation for issue #{issue_id}")
        
        try:
            # Build context using shared context builder
            context = await self.context_builder.build_issue_context(
                issue_data,
                include_knowledge=True,
                include_zabbix=True,
                correlation_minutes=60
            )
            
            # Get AI analysis and resolution notes
            ai_analysis = await self.context_builder.get_ai_analysis(issue_id)
            resolution_notes = await self.context_builder.get_resolution_notes(issue_id)
            
            # Generate evaluation prompt
            prompt = get_evaluation_prompt(
                issue_data=issue_data,
                ai_analysis=ai_analysis or "No AI analysis found",
                resolution_notes=resolution_notes,
                knowledge_data=context.get("knowledge", {}),
                zabbix_data=context.get("zabbix", {})
            )
            
            # Call Claude Opus for evaluation
            logger.info(f"Calling {self.model} for evaluation")
            response = await self.anthropic.messages.create(
                model=self.model,
                max_tokens=self.max_tokens,
                messages=[{
                    "role": "user",
                    "content": prompt
                }]
            )
            
            # Parse evaluation response
            evaluation = self._parse_evaluation(response.content[0].text)
            evaluation["issue_id"] = issue_id
            evaluation["evaluated_at"] = datetime.utcnow().isoformat()
            evaluation["model"] = self.model
            
            logger.info(
                f"Evaluation complete for issue #{issue_id}: "
                f"Quality={evaluation['metrics']['solution_quality']}, "
                f"Automation={evaluation['metrics']['automation_potential']}"
            )
            
            return evaluation
            
        except Exception as e:
            logger.error(f"Evaluation failed for issue #{issue_id}: {e}")
            return {
                "issue_id": issue_id,
                "error": str(e),
                "evaluated_at": datetime.utcnow().isoformat()
            }
    
    def _parse_evaluation(self, response_text: str) -> dict:
        """
        Parse evaluation response from AI.
        
        Attempts to extract JSON from response, falls back to text parsing.
        
        Args:
            response_text: Raw response from AI model
            
        Returns:
            Structured evaluation data
        """
        try:
            # Try to extract JSON from response
            json_start = response_text.find("{")
            json_end = response_text.rfind("}") + 1
            
            if json_start >= 0 and json_end > json_start:
                json_str = response_text[json_start:json_end]
                return json.loads(json_str)
            
            # Fallback: parse text manually
            logger.warning("Could not find JSON in response, using text parsing")
            return self._parse_text_response(response_text)
            
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON: {e}")
            return self._parse_text_response(response_text)
    
    def _parse_text_response(self, text: str) -> dict:
        """
        Fallback text parsing for evaluation response.
        
        Extracts scores and analysis from text format.
        
        Args:
            text: Response text
            
        Returns:
            Best-effort structured evaluation
        """
        evaluation = {
            "metrics": {
                "solution_quality": 5,
                "adherence_to_solution": 5,
                "operator_effort": 5,
                "automation_potential": 5,
                "resolution_efficiency": 5
            },
            "analysis": {
                "solution_quality_notes": "",
                "adherence_notes": "",
                "operator_effort_notes": "",
                "automation_recommendations": "",
                "efficiency_notes": ""
            },
            "summary": "",
            "improvement_priority": "medium",
            "raw_response": text
        }
        
        # Simple pattern matching for scores
        import re
        
        score_patterns = {
            "solution_quality": r"Solution Quality.*?Score.*?:.*?(\d+)",
            "adherence_to_solution": r"Adherence.*?Score.*?:.*?(\d+)",
            "operator_effort": r"Operator Effort.*?Score.*?:.*?(\d+)",
            "automation_potential": r"Automation Potential.*?Score.*?:.*?(\d+)",
            "resolution_efficiency": r"Resolution Efficiency.*?Score.*?:.*?(\d+)"
        }
        
        for metric, pattern in score_patterns.items():
            match = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
            if match:
                try:
                    score = int(match.group(1))
                    if 1 <= score <= 10:
                        evaluation["metrics"][metric] = score
                except ValueError:
                    pass
        
        return evaluation
    
    async def store_evaluation(self, evaluation: dict) -> bool:
        """
        Store evaluation results in Redmine.
        
        Saves evaluation metrics to custom fields and adds a note.
        
        Args:
            evaluation: Evaluation results
            
        Returns:
            True if stored successfully
        """
        issue_id = evaluation["issue_id"]
        
        try:
            # Format evaluation note
            metrics = evaluation.get("metrics", {})
            summary = evaluation.get("summary", "No summary available")
            
            note = f"""## AI Evaluation Results

**Model**: {evaluation.get('model', 'unknown')}
**Evaluated**: {evaluation.get('evaluated_at', 'unknown')}

### Metrics (1-10)
- Solution Quality: {metrics.get('solution_quality', 'N/A')}
- Adherence to Solution: {metrics.get('adherence_to_solution', 'N/A')}
- Operator Effort: {metrics.get('operator_effort', 'N/A')} (10 = minimal)
- Automation Potential: {metrics.get('automation_potential', 'N/A')}
- Resolution Efficiency: {metrics.get('resolution_efficiency', 'N/A')}

### Summary
{summary}

### Automation Recommendations
{evaluation.get('analysis', {}).get('automation_recommendations', 'None provided')}

---
*Priority: {evaluation.get('improvement_priority', 'medium').upper()}*
"""
            
            # Store in Redmine
            # Note: Adjust custom field IDs based on your Redmine configuration
            custom_fields = {
                "evaluation_quality": metrics.get("solution_quality"),
                "evaluation_adherence": metrics.get("adherence_to_solution"),
                "evaluation_effort": metrics.get("operator_effort"),
                "evaluation_automation": metrics.get("automation_potential"),
                "evaluation_efficiency": metrics.get("resolution_efficiency")
            }
            
            await self.mcp.update_redmine_issue(
                issue_id=issue_id,
                notes=note,
                custom_fields=custom_fields
            )
            
            logger.info(f"Stored evaluation for issue #{issue_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to store evaluation for issue #{issue_id}: {e}")
            return False

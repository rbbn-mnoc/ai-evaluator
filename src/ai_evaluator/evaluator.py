"""Evaluation agent - performs post-resolution quality assessment."""

import json
import logging
from datetime import datetime
from typing import Optional
import asyncio
import boto3
from strands.models import BedrockModel
from strands import Agent

from .prompts import get_evaluation_prompt

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
        bedrock_model_arn: str,
        aws_region: str = "us-west-2",
        max_tokens: int = 4096,
        mcp_tools: list = None
    ):
        """
        Initialize evaluation agent.
        
        Args:
            mcp_client: MCP client for fetching context (not used directly, tools have it)
            bedrock_model_arn: AWS Bedrock model ARN
            aws_region: AWS region for Bedrock
            max_tokens: Maximum tokens for response
            mcp_tools: List of MCP tools for the agent
        """
        self.mcp = mcp_client  # Keep reference but Agent tools will do the work
        
        # Initialize Bedrock model
        session = boto3.Session(region_name=aws_region)
        bedrock_model = BedrockModel(
            model_id=bedrock_model_arn,
            boto_session=session
        )
        
        # Create Strands Agent with MCP tools (like ai-agents does)
        self.agent = Agent(tools=mcp_tools or [], model=bedrock_model)
        self.model_arn = bedrock_model_arn
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
            # Build evaluation prompt - the Agent has MCP tools and will fetch context itself
            prompt = get_evaluation_prompt(
                issue_data=issue_data,
                ai_analysis="Use get_redmine_issue to fetch AI analysis from issue notes",
                resolution_notes="Use get_redmine_issue to fetch resolution notes from journals",
                knowledge_data="Use get_knowledge tool if class_id is available",
                zabbix_data="Use search_zabbix_alerts to fetch correlated alerts"
            )
            
            # Call Bedrock for evaluation using Strands Agent
            logger.info(f"Calling Bedrock model {self.model_arn} for evaluation")
            
            # Use Agent.invoke_async() like ai-agents does
            response = await asyncio.wait_for(
                self.agent.invoke_async(prompt),
                timeout=300  # 5 minute timeout for evaluation
            )
            
            # Parse evaluation response - response is an AgentResult object
            evaluation = self._parse_evaluation(response)
            evaluation["issue_id"] = issue_id
            evaluation["evaluated_at"] = datetime.utcnow().isoformat()
            evaluation["model"] = self.model_arn
            
            logger.info(
                f"Evaluation complete for issue #{issue_id}: "
                f"Quality={evaluation['metrics'].get('solution_quality', 0)}, "
                f"Automation={evaluation['metrics'].get('automation_potential', 0)}"
            )
            
            return evaluation
            
        except Exception as e:
            logger.error(f"Evaluation failed for issue #{issue_id}: {e}")
            return {
                "issue_id": issue_id,
                "error": str(e),
                "evaluated_at": datetime.utcnow().isoformat()
            }
    
    def _parse_evaluation(self, agent_result) -> dict:
        """
        Parse evaluation response from Agent.
        
        AgentResult object has a .response attribute with the text.
        Attempts to extract JSON from response, falls back to text parsing.
        
        Args:
            agent_result: AgentResult object from Agent.invoke_async()
            
        Returns:
            Structured evaluation data
        """
        try:
            # Extract text from AgentResult
            response_text = str(agent_result.response) if hasattr(agent_result, 'response') else str(agent_result)
            
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
            response_text = str(agent_result.response) if hasattr(agent_result, 'response') else str(agent_result)
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
        Store evaluation results (placeholder - actual storage in ClickHouse).
        
        Note: We don't store back to Redmine to avoid complexity.
        Evaluations are stored in ClickHouse for analytics.
        
        Args:
            evaluation: Evaluation results
            
        Returns:
            True always (ClickHouse storage handled in main.py)
        """
        logger.info(f"Stored evaluation for issue #{evaluation['issue_id']}")
        return True

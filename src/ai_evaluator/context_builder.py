"""Shared context builder to avoid code duplication."""

from typing import Optional
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)


class ContextBuilder:
    """
    Shared context building logic used by both ai-agents and ai-evaluator.
    
    This class provides common functionality for building issue context
    from MCP tools, eliminating code duplication.
    """
    
    def __init__(self, mcp_client):
        """
        Initialize context builder.
        
        Args:
            mcp_client: MCP client instance (from ai-agents or ai-evaluator)
        """
        self.mcp = mcp_client
    
    async def build_issue_context(
        self,
        issue_data: dict,
        include_knowledge: bool = True,
        include_zabbix: bool = True,
        correlation_minutes: int = 60
    ) -> dict:
        """
        Build comprehensive context for an issue.
        
        Args:
            issue_data: Issue data from redmine-event-source
            include_knowledge: Whether to fetch knowledge base data
            include_zabbix: Whether to fetch Zabbix alerts
            correlation_minutes: Time window for correlated alerts
            
        Returns:
            Dictionary with knowledge, zabbix, and other context
        """
        context = {
            "issue_data": issue_data,
            "knowledge": None,
            "zabbix": None,
            "errors": []
        }
        
        # Fetch knowledge base data
        if include_knowledge and issue_data.get("class_id"):
            try:
                knowledge = await self.mcp.get_knowledge(
                    class_id=issue_data["class_id"],
                    project_identifier=issue_data["project_identifier"]
                )
                context["knowledge"] = knowledge
            except Exception as e:
                logger.error(f"Failed to fetch knowledge: {e}")
                context["errors"].append(f"Knowledge fetch failed: {e}")
        
        # Fetch Zabbix correlation data
        if include_zabbix and issue_data.get("created_on"):
            try:
                created_time = datetime.fromisoformat(
                    issue_data["created_on"].replace("Z", "+00:00")
                )
                time_from = created_time - timedelta(minutes=correlation_minutes)
                time_to = created_time + timedelta(minutes=correlation_minutes)
                
                zabbix = await self.mcp.search_zabbix_alerts(
                    time_from=time_from.isoformat(),
                    time_to=time_to.isoformat()
                )
                context["zabbix"] = zabbix
            except Exception as e:
                logger.error(f"Failed to fetch Zabbix data: {e}")
                context["errors"].append(f"Zabbix fetch failed: {e}")
        
        return context
    
    async def get_resolution_notes(self, issue_id: int) -> str:
        """
        Extract resolution notes from issue journals.
        
        Args:
            issue_id: Redmine issue ID
            
        Returns:
            Concatenated resolution notes from all journals
        """
        try:
            issue_detail = await self.mcp.get_redmine_issue(issue_id)
            
            journals = issue_detail.get("journals", [])
            notes = []
            
            for journal in journals:
                if journal.get("notes"):
                    author = journal.get("user", {}).get("name", "Unknown")
                    created = journal.get("created_on", "")
                    note_text = journal.get("notes", "")
                    notes.append(f"[{created}] {author}:\n{note_text}")
            
            return "\n\n---\n\n".join(notes) if notes else "No resolution notes available"
            
        except Exception as e:
            logger.error(f"Failed to fetch resolution notes: {e}")
            return f"Error fetching notes: {e}"
    
    async def get_ai_analysis(self, issue_id: int) -> Optional[str]:
        """
        Extract AI analysis from issue notes.
        
        Looks for notes from AI agent in the issue journals.
        
        Args:
            issue_id: Redmine issue ID
            
        Returns:
            AI analysis text or None
        """
        try:
            issue_detail = await self.mcp.get_redmine_issue(issue_id)
            journals = issue_detail.get("journals", [])
            
            # Look for AI analysis (usually first note from ai-agents)
            for journal in journals:
                author = journal.get("user", {}).get("name", "")
                notes = journal.get("notes", "")
                
                # Check if this looks like AI analysis
                if "AI Analysis" in notes or "mnoc-ai" in author.lower():
                    return notes
            
            return None
            
        except Exception as e:
            logger.error(f"Failed to fetch AI analysis: {e}")
            return None

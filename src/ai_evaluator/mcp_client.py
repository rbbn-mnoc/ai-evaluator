"""MCP Client for AI Evaluator - reuses MCP server tools."""

import httpx
import logging
from typing import Any, Optional
from mcp.client.streamable_http import streamablehttp_client
from strands.tools.mcp.mcp_client import MCPClient as StrandsMCPClient

logger = logging.getLogger(__name__)


class MCPClient:
    """Client for communicating with Redmine MCP Server."""
    
    def __init__(self, base_url: str, api_key: str = ""):
        """
        Initialize MCP client.
        
        Args:
            base_url: MCP server base URL (e.g., http://172.31.33.44:8000/mcp/)
            api_key: API key for Bearer token authentication
        """
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        
        # Create transport factory function (like ai-agents does)
        def create_transport():
            if api_key:
                headers = {"Authorization": f"Bearer {api_key}"}
                logger.info("[mcp] MCP authentication enabled (using Authorization Bearer header)")
                return streamablehttp_client(base_url, headers=headers)
            else:
                logger.warning("[mcp] MCP authentication disabled - no API key provided")
                return streamablehttp_client(base_url)
        
        # Create Strands MCP client
        self._client = StrandsMCPClient(create_transport)
        
    def list_tools_sync(self) -> list:
        """List available MCP tools synchronously."""
        return self._client.list_tools_sync()
        
    async def call_tool(self, tool_name: str, arguments: dict) -> dict:
        """
        Call an MCP tool.
        
        Args:
            tool_name: Name of the tool to call
            arguments: Tool arguments
            
        Returns:
            Tool response data
        """
        try:
            response = await self.client.post(
                f"{self.base_url}/tools/{tool_name}",
                json={"arguments": arguments}
            )
            response.raise_for_status()
            return response.json()
        except httpx.HTTPError as e:
            logger.error(f"MCP tool call failed: {tool_name} - {e}")
            return {"error": str(e)}
    
    async def get_knowledge(self, class_id: str, project_identifier: str) -> dict:
        """Fetch knowledge base data for a class_id."""
        return await self.call_tool("get_knowledge", {
            "class_id": class_id,
            "project_identifier": project_identifier
        })
    
    async def search_zabbix_alerts(
        self,
        host: Optional[str] = None,
        time_from: Optional[str] = None,
        time_to: Optional[str] = None,
        severity: Optional[int] = None
    ) -> dict:
        """Search Zabbix alerts."""
        args = {}
        if host:
            args["host"] = host
        if time_from:
            args["time_from"] = time_from
        if time_to:
            args["time_to"] = time_to
        if severity is not None:
            args["severity"] = severity
            
        return await self.call_tool("search_zabbix_alerts", args)
    
    async def get_redmine_issue(self, issue_id: int) -> dict:
        """Get full Redmine issue details including notes."""
        return await self.call_tool("get_redmine_issue", {
            "issue_id": issue_id,
            "include_journals": True
        })
    
    async def update_redmine_issue(
        self,
        issue_id: int,
        custom_fields: Optional[dict] = None,
        notes: Optional[str] = None
    ) -> dict:
        """Update Redmine issue with evaluation results."""
        args = {"issue_id": issue_id}
        if custom_fields:
            args["custom_fields"] = custom_fields
        if notes:
            args["notes"] = notes
            
        return await self.call_tool("update_redmine_issue", args)
    
    async def close(self):
        """Close HTTP client."""
        await self.client.aclose()

"""AI Evaluator package."""

from .evaluator import EvaluationAgent
from .mcp_client import MCPClient
from .context_builder import ContextBuilder
from .clickhouse_client import ClickHouseClient

__version__ = "0.1.0"

__all__ = ["EvaluationAgent", "MCPClient", "ContextBuilder", "ClickHouseClient"]

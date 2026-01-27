"""AI Evaluator Service - Main entry point."""

import os
import asyncio
import logging
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Depends, status
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from pydantic import BaseModel
import secrets

from .evaluator import EvaluationAgent
from .mcp_client import MCPClient
from .clickhouse_client import ClickHouseClient

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="MNOC AI Evaluator",
    description="Post-resolution quality assessment service",
    version="0.1.0"
)

# Basic auth for API endpoints
security = HTTPBasic()

# Configuration
MCP_SERVER_URL = os.getenv("MCP_SERVER_URL", "http://redmine-mcp-server:8000")
MCP_USERNAME = os.getenv("MCP_USERNAME", "")
MCP_PASSWORD = os.getenv("MCP_PASSWORD", "")
BEDROCK_MODEL_ARN = os.getenv(
    "BEDROCK_MODEL_ARN",
    "us.amazon.nova-pro-v1:0"  # Amazon Nova Pro for unbiased evaluation
)
AWS_REGION = os.getenv("AWS_REGION", "us-west-2")
MAX_TOKENS = int(os.getenv("MAX_TOKENS", "4096"))

# ClickHouse configuration
CLICKHOUSE_URL = os.getenv("CLICKHOUSE_URL", "")
CLICKHOUSE_USER = os.getenv("CLICKHOUSE_USER", "")
CLICKHOUSE_PASSWORD = os.getenv("CLICKHOUSE_PASSWORD", "")
CLICKHOUSE_DATABASE = os.getenv("CLICKHOUSE_DATABASE", "mnoc_prod")
CLICKHOUSE_ENABLED = bool(CLICKHOUSE_URL and CLICKHOUSE_USER)

# Service credentials
SERVICE_USERNAME = os.getenv("SERVICE_USERNAME", "evaluator")
SERVICE_PASSWORD = os.getenv("SERVICE_PASSWORD", "changeme")

# Global instances
mcp_client: MCPClient = None
evaluation_agent: EvaluationAgent = None
clickhouse_client: ClickHouseClient = None


class EvaluationRequest(BaseModel):
    """Request to evaluate an issue."""
    model_config = {"extra": "ignore"}  # Ignore extra fields from redmine-event-source
    
    issue_id: int
    project_id: int
    project_identifier: str
    subject: str
    description: str
    author: str
    tracker: str
    status: str
    priority: str
    created_on: str
    updated_on: str
    issue_type: str
    alarming_state: bool | str
    class_id: str | None = None
    issue_resolve_method: str | None = None
    issue_resolve_in: str | None = None
    issue_resolve_by: str | None = None
    issue_resolve_at: str | None = None
    collector_name: str | None = None  # Added field
    trigger_name: str | None = None  # Added field
    known_error_id: str | None = None  # Added field
    zabbix_event_id: str | None = None  # Added field


class EvaluationResponse(BaseModel):
    """Response from evaluation."""
    success: bool
    issue_id: int
    message: str
    evaluation: dict | None = None


def verify_credentials(credentials: HTTPBasicCredentials = Depends(security)):
    """Verify HTTP basic auth credentials."""
    correct_username = secrets.compare_digest(credentials.username, SERVICE_USERNAME)
    correct_password = secrets.compare_digest(credentials.password, SERVICE_PASSWORD)
    
    if not (correct_username and correct_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
            headers={"WWW-Authenticate": "Basic"},
        )
    return credentials.username


@app.on_event("startup")
async def startup_event():
    """Initialize services on startup."""
    global mcp_client, evaluation_agent, clickhouse_client
    
    logger.info("Starting AI Evaluator service...")
    logger.info(f"Using Bedrock model: {BEDROCK_MODEL_ARN}")
    logger.info(f"AWS Region: {AWS_REGION}")
    
    # Initialize MCP client
    mcp_client = MCPClient(
        base_url=MCP_SERVER_URL,
        username=MCP_USERNAME,
        password=MCP_PASSWORD
    )
    
    # Initialize ClickHouse client if configured
    if CLICKHOUSE_ENABLED:
        logger.info("Initializing ClickHouse client...")
        clickhouse_client = ClickHouseClient(
            url=CLICKHOUSE_URL,
            user=CLICKHOUSE_USER,
            password=CLICKHOUSE_PASSWORD,
            database=CLICKHOUSE_DATABASE
        )
        logger.info("ClickHouse client initialized")
    else:
        logger.warning("ClickHouse not configured - evaluations will only be stored in Redmine")
    
    # Initialize evaluation agent
    evaluation_agent = EvaluationAgent(
        mcp_client=mcp_client,
        bedrock_model_arn=BEDROCK_MODEL_ARN,
        aws_region=AWS_REGION,
        max_tokens=MAX_TOKENS
    )
    
    logger.info(f"AI Evaluator initialized with model: {BEDROCK_MODEL_ARN}")
    if CLICKHOUSE_ENABLED:
        logger.info(f"ClickHouse storage: ENABLED ({CLICKHOUSE_URL})")
    else:
        logger.info("ClickHouse storage: DISABLED")


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown."""
    global mcp_client, clickhouse_client
    
    logger.info("Shutting down AI Evaluator service...")
    
    if mcp_client:
        await mcp_client.close()
    
    if clickhouse_client:
        await clickhouse_client.close()


@app.get("/health")
async def health_check():
    """Health check endpoint for container orchestration."""
    return {
        "status": "healthy",
        "service": "ai-evaluator",
        "model": BEDROCK_MODEL_ARN,
        "clickhouse_enabled": CLICKHOUSE_ENABLED
    }


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "service": "ai-evaluator",
        "model": EVALUATION_MODEL
    }


@app.post("/evaluate", response_model=EvaluationResponse)
async def evaluate_issue(
    request: EvaluationRequest,
    username: str = Depends(verify_credentials)
):
    """
    Evaluate a closed issue's resolution.
    
    This endpoint is called by redmine-event-source after an issue is closed.
    """
    logger.info(f"Received evaluation request for issue #{request.issue_id} from {username}")
    
    try:
        # Convert request to dict for evaluator
        issue_data = request.dict()
        
        # Perform evaluation
        evaluation = await evaluation_agent.evaluate_resolution(issue_data)
        
        # Store results in Redmine
        stored_redmine = await evaluation_agent.store_evaluation(evaluation)
        
        # Store results in ClickHouse if enabled
        stored_clickhouse = False
        if CLICKHOUSE_ENABLED and clickhouse_client and not evaluation.get("error"):
            stored_clickhouse = await clickhouse_client.store_evaluation(evaluation, issue_data)
        
        storage_status = []
        if stored_redmine:
            storage_status.append("Redmine")
        if stored_clickhouse:
            storage_status.append("ClickHouse")
        
        message = f"Evaluation completed"
        if storage_status:
            message += f" and stored in {', '.join(storage_status)}"
        else:
            message += " but storage failed"
        
        return EvaluationResponse(
            success=True,
            issue_id=request.issue_id,
            message=message,
            evaluation=evaluation
        )
        
    except Exception as e:
        logger.error(f"Evaluation failed for issue #{request.issue_id}: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Evaluation failed: {str(e)}"
        )


@app.get("/stats")
async def get_stats(username: str = Depends(verify_credentials)):
    """Get evaluation statistics."""
    if not CLICKHOUSE_ENABLED or not clickhouse_client:
        return {
            "message": "ClickHouse not configured - statistics unavailable",
            "clickhouse_enabled": False
        }
    
    try:
        # Get automation candidates
        automation_candidates = await clickhouse_client.get_automation_candidates(limit=10)
        
        # Get quality trends (last 30 days)
        quality_trends = await clickhouse_client.get_quality_trends(days=30)
        
        return {
            "clickhouse_enabled": True,
            "automation_candidates": automation_candidates.get("data"),
            "quality_trends": quality_trends.get("data"),
            "message": "Statistics retrieved successfully"
        }
    except Exception as e:
        logger.error(f"Failed to get statistics: {e}")
        return {
            "clickhouse_enabled": True,
            "error": str(e),
            "message": "Failed to retrieve statistics"
        }


if __name__ == "__main__":
    import uvicorn
    
    host = os.getenv("SERVER_HOST", "0.0.0.0")
    port = int(os.getenv("SERVER_PORT", "8001"))
    
    logger.info(f"Starting AI Evaluator on {host}:{port}")
    
    uvicorn.run(
        "ai_evaluator.main:app",
        host=host,
        port=port,
        reload=False
    )

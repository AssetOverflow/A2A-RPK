import os
import asyncio
import logging
from typing import Optional
from contextlib import asynccontextmanager
from fastapi import FastAPI
import uvicorn

from agent_base import AgentBase
from agent_requester import RequesterAgent
from agent_provider import ProviderAgent
from agent_executor import ExecutorAgent
import mcp_server

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Global agent instance
agent_instance: Optional[AgentBase] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for FastAPI app"""
    global agent_instance

    # Startup
    agent_type = os.getenv("AGENT_TYPE", "requester")
    agent_id = os.getenv("AGENT_ID", "default-agent")

    logger.info(f"Starting agent: {agent_type} with ID: {agent_id}")

    # Create agent instance based on type
    if agent_type == "requester":
        agent_instance = RequesterAgent(agent_id)
    elif agent_type == "provider":
        agent_instance = ProviderAgent(agent_id)
    elif agent_type == "executor":
        agent_instance = ExecutorAgent(agent_id)
    else:
        raise ValueError(f"Unknown agent type: {agent_type}")

    # Initialize the agent (pure Kafka communication)
    await agent_instance.initialize()

    # Set agent instance for MCP server
    mcp_server.set_agent_instance(agent_instance)

    logger.info(f"Agent {agent_id} initialized - communicating via Kafka topics only")

    yield

    # Shutdown
    if agent_instance:
        await agent_instance.shutdown()
        logger.info("Agent shutdown complete")


# Create FastAPI app for health/status monitoring only
app = FastAPI(
    title="A2A Agent Monitor",
    description="Health and status monitoring for A2A Kafka-based agent (NO REST messaging)",
    version="1.0.0",
    lifespan=lifespan,
)


# Health check endpoint (for Docker/k8s orchestration)
@app.get("/health")
async def health_check():
    """Health check endpoint for container orchestration"""
    if not agent_instance or not agent_instance.is_running:
        return {"status": "unhealthy", "reason": "Agent not running"}

    return {
        "status": "healthy",
        "agent_id": agent_instance.agent_id,
        "agent_type": os.getenv("AGENT_TYPE", "unknown"),
        "communication": "kafka-only",
    }


# Status endpoint (for monitoring and debugging)
@app.get("/status")
async def get_status():
    """Get detailed agent status - for monitoring, not messaging"""
    if not agent_instance:
        return {"error": "Agent not initialized"}

    status = await agent_instance.get_status()
    status["note"] = "This agent communicates ONLY via Kafka topics - no REST messaging"
    return status


# MCP information endpoint
@app.get("/mcp")
async def get_mcp_info():
    """Get MCP server information"""
    return {
        "mcp_enabled": True,
        "mcp_server_port": os.getenv("MCP_SERVER_PORT", "N/A"),
        "note": "Use MCP protocol for agent control - Kafka for all messaging",
    }


if __name__ == "__main__":
    port = int(os.getenv("MCP_SERVER_PORT", "8000"))

    # Run FastAPI app (for health/status monitoring only)
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=False, log_level="info")

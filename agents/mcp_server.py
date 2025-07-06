"""
MCP Server implementation for A2A agents
Provides Model Context Protocol endpoints for agent discovery and interaction
"""

import asyncio
import json
import os
from typing import Dict, Any, List
from mcp import types
from mcp.server import Server
from mcp.server.stdio import stdio_server

# Global agent instance (will be set by main.py)
agent_instance = None


def set_agent_instance(agent):
    """Set the agent instance for MCP server"""
    global agent_instance
    agent_instance = agent


# Create MCP server
app = Server("a2a-agent")


@app.list_tools()
async def list_tools() -> List[types.Tool]:
    """List available tools for this agent"""
    tools = [
        types.Tool(
            name="get_agent_status",
            description="Get the current status of this agent",
            inputSchema={
                "type": "object",
                "properties": {},
                "additionalProperties": False,
            },
        ),
        types.Tool(
            name="get_active_tasks",
            description="Get all active tasks for this agent",
            inputSchema={
                "type": "object",
                "properties": {},
                "additionalProperties": False,
            },
        ),
    ]

    # Add agent-specific tools
    agent_type = os.getenv("AGENT_TYPE", "unknown")

    if agent_type == "requester":
        tools.append(
            types.Tool(
                name="request_task",
                description="Request a new task from providers",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "description": {
                            "type": "string",
                            "description": "Description of the task to request",
                        },
                        "proposed_cost": {
                            "type": "number",
                            "description": "Proposed cost for the task",
                        },
                    },
                    "required": ["description"],
                    "additionalProperties": False,
                },
            )
        )

        tools.append(
            types.Tool(
                name="get_pending_requests",
                description="Get all pending task requests",
                inputSchema={
                    "type": "object",
                    "properties": {},
                    "additionalProperties": False,
                },
            )
        )

    elif agent_type == "executor":
        tools.append(
            types.Tool(
                name="get_execution_queue",
                description="Get the current execution queue",
                inputSchema={
                    "type": "object",
                    "properties": {},
                    "additionalProperties": False,
                },
            )
        )

        tools.append(
            types.Tool(
                name="get_completed_tasks",
                description="Get all completed tasks",
                inputSchema={
                    "type": "object",
                    "properties": {},
                    "additionalProperties": False,
                },
            )
        )

    return tools


@app.call_tool()
async def call_tool(name: str, arguments: Dict[str, Any]) -> List[types.TextContent]:
    """Handle tool calls"""
    if not agent_instance:
        return [
            types.TextContent(type="text", text="Error: Agent instance not available")
        ]

    try:
        if name == "get_agent_status":
            status = await agent_instance.get_status()
            return [types.TextContent(type="text", text=json.dumps(status, indent=2))]

        elif name == "get_active_tasks":
            tasks = agent_instance.tasks
            return [
                types.TextContent(
                    type="text", text=json.dumps(tasks, indent=2, default=str)
                )
            ]

        elif name == "request_task" and hasattr(agent_instance, "request_task"):
            task_id = await agent_instance.request_task(
                arguments["description"], arguments.get("proposed_cost")
            )
            return [
                types.TextContent(
                    type="text", text=f"Task requested with ID: {task_id}"
                )
            ]

        elif name == "get_pending_requests" and hasattr(
            agent_instance, "get_pending_requests"
        ):
            requests = await agent_instance.get_pending_requests()
            return [
                types.TextContent(
                    type="text", text=json.dumps(requests, indent=2, default=str)
                )
            ]

        elif name == "get_execution_queue" and hasattr(
            agent_instance, "get_execution_queue"
        ):
            queue = await agent_instance.get_execution_queue()
            return [
                types.TextContent(
                    type="text", text=json.dumps(queue, indent=2, default=str)
                )
            ]

        elif name == "get_completed_tasks" and hasattr(
            agent_instance, "get_completed_tasks"
        ):
            completed = await agent_instance.get_completed_tasks()
            return [
                types.TextContent(
                    type="text", text=json.dumps(completed, indent=2, default=str)
                )
            ]

        else:
            return [types.TextContent(type="text", text=f"Unknown tool: {name}")]

    except Exception as e:
        return [
            types.TextContent(
                type="text", text=f"Error executing tool {name}: {str(e)}"
            )
        ]


@app.list_resources()
async def list_resources() -> List[types.Resource]:
    """List available resources"""
    return [
        types.Resource(
            uri="agent://status",
            name="Agent Status",
            description="Current status of this agent",
            mimeType="application/json",
        ),
        types.Resource(
            uri="agent://tasks",
            name="Agent Tasks",
            description="Current tasks for this agent",
            mimeType="application/json",
        ),
    ]


@app.read_resource()
async def read_resource(uri: str) -> str:
    """Read a resource"""
    if not agent_instance:
        return json.dumps({"error": "Agent instance not available"})

    if uri == "agent://status":
        status = await agent_instance.get_status()
        return json.dumps(status, indent=2)

    elif uri == "agent://tasks":
        tasks = agent_instance.tasks
        return json.dumps(tasks, indent=2, default=str)

    else:
        return json.dumps({"error": f"Unknown resource: {uri}"})


async def main():
    """Run the MCP server"""
    async with stdio_server() as (read_stream, write_stream):
        await app.run(read_stream, write_stream, app.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(main())

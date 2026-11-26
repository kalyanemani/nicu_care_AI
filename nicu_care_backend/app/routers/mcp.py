"""
FastAPI Router for Model Context Protocol (MCP) Tools.
Exposes MCP tool discovery and execution endpoints.
"""
from typing import Dict, Any
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from ..mcp.mcp_server import mcp_server

router = APIRouter(prefix="/api/v1/mcp", tags=["Model Context Protocol (MCP)"])


class MCPCallRequest(BaseModel):
    name: str
    arguments: Dict[str, Any] = {}


@router.get("/tools")
def list_mcp_tools():
    """Lists all standardized MCP tools with their JSON input schemas."""
    return {"tools": mcp_server.list_tools()}


@router.post("/call")
def call_mcp_tool(req: MCPCallRequest):
    """Executes a specific MCP tool with arguments."""
    try:
        return mcp_server.call_tool(req.name, req.arguments)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"MCP Execution failed: {str(e)}")

"""
MCP Agent Tools - Bridge between MCP servers and AI agent frameworks

This package provides tools to easily expose MCP server capabilities to AI agents,
with built-in support for the SmolAgents framework.

Main components:
- MCPClient: Low-level client for connecting to MCP servers
- MCPToolService: Persistent service for managing MCP connections
- MCPTool: Class representing individual MCP tools
- SmolMCPToolFactory: Factory for converting MCP tools to SmolAgents tools
"""

__version__ = "0.1.0"

from .models import MCPTool
from .mcp_tool_service import MCPClient, MCPToolService
from .smol_mcp_tool_factory import SmolMCPToolFactory
from .exceptions import (
    MCPAgentToolsError,
    ConnectionError,
    ToolCallError,
    ToolNotFoundError,
    ConversionError,
    InvalidArgumentError,
    ServiceError,
    TimeoutError,
)

__all__ = [
    'MCPTool',
    'MCPClient',
    'MCPToolService',
    'SmolMCPToolFactory',
    'MCPAgentToolsError',
    'ConnectionError',
    'ToolCallError',
    'ToolNotFoundError',
    'ConversionError',
    'InvalidArgumentError',
    'ServiceError',
    'TimeoutError',
] 
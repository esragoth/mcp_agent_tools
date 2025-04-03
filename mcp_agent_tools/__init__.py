"""
MCP Tools Package - Provides integration with MCP servers for AI agents

This package provides classes for:
1. Connecting to MCP servers via stdio or SSE
2. Managing MCP tools
3. Converting MCP tools to SmolAgents tools
"""

from .models import MCPTool
from .mcp_tool_service import MCPClient, MCPToolService
from .smol_mcp_tool_factory import SmolMCPToolFactory
from .smol_tool_converter import MCPToSmolToolConverter, convert_mcp_to_smol
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
    'MCPToSmolToolConverter',
    'convert_mcp_to_smol',
    'MCPAgentToolsError',
    'ConnectionError',
    'ToolCallError',
    'ToolNotFoundError',
    'ConversionError',
    'InvalidArgumentError',
    'ServiceError',
    'TimeoutError',
] 
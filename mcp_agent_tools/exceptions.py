"""
Custom exceptions for the MCP Agent Tools package.

This module defines exceptions that can be raised by the package,
allowing for more specific error handling by users.
"""

class MCPAgentToolsError(Exception):
    """Base exception for all MCP Agent Tools errors."""
    pass

class ConnectionError(MCPAgentToolsError):
    """Raised when there's an error connecting to an MCP server."""
    pass

class ToolCallError(MCPAgentToolsError):
    """Raised when there's an error calling a tool."""
    pass

class ToolNotFoundError(MCPAgentToolsError):
    """Raised when a requested tool is not found."""
    pass

class ConversionError(MCPAgentToolsError):
    """Raised when there's an error converting between tool formats."""
    pass

class InvalidArgumentError(MCPAgentToolsError):
    """Raised when an invalid argument is provided to a method."""
    pass

class ServiceError(MCPAgentToolsError):
    """Raised when there's an error with the MCPToolService."""
    pass

class TimeoutError(MCPAgentToolsError):
    """Raised when an operation times out."""
    pass 
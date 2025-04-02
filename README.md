# MCP Agent Tools

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

MCP Agent Tools is a Python library that bridges Model Context Protocol (MCP) servers with various AI agent frameworks. It provides tools to easily expose MCP server capabilities to AI agents, with built-in support for the SmolAgents framework.

## What is MCP?

Model Context Protocol (MCP) is a standardized protocol for exposing tools and capabilities to AI models and agents. MCP servers provide a consistent interface for AI agents to access external tools and capabilities.

## Features

- Connect to MCP servers using stdio or Server-Sent Events (SSE)
- Convert MCP tools to SmolAgents-compatible tools
- Manage persistent connections to MCP servers
- Easily extend to support other agent frameworks

## Installation

```bash
pip install mcp-agent-tools
```

## Quick Start

```python
import asyncio
from mcp_agent_tools import MCPClient, SmolMCPToolFactory

# Connect to an MCP server
async def main():
    # Using SSE connection
    client = MCPClient.create_sse_client(server_url="http://localhost:8000/sse")
    
    async with client as mcp:
        # List available tools
        tools = await mcp.list_tools()
        print(f"Available tools: {tools}")
        
        # Call a tool
        result = await mcp.call_tool("echo", {"message": "Hello from MCP client!"})
        print(f"Tool result: {result}")

# Integration with SmolAgents
def use_with_smolagents():
    # Create factory and convert tools
    factory = SmolMCPToolFactory(server_url="http://localhost:8000/sse")
    
    # Get tools as SmolAgents tools
    tools = factory.get_smolagent_tools()
    
    # Use with SmolAgents
    from smolagents import CodeAgent, LiteLLMModel
    
    model = LiteLLMModel(model_id="openai/gpt-4o")
    agent = CodeAgent(tools=tools, model=model)
    
    # Run agent
    result = agent.run("List the allowed directories")
    print(result)

if __name__ == "__main__":
    asyncio.run(main())
```

## Documentation

### Main Components

- **MCPClient**: Low-level client for connecting to MCP servers
- **MCPToolService**: Persistent service for managing MCP connections
- **MCPTool**: Class representing individual MCP tools
- **SmolMCPToolFactory**: Factory for converting MCP tools to SmolAgents tools

### Connection Methods

MCP Agent Tools supports two connection methods:

1. **stdio**: Connect to an MCP server running as a child process
2. **SSE (Server-Sent Events)**: Connect to an MCP server over HTTP

### Usage Examples

See the `examples.py` file for comprehensive usage examples.

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

This project is licensed under the MIT License - see the LICENSE file for details.

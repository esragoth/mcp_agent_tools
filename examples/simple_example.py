#!/usr/bin/env python3
"""
Simple example of using MCP Agent Tools

This example demonstrates basic usage of MCPClient and SmolMCPToolFactory.
"""

import asyncio
import logging
from mcp_agent_tools import (
    MCPClient, 
    SmolMCPToolFactory,
    ConnectionError,
    ToolCallError,
    ToolNotFoundError,
    ConversionError,
    InvalidArgumentError,
    ServiceError,
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

async def simple_client_example():
    """Example of using MCPClient with SSE connection."""
    logger.info("=== Simple MCPClient Example ===")
    
    # Create the client using SSE - replace with your actual server URL
    client = MCPClient.create_sse_client(
        server_url="http://localhost:8000/sse",
    )
    
    # Use as an async context manager
    try:
        async with client as mcp:
            # Check connection
            if await mcp.verify_connection():
                logger.info("Successfully connected to MCP server")
                
                # List available tools
                try:
                    tools = await mcp.list_tools()
                    logger.info(f"Available tools: {tools}")
                except ServiceError as e:
                    logger.error(f"Service error when listing tools: {e}")
                
                # Call a tool (replace with a tool that exists in your server)
                try:
                    result = await mcp.call_tool("echo", {"message": "Hello from MCP Agent Tools!"})
                    logger.info(f"Tool result: {result}")
                except ToolCallError as e:
                    logger.error(f"Error calling tool: {e}")
                except ToolNotFoundError as e:
                    logger.error(f"Tool not found: {e}")
            else:
                logger.error("Failed to connect to MCP server")
    except ConnectionError as e:
        logger.error(f"Connection error: {e}")
    except ServiceError as e:
        logger.error(f"Service error: {e}")
    except Exception as e:
        logger.error(f"Unexpected error: {e}")

def simple_smolagents_example():
    """Example of using SmolMCPToolFactory with SmolAgents."""
    logger.info("=== Simple SmolMCPToolFactory Example ===")
    
    # Create the factory
    try:
        factory = SmolMCPToolFactory(
            server_url="http://localhost:8000/sse",
            logger=logger
        )
        
        try:
            # Get SmolAgents tools
            try:
                tools = factory.get_smolagent_tools()
                logger.info(f"Converted to {len(tools)} SmolAgents tools")
                
                # Print tool details
                for i, tool in enumerate(tools):
                    logger.info(f"Tool {i+1}: {tool.name}")
                    logger.info(f"  Description: {tool.description[:50]}...")
                    
                # Note: To use with SmolAgents, you would do:
                # from smolagents import CodeAgent, LiteLLMModel
                # model = LiteLLMModel(model_id="openai/gpt-4o")
                # agent = CodeAgent(tools=tools, model=model)
                # result = agent.run("Your query here")
            except ConversionError as e:
                logger.error(f"Error converting tools: {e}")
            except ServiceError as e:
                logger.error(f"Service error: {e}")
        finally:
            # Clean up
            factory.close()
    except Exception as e:
        logger.error(f"Error creating factory: {e}")

def error_handling_example():
    """Example demonstrating error handling with custom exceptions."""
    logger.info("=== Error Handling Example ===")
    
    # Example 1: Invalid connection type
    try:
        client = MCPClient.__new__(MCPClient)
        client.connection_type = "invalid"
        async def test_invalid_connection():
            async with client:
                pass
        asyncio.run(test_invalid_connection())
    except InvalidArgumentError as e:
        logger.info(f"✅ Successfully caught InvalidArgumentError: {e}")
    except Exception as e:
        logger.error(f"❌ Unexpected error type: {e}")
        
    # Example 2: Convert invalid tool
    try:
        factory = SmolMCPToolFactory(
            server_url="http://localhost:8000/sse",
            logger=logger
        )
        # Create a minimal MCPTool without required attributes
        class InvalidTool:
            pass
        
        invalid_tool = InvalidTool()
        factory.mcp_to_smolagent_tool(invalid_tool)
    except ConversionError as e:
        logger.info(f"✅ Successfully caught ConversionError: {e}")
    except Exception as e:
        logger.error(f"❌ Unexpected error type: {e}")

async def main():
    """Run the examples."""
    # Run the MCPClient example
    await simple_client_example()
    
    # Run the SmolAgents example
    simple_smolagents_example()
    
    # Run the error handling example
    error_handling_example()

if __name__ == "__main__":
    asyncio.run(main()) 
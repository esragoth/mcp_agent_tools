#!/usr/bin/env python3
"""
Examples of using the MCP Agent Tools package

This file contains examples of how to use:
- MCPClient for direct connections to MCP servers
- MCPToolService for persistent connections in background threads
- MCPTool for working with MCP tools directly
- SmolMCPToolFactory for converting MCP tools to SmolAgents tools
"""

import asyncio
import logging
import os
from typing import Dict, Any, List

# Import from the mcp_agent_tools package
from mcp_agent_tools import (
    MCPClient, 
    MCPToolService, 
    MCPTool,
    SmolMCPToolFactory, 
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


#########################
# MCPClient Examples
#########################

async def example_mcpclient_stdio():
    """Example of using MCPClient with stdio connection."""
    logger.info("=== Example: MCPClient with stdio connection ===")
    
    # Create the client using stdio - replace with your actual command
    client = MCPClient(
        command="python",
        args=["-m", "your_mcp_server_module"],
    )
    
    # Use as an async context manager
    try:
        async with client as mcp:
            # Check connection
            if await mcp.verify_connection():
                logger.info("Successfully connected to MCP server")
                
                # List available tools
                tools = await mcp.list_tools()
                logger.info(f"Available tools: {tools}")
                
                # Call a tool (replace with a tool that actually exists in your server)
                try:
                    result = await mcp.call_tool("echo", {"message": "Hello from MCP client!"})
                    logger.info(f"Tool result: {result}")
                except Exception as e:
                    logger.error(f"Error calling tool: {e}")
            else:
                logger.error("Failed to connect to MCP server")
    except Exception as e:
        logger.error(f"Error using MCPClient: {e}")


async def example_mcpclient_sse():
    """Example of using MCPClient with SSE connection."""
    logger.info("=== Example: MCPClient with SSE connection ===")
    
    # Create the client using SSE - replace with your actual server URL
    client = MCPClient.create_sse_client(
        server_url="http://localhost:8000/sse",
    )
    
    # Use as an async context manager
    try:
        async with client as mcp:
            # Check connection
            if await mcp.verify_connection():
                logger.info("Successfully connected to SSE server")
                
                # List available tools
                tools = await mcp.list_tools()
                logger.info(f"Available tools: {tools}")
                
                # Get tools list in a format that's easier to work with
                tool_list = await mcp.get_tools_list()
                tool_names = [t.name if hasattr(t, 'name') else str(t) for t in tool_list]
                logger.info(f"Tool names: {tool_names}")
                
                # Call a tool (replace with a tool that actually exists in your server)
                try:
                    result = await mcp.call_tool("list_allowed_directories", {})
                    logger.info(f"Tool result: {result}")
                except Exception as e:
                    logger.error(f"Error calling tool: {e}")
            else:
                logger.error("Failed to connect to SSE server")
    except ConnectionError as e:
        logger.error(f"Connection error: {e}")
    except Exception as e:
        logger.error(f"Error using MCPClient: {e}")


async def example_mcpclient_get_tools_as_functions():
    """Example of getting tools as callable functions from MCPClient."""
    logger.info("=== Example: Getting tools as functions ===")
    
    client = MCPClient.create_sse_client(
        server_url="http://localhost:8000/sse",
    )
    
    try:
        async with client as mcp:
            # Get tools as async functions
            tool_functions = await mcp.get_tools_as_functions()
            logger.info(f"Available tool functions: {list(tool_functions.keys())}")
            
            # Call a tool function directly
            if "list_allowed_directories" in tool_functions:
                result = await tool_functions["list_allowed_directories"]()
                logger.info(f"Function result: {result}")
                
            # Get synchronous versions for non-async code
            sync_tools = await mcp.get_sync_tool_functions()
            logger.info(f"Sync tool functions: {list(sync_tools.keys())}")
            
            # Call a sync tool function
            if "echo" in sync_tools:
                result = sync_tools["echo"](message="Hello from sync function!")
                logger.info(f"Sync function result: {result}")
    except Exception as e:
        logger.error(f"Error: {e}")


#########################
# MCPToolService Examples
#########################

def example_mcptoolservice():
    """Example of using MCPToolService for persistent connections."""
    logger.info("=== Example: MCPToolService ===")
    
    # Create the service
    service = MCPToolService(
        server_url="http://localhost:8000/sse",
        reconnect_delay=3.0,
        max_reconnect_attempts=3,
        logger=logger
    )
    
    try:
        # Start the service
        if service.start():
            logger.info("Successfully started MCPToolService")
            
            # Get the available tools
            tools = service.get_tools()
            logger.info(f"Available tools: {[t.name for t in tools]}")
            
            # Call a tool
            if tools:
                # Display tool details
                tool = tools[0]
                logger.info(f"Using tool: {tool.name}")
                logger.info(f"Description: {tool.description}")
                logger.info(f"Inputs: {list(tool.inputs.keys())}")
                
                # Prepare arguments based on the tool's expected inputs
                args = {}
                if "message" in tool.inputs:
                    args["message"] = "Hello from MCPToolService!"
                elif "path" in tool.inputs:
                    args["path"] = "."
                
                # Call the tool
                try:
                    result = service._call_tool(tool.name, args)
                    logger.info(f"Tool result: {result}")
                except Exception as e:
                    logger.error(f"Error calling tool: {e}")
        else:
            logger.error("Failed to start MCPToolService")
    except Exception as e:
        logger.error(f"Error: {e}")
    finally:
        # Stop the service
        service.stop()
        logger.info("MCPToolService stopped")


#########################
# SmolMCPToolFactory Examples
#########################

def example_smolagents_integration():
    """Example of using SmolMCPToolFactory to integrate with SmolAgents."""
    logger.info("=== Example: SmolMCPToolFactory ===")
    try:
        # Create the factory
        factory = SmolMCPToolFactory(
            server_url="http://localhost:8000/sse",
            logger=logger
        )
        
        try:
            # Get MCP tools
            mcp_tools = factory.get_tools()
            if not mcp_tools:
                logger.warning("No MCP tools found")
                return
                
            logger.info(f"Retrieved {len(mcp_tools)} MCP tools")
            
            # Convert to SmolAgents tools
            smolagent_tools = factory.get_smolagent_tools()
            logger.info(f"Converted to {len(smolagent_tools)} SmolAgents tools")
            
            # Show tool details
            for i, tool in enumerate(smolagent_tools):
                logger.info(f"Tool {i+1}: {tool.name}")
                logger.info(f"  Description: {tool.description[:50]}...")
                logger.info(f"  Inputs: {tool.inputs}")
                
            # Use tools with SmolAgents
            try:
                # This section requires SmolAgents to be installed
                from smolagents import CodeAgent, LiteLLMModel
                
                # Check for OpenAI API key
                if not os.environ.get("OPENAI_API_KEY"):
                    logger.warning("OPENAI_API_KEY not set - using dummy model")
                    
                # Create a model (will use LiteLLM)
                model = LiteLLMModel(model_id="openai/gpt-4o")
                
                # Create an agent with the tools
                agent = CodeAgent(
                    tools=smolagent_tools,
                    model=model,
                    max_steps=5
                )
                
                # Run the agent with a query
                query = "List the allowed directories, then help me understand what they are."
                logger.info(f"Running agent with query: '{query}'")
                
                result = agent.run(query)
                logger.info(f"Agent result: {result}")
                
          
            except Exception as e:
                logger.error(f"Error running SmolAgents agent: {e}")
        finally:
            factory.close()
            logger.info("Factory closed")
    except Exception as e:
        logger.error(f"Error: {e}")


#########################
# Custom MCPTool Example
#########################

def example_custom_mcptool():
    """Example of creating and using a custom MCPTool."""
    logger.info("=== Example: Custom MCPTool ===")
    
    # Define a function that will be wrapped as an MCPTool
    def calculator(operation: str, a: float, b: float) -> float:
        """
        Perform a mathematical operation on two numbers.
        
        Args:
            operation: The operation to perform (add, subtract, multiply, divide)
            a: First number
            b: Second number
            
        Returns:
            The result of the operation
        """
        operation = operation.lower()
        if operation == "add":
            return a + b
        elif operation == "subtract":
            return a - b
        elif operation == "multiply":
            return a * b
        elif operation == "divide":
            if b == 0:
                raise ValueError("Cannot divide by zero")
            return a / b
        else:
            raise ValueError(f"Unknown operation: {operation}")
    
    # Create an MCPTool from the function
    tool = MCPTool(
        name="calculator",
        description="Perform mathematical operations on two numbers",
        function=calculator,
        input_descriptions={
            "operation": "The operation to perform (add, subtract, multiply, divide)",
            "a": "First number",
            "b": "Second number"
        },
        output_description="The result of the calculation"
    )
    
    # Use the tool
    logger.info(f"Created tool: {tool.name}")
    logger.info(f"Description: {tool.description}")
    logger.info(f"Inputs: {list(tool.inputs.keys())}")
    
    try:
        result = tool(operation="add", a=10, b=5)
        logger.info(f"10 + 5 = {result}")
        
        result = tool(operation="multiply", a=10, b=5)
        logger.info(f"10 * 5 = {result}")
    except Exception as e:
        logger.error(f"Error using tool: {e}")
    
        # If SmolAgents is available, also convert to a SmolAgents tool
        try:
            # Create a minimal factory just for conversion
            factory = SmolMCPToolFactory(logger=logger)
            
            # Convert to SmolAgents tool
            smolagent_tool = factory.mcp_to_smolagent_tool(tool)
            logger.info(f"Converted to SmolAgents tool: {smolagent_tool.name}")
            logger.info(f"Inputs: {smolagent_tool.inputs}")
            
            # Use the converted tool
            result = smolagent_tool(operation="divide", a=10, b=2)
            logger.info(f"10 / 2 = {result}")
        except Exception as e:
            logger.error(f"Error with SmolAgents tool: {e}")


#########################
# Main function to run all examples
#########################

async def main():
    """Run all the examples."""
    try:
        # # MCPClient examples
        # await example_mcpclient_sse()
        # # await example_mcpclient_stdio()  # Uncomment if you have a stdio server
        # await example_mcpclient_get_tools_as_functions()
        
        # # MCPToolService example
        # example_mcptoolservice()
        
        # # Custom MCPTool example
        # example_custom_mcptool()
        
        # SmolAgents integration example
        example_smolagents_integration()
        
    except Exception as e:
        logger.error(f"Error in examples: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    # Run the async examples
    asyncio.run(main()) 
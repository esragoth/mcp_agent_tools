import asyncio
import inspect
import functools
import threading
import queue
import time
import logging
import textwrap
from concurrent.futures import ThreadPoolExecutor
from typing import Dict, Any, Tuple, Optional, Callable, List, Union, Set, TypeVar, Type

from mcp import ClientSession, StdioServerParameters, types
from mcp.client.stdio import stdio_client
from mcp.client.sse import sse_client

from .models import MCPTool

class MCPClient:
    """
    A simple wrapper around the MCP Python SDK for connecting to MCP servers.
    
    This client handles common MCP operations including:
    - Initializing connections
    - Listing prompts, resources, and tools
    - Getting prompts with arguments
    - Reading resources
    - Calling tools
    
    Supports both stdio and SSE (Server-Sent Events) communication.
    """
    
    def __init__(
        self, 
        command: str, 
        args: Optional[List[str]] = None, 
        env: Optional[Dict[str, str]] = None,
        sampling_callback: Optional[Callable] = None
    ):
        """
        Initialize the MCP client using stdio communication.
        
        Args:
            command: The command to run the server
            args: Optional list of arguments for the server command
            env: Optional environment variables for the server
            sampling_callback: Optional callback function for handling sampling messages
        """
        self.server_params = StdioServerParameters(
            command=command,
            args=args or [],
            env=env
        )
        self.sampling_callback = sampling_callback
        self.session = None
        self.connection_type = "stdio"
        self.server_url = None
        self._context_managers = []

    @classmethod
    def create_sse_client(
        cls, 
        server_url: str,
        sampling_callback: Optional[Callable] = None
    ) -> 'MCPClient':
        """
        Create an MCPClient using SSE communication.
        
        Args:
            server_url: The URL of the SSE server to connect to
            sampling_callback: Optional callback function for handling sampling messages
            
        Returns:
            An MCPClient instance configured for SSE
        """
        client = cls.__new__(cls)
        client.server_url = server_url
        client.sampling_callback = sampling_callback
        client.session = None
        client.connection_type = "sse"
        client._context_managers = []
        return client

    async def __aenter__(self):
        """Enter async context manager."""
        if self.connection_type == "stdio":
            await self._setup_stdio_connection()
        elif self.connection_type == "sse":
            await self._setup_sse_connection()
        else:
            raise ValueError(f"Unsupported connection type: {self.connection_type}")
            
        await self.initialize()
        return self

    async def _setup_stdio_connection(self):
        """Set up stdio connection to MCP server."""
        # Create context manager for stdio client
        cm = stdio_client(self.server_params)
        self._context_managers.append(cm)
        
        # Enter the context manager
        self._read_write = await cm.__aenter__()
        
        # Create and enter the ClientSession context
        session_cm = ClientSession(
            self._read_write[0], 
            self._read_write[1],
            sampling_callback=self.sampling_callback
        )
        self._context_managers.append(session_cm)
        self.session = await session_cm.__aenter__()

    async def _setup_sse_connection(self):
        """Set up SSE connection to MCP server."""
        if not self.server_url:
            raise ValueError("Server URL is required for SSE connection")
            
        try:
            # Create and enter the sse_client context manager
            cm = sse_client(self.server_url)
            self._context_managers.append(cm)
            
            # Enter the context manager to get read/write streams
            self._read_write = await cm.__aenter__()
            
            # Create and enter ClientSession context
            session_cm = ClientSession(
                self._read_write[0], 
                self._read_write[1],
                sampling_callback=self.sampling_callback
            )
            self._context_managers.append(session_cm)
            self.session = await session_cm.__aenter__()
        except asyncio.CancelledError as e:
            # Handle cancellation errors from httpx/httpcore specifically
            for ctx in reversed(self._context_managers):
                try:
                    await ctx.__aexit__(type(e), e, e.__traceback__)
                except Exception:
                    pass
            self._context_managers = []
            raise ConnectionError(f"Connection to SSE server was cancelled - is the server running at {self.server_url}?") from e
        except Exception as e:
            # Clean up any context managers we've entered
            for ctx in reversed(self._context_managers):
                try:
                    await ctx.__aexit__(type(e), e, e.__traceback__)
                except Exception:
                    pass
            self._context_managers = []
            raise ConnectionError(f"Failed to connect to SSE server: {e}") from e

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Exit async context manager."""
        # Exit all context managers in reverse order
        for ctx in reversed(self._context_managers):
            try:
                await ctx.__aexit__(exc_type, exc_val, exc_tb)
            except Exception as e:
                print(f"Error while exiting context manager: {e}")
        
        self._context_managers = []
        self.session = None

    async def initialize(self) -> None:
        """Initialize the connection with the MCP server."""
        if not self.session:
            raise RuntimeError("Session not initialized. Use as async context manager.")
        await self.session.initialize()

    async def list_prompts(self) -> List[Dict[str, Any]]:
        """List all available prompts from the server."""
        if not self.session:
            raise RuntimeError("Session not initialized. Use as async context manager.")
        return await self.session.list_prompts()

    async def get_prompt(self, prompt_id: str, arguments: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Get a specific prompt with arguments.
        
        Args:
            prompt_id: The ID of the prompt to retrieve
            arguments: Optional arguments for the prompt
            
        Returns:
            The prompt with applied arguments
        """
        if not self.session:
            raise RuntimeError("Session not initialized. Use as async context manager.")
        return await self.session.get_prompt(prompt_id, arguments=arguments or {})

    async def list_resources(self) -> List[Dict[str, Any]]:
        """List all available resources from the server."""
        if not self.session:
            raise RuntimeError("Session not initialized. Use as async context manager.")
        return await self.session.list_resources()

    async def list_tools(self) -> List[Dict[str, Any]]:
        """List all available tools from the server."""
        if not self.session:
            raise RuntimeError("Session not initialized. Use as async context manager.")
        return await self.session.list_tools()

    async def get_tools_list(self) -> List:
        """
        Get the actual list of tools from the server.
        
        This method handles extracting the tool list from ListToolsResult objects
        that may be returned by the list_tools method.
        
        Returns:
            A list of tool objects
        """
        if not self.session:
            raise RuntimeError("Session not initialized. Use as async context manager.")
            
        # Get raw result from list_tools
        raw_result = await self.list_tools()
        
        # Handle different result formats
        if raw_result is None:
            return []
            
        # Case 1: It's already a list
        if isinstance(raw_result, list):
            return raw_result
            
        # Case 2: It has a 'tools' attribute (common for ListToolsResult)
        if hasattr(raw_result, 'tools'):
            return raw_result.tools
            
        # Case 3: It's iterable
        if hasattr(raw_result, '__iter__') and not isinstance(raw_result, (str, bytes, dict)):
            try:
                return list(raw_result)
            except Exception:
                pass
                
        # Case 4: It has dict-like access
        if hasattr(raw_result, 'get') or hasattr(raw_result, '__getitem__'):
            try:
                if hasattr(raw_result, 'get'):
                    tools = raw_result.get('tools')
                    if tools is not None:
                        return tools
                        
                if hasattr(raw_result, '__getitem__'):
                    try:
                        return raw_result['tools']
                    except (KeyError, TypeError):
                        pass
            except Exception:
                pass
                
        # If we can't determine the format, return empty list
        return []

    async def read_resource(self, resource_path: str) -> Tuple[bytes, str]:
        """
        Read a resource from the specified path.
        
        Args:
            resource_path: The path to the resource
            
        Returns:
            A tuple of (content, mime_type)
        """
        if not self.session:
            raise RuntimeError("Session not initialized. Use as async context manager.")
        return await self.session.read_resource(resource_path)

    async def call_tool(self, tool_name: str, arguments: Optional[Dict[str, Any]] = None) -> Any:
        """
        Call a tool with arguments.
        
        Args:
            tool_name: The name of the tool to call
            arguments: Optional arguments for the tool
            
        Returns:
            The result of the tool call
        """
        if not self.session:
            raise RuntimeError("Session not initialized. Use as async context manager.")
        return await self.session.call_tool(tool_name, arguments=arguments or {})

    async def verify_connection(self) -> bool:
        """
        Verify that the MCP connection is working correctly.
        
        Returns:
            True if connection is verified, False otherwise
        """
        if not self.session:
            return False
        
        try:
            # Try to list tools as a basic test
            tools = await self.list_tools()
            return True
        except Exception:
            return False

    async def get_tools_as_functions(self) -> Dict[str, Callable]:
        """
        Get all available tools from the server as callable functions.
        
        Returns:
            A dictionary of tool name to callable function that can be passed to an agent.
            Each function has the same signature as the corresponding tool.
        """
        if not self.session:
            raise RuntimeError("Session not initialized. Use as async context manager.")
            
        # Get the tools from the server using our helper method
        tool_list = await self.get_tools_list()
        
        # Debug the tools structure
        print(f"Retrieved tool list with {len(tool_list) if tool_list else 0} tools")
        
        tool_functions = {}
        
        # Process the tool list
        if tool_list:
            for tool in tool_list:
                # Handle different tool formats
                tool_name = None
                tool_description = None
                
                # Extract tool name
                if hasattr(tool, 'name'):
                    tool_name = tool.name
                elif isinstance(tool, dict) and 'name' in tool:
                    tool_name = tool['name']
                elif isinstance(tool, tuple) and len(tool) > 0:
                    # Common format: (name, description, parameters)
                    tool_name = tool[0] if isinstance(tool[0], str) else None
                    if len(tool) > 1:
                        tool_description = tool[1] if isinstance(tool[1], str) else None
                
                if not tool_name:
                    print(f"Skipping tool with unknown format: {tool}")
                    continue
                
                # Create the tool function
                async def tool_function(*args, _tool_name=tool_name, **kwargs):
                    # Convert positional args to kwargs if needed
                    if args:
                        # We don't have parameter names here, so just use generic names
                        for i, arg in enumerate(args):
                            kwargs[f"arg{i}"] = arg
                    
                    return await self.call_tool(_tool_name, kwargs)
                
                # Set function metadata
                tool_function.__name__ = tool_name
                tool_function.__doc__ = tool_description or f"Call the {tool_name} tool"
                
                # Add to dictionary
                tool_functions[tool_name] = tool_function
        
        return tool_functions

    async def get_sync_tool_functions(self) -> Dict[str, Callable]:
        """
        Get all available tools from the server as synchronous callable functions.
        
        This is useful for integrating with agents that don't support async functions.
        
        Returns:
            A dictionary of tool name to synchronous callable function.
        """
        if not self.session:
            raise RuntimeError("Session not initialized. Use as async context manager.")
            
        # Get the async tool functions
        async_tools = await self.get_tools_as_functions()
        sync_tools = {}
        
        # Create event loop for executing async functions
        loop = asyncio.get_event_loop()
        
        # Convert each async function to a sync function
        for name, async_func in async_tools.items():
            def sync_tool_function(*args, _async_func=async_func, **kwargs):
                # Run the async function in the event loop
                return loop.run_until_complete(_async_func(*args, **kwargs))
            
            # Copy metadata
            sync_tool_function.__name__ = async_func.__name__
            sync_tool_function.__doc__ = async_func.__doc__
            
            # Add to the dictionary
            sync_tools[name] = sync_tool_function
            
        return sync_tools


class MCPToolService:
    """
    A service that maintains a persistent connection to an MCP server and
    provides tools that can be used outside of an async context manager.
    
    This service runs in a background thread and automatically handles 
    reconnection if the connection is lost.
    """
    
    def __init__(
        self,
        server_url: str = None,
        command: str = None,
        args: Optional[List[str]] = None,
        env: Optional[Dict[str, str]] = None,
        sampling_callback: Optional[Callable] = None,
        reconnect_delay: float = 5.0,
        max_reconnect_attempts: int = 5,
        logger: Optional[logging.Logger] = None
    ):
        """
        Initialize the MCP Tool Service.
        
        Args:
            server_url: URL for SSE connection (if using SSE)
            command: Command for stdio connection (if using stdio)
            args: Arguments for stdio connection
            env: Environment variables for stdio connection
            sampling_callback: Callback for handling sampling messages
            reconnect_delay: Seconds to wait between reconnection attempts
            max_reconnect_attempts: Maximum number of reconnection attempts
            logger: Logger instance to use
        """
        # Connection parameters
        self.server_url = server_url
        self.command = command
        self.args = args or []
        self.env = env
        self.sampling_callback = sampling_callback
        self.reconnect_delay = reconnect_delay
        self.max_reconnect_attempts = max_reconnect_attempts
        
        # Connection mode
        if server_url:
            self.connection_type = "sse"
        elif command:
            self.connection_type = "stdio"
        else:
            raise ValueError("Either server_url or command must be provided")
        
        # Service state
        self.running = False
        self.connected = False
        self._tool_cache = {}
        self._loop = None
        self._thread = None
        self._client = None
        self._command_queue = queue.Queue()
        self._result_queues = {}
        self._next_request_id = 0
        self._lock = threading.RLock()
        
        # Logging
        self.logger = logger or logging.getLogger(__name__)
        
    def start(self):
        """Start the MCP Tool Service in a background thread."""
        if self.running:
            self.logger.warning("MCP Tool Service is already running")
            return
            
        self.running = True
        self._thread = threading.Thread(target=self._run_service, daemon=True)
        self._thread.start()
        
        # Wait for service to initialize
        timeout = 10.0
        start_time = time.time()
        while not self.connected and time.time() - start_time < timeout:
            time.sleep(0.1)
            
        if not self.connected:
            self.logger.warning("MCP Tool Service failed to connect within timeout")
        else:
            self.logger.info("MCP Tool Service started and connected")
            
        return self.connected
        
    def stop(self):
        """Stop the MCP Tool Service."""
        if not self.running:
            return
            
        self.running = False
        
        # Submit a stop command
        self._submit_command({"action": "stop"})
        
        # Wait for the thread to complete
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=5.0)
            
        self.logger.info("MCP Tool Service stopped")
        
    def _run_service(self):
        """Run the service in a background thread."""
        # Create a new event loop for this thread
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        
        try:
            # Run the main service coroutine
            self._loop.run_until_complete(self._service_main())
        except Exception as e:
            self.logger.error(f"Error in MCP Tool Service: {e}")
        finally:
            # Clean up
            self._loop.close()
            self._loop = None
            self.connected = False
            
    async def _service_main(self):
        """Main service coroutine that handles the connection and processes commands."""
        reconnect_attempts = 0
        
        while self.running:
            try:
                # Create and connect the client
                self._client = self._create_client()
                async with self._client as client:
                    # Mark as connected
                    self.connected = True
                    reconnect_attempts = 0
                    
                    try:
                        # Fetch available tools using the helper method
                        tool_list = await client.get_tools_list()
                        self.logger.info(f"Retrieved tool list with {len(tool_list) if tool_list else 0} tools")
                        
                        # Debug the tools structure
                        if tool_list and len(tool_list) > 0:
                            self.logger.info(f"First tool type: {type(tool_list[0])}")
                            
                            # Log more detailed information about the first tool
                            first_tool = tool_list[0]
                            self.logger.info(f"First tool structure: {first_tool}")
                            
                            # Log the tool attributes
                            if hasattr(first_tool, '__dict__'):
                                self.logger.info(f"First tool attributes: {first_tool.__dict__}")
                            
                            # Log directory structure
                            try:
                                self.logger.info(f"First tool dir: {dir(first_tool)}")
                            except Exception:
                                pass
                        else:
                            self.logger.warning("No tools found or empty tool list")
                        
                        # Extract tool names safely
                        tool_names = self._extract_tool_names(tool_list)
                        
                        # Log tools in a pretty format
                        self._log_tools_pretty(tool_list)
                        
                        self.logger.info(f"Connected to MCP server with {len(tool_list) if tool_list else 0} tools: {tool_names}")
                        
                        # Cache the tools in a usable format
                        if not tool_names:
                            self.logger.warning("No tools found in the server response")
                            
                        # Get synchronous tool functions for our service
                        self._tool_cache = self._create_tool_functions(client, tool_list, tool_names)
                        
                        # Log the generated tool cache
                        for name, tool in self._tool_cache.items():
                            # Handle both dictionary and MCPTool formats
                            if isinstance(tool, dict):
                                self.logger.info(f"Cached tool '{name}' with description: {tool.get('description', 'No description')}")
                            elif hasattr(tool, 'description'):
                                self.logger.info(f"Cached tool '{name}' with description: {tool.description}")
                            else:
                                self.logger.info(f"Cached tool '{name}'")
                            
                    except Exception as e:
                        self.logger.error(f"Error setting up tools: {e}")
                        import traceback
                        self.logger.error(f"Traceback: {traceback.format_exc()}")
                        # Continue with empty tool cache
                        self._tool_cache = {}
                        
                    # Process commands until stopped
                    await self._process_commands(client)
                    
            except Exception as e:
                self.connected = False
                reconnect_attempts += 1
                self.logger.error(f"MCP connection error: {e}")
                import traceback
                self.logger.error(f"Traceback: {traceback.format_exc()}")
                
                if not self.running:
                    break
                    
                if reconnect_attempts > self.max_reconnect_attempts:
                    self.logger.error(f"Maximum reconnection attempts ({self.max_reconnect_attempts}) reached. Stopping service.")
                    self.running = False
                    break
                    
                # Wait before reconnecting
                self.logger.info(f"Reconnecting in {self.reconnect_delay} seconds (attempt {reconnect_attempts}/{self.max_reconnect_attempts})...")
                await asyncio.sleep(self.reconnect_delay)
    
    def _log_tools_pretty(self, tools):
        """Log tool names and descriptions in a pretty, readable format."""
        if not tools:
            self.logger.info("No tools available")
            return
            
        # Calculate the maximum name length for alignment
        max_name_length = 0
        for tool in tools:
            name = self._extract_tool_name(tool)
            if name and len(name) > max_name_length:
                max_name_length = len(name)
                
        # Format the header
        separator = "=" * (max_name_length + 50)
        self.logger.info("\nAvailable MCP Tools:")
        self.logger.info(separator)
        
        # Format and log each tool
        for i, tool in enumerate(tools):
            name = self._extract_tool_name(tool)
            desc = self._extract_tool_description(tool)
            
            if name:
                # Format the tool info
                tool_number = f"{i+1:2d}."
                name_padded = name.ljust(max_name_length)
                
                if desc:
                    # Multi-line description handling
                    if "\n" in desc:
                        lines = desc.split("\n")
                        first_line = lines[0].strip()
                        remaining = "\n".join(lines[1:]).strip()
                        
                        # Log the first line with the name
                        self.logger.info(f"{tool_number} {name_padded} | {first_line}")
                        
                        # Log remaining lines with proper indentation
                        if remaining:
                            indent = " " * (len(tool_number) + 1 + max_name_length + 3)
                            for line in remaining.split("\n"):
                                self.logger.info(f"{indent}{line.strip()}")
                    else:
                        # Single line description
                        self.logger.info(f"{tool_number} {name_padded} | {desc}")
                else:
                    # No description
                    self.logger.info(f"{tool_number} {name_padded} | (No description available)")
                    
        # End separator
        self.logger.info(separator)
        
    def _extract_tool_name(self, tool):
        """Extract the name from a tool object."""
        if hasattr(tool, 'name'):
            return tool.name
        elif isinstance(tool, dict) and 'name' in tool:
            return tool['name']
        elif isinstance(tool, tuple) and len(tool) > 0:
            if isinstance(tool[0], str):
                return tool[0]
            elif hasattr(tool[0], 'name'):
                return tool[0].name
            elif isinstance(tool[0], dict) and 'name' in tool[0]:
                return tool[0]['name']
        return None
        
    def _extract_tool_description(self, tool):
        """Extract the description from a tool object."""
        # Try different ways to get the description based on common formats
        
        # Case 1: Direct description attribute
        if hasattr(tool, 'description'):
            return tool.description
            
        # Case 2: Description in a dictionary
        elif isinstance(tool, dict):
            if 'description' in tool:
                return tool['description']
            elif 'doc' in tool:
                return tool['doc']
            elif 'help' in tool:
                return tool['help']
                
        # Case 3: Description in a tuple (common format: name, description, params)
        elif isinstance(tool, tuple) and len(tool) > 1:
            if isinstance(tool[1], str):
                return tool[1]
            elif hasattr(tool[1], 'description'):
                return tool[1].description
            elif isinstance(tool[1], dict) and 'description' in tool[1]:
                return tool[1]['description']
                
        # Case 4: Check for 'schema' or 'meta' attributes that might contain a description
        elif hasattr(tool, 'schema') and tool.schema:
            schema = tool.schema
            if hasattr(schema, 'description'):
                return schema.description
            elif isinstance(schema, dict) and 'description' in schema:
                return schema['description']
                
        elif hasattr(tool, 'meta') and tool.meta:
            meta = tool.meta
            if hasattr(meta, 'description'):
                return meta.description
            elif isinstance(meta, dict) and 'description' in meta:
                return meta['description']
                
        # Case 5: Check for documentation from function objects
        elif hasattr(tool, '__doc__') and tool.__doc__:
            return tool.__doc__
            
        # Case 6: Check for a 'get_description' method
        elif hasattr(tool, 'get_description') and callable(tool.get_description):
            try:
                return tool.get_description()
            except Exception:
                pass
                
        return None

    def _extract_tool_names(self, tools):
        """Extract tool names from different possible tool formats."""
        tool_names = []
        
        if not tools:
            return tool_names
            
        for tool in tools:
            # Handle different possible formats
            if hasattr(tool, 'name'):
                tool_names.append(tool.name)
            elif isinstance(tool, dict) and 'name' in tool:
                tool_names.append(tool['name'])
            elif isinstance(tool, tuple) and len(tool) > 0:
                # If it's a tuple, try to get the name from it
                first_item = tool[0]
                if isinstance(first_item, str):
                    tool_names.append(first_item)
                elif hasattr(first_item, 'name'):
                    tool_names.append(first_item.name)
                elif isinstance(first_item, dict) and 'name' in first_item:
                    tool_names.append(first_item['name'])
                else:
                    self.logger.warning(f"Unknown tool format in tuple: {tool}")
            else:
                self.logger.warning(f"Unknown tool format: {tool}")
                
        return tool_names
        
    def _create_tool_functions(self, client, raw_tools, tool_names):
        """Create enhanced callable functions with metadata directly instead of MCPTool objects."""
        tool_objects = {}
        
        # If we have no tool names, we can't create tools
        if not tool_names:
            return tool_objects
            
        # First, extract tool descriptions from raw_tools if available
        tool_descriptions = {}
        for tool in raw_tools:
            name = self._extract_tool_name(tool)
            if name:
                description = self._extract_tool_description(tool)
                if description:
                    tool_descriptions[name] = description
        
        # Create an enhanced function for each tool name
        for name in tool_names:
            # Create a closure to capture the tool name
            def make_tool_function(tool_name):
                # Store the tool_name in the closure
                name_in_closure = tool_name
                
                # Store the service reference for closure
                service = self
                
                # Define a function that directly communicates with MCP server
                def func(self_or_none=None, **kwargs):
                    # self_or_none is ignored - it's just there to handle if called as a method
                    # The actual service reference is captured in the closure
                    
                    # Use a command to directly call the server
                    with service._lock:
                        # Generate a unique request ID
                        request_id = service._next_request_id
                        service._next_request_id += 1
                        
                        # Create a result queue for this request
                        result_queue = queue.Queue()
                        service._result_queues[request_id] = result_queue
                    
                    # Submit the command
                    service._submit_command({
                        "action": "call_tool",
                        "request_id": request_id,
                        "tool_name": name_in_closure,
                        "args": kwargs
                    })
                    
                    # Wait for the result
                    try:
                        result = result_queue.get(timeout=30.0)
                        if result.get("success"):
                            return result.get("result")
                        else:
                            raise RuntimeError(f"Tool execution error: {result.get('error')}")
                    finally:
                        # Clean up
                        with service._lock:
                            if request_id in service._result_queues:
                                del service._result_queues[request_id]
                                
                return func
                
            # Create the function
            tool_func = make_tool_function(name)
            
            # Set basic metadata
            description = tool_descriptions.get(name, f"Call the {name} tool")
            tool_func.__name__ = name
            tool_func.__doc__ = description
            
            # Extract parameter descriptions from the function docstring if available
            param_descriptions = {}
            if tool_func.__doc__:
                # Simple docstring parsing to find parameter descriptions
                doc_lines = tool_func.__doc__.split('\n')
                for line in doc_lines:
                    line = line.strip()
                    if ':' in line and line.split(':')[0].strip().startswith('param'):
                        parts = line.split(':')
                        param_name = parts[0].strip().split(' ')[-1]
                        param_desc = ':'.join(parts[1:]).strip()
                        param_descriptions[param_name] = param_desc
            
            # Add enhanced metadata as attributes directly on the function
            tool_func.name = name
            tool_func.description = description
            tool_func.inputs = {}  # Will be filled below
            tool_func.output_description = f"Result of the {name} tool"
            
            # Parse parameter info for the inputs schema
            try:
                sig = inspect.signature(tool_func)
                for param_name, param in sig.parameters.items():
                    # Use provided description or generate a placeholder
                    param_desc = "Parameter"
                    if param_descriptions and param_name in param_descriptions:
                        param_desc = param_descriptions[param_name]
                        
                    # Get type from annotation if available
                    param_type = param.annotation if param.annotation != inspect.Parameter.empty else Any
                    
                    tool_func.inputs[param_name] = {
                        "type": param_type,
                        "description": param_desc
                    }
            except Exception as e:
                self.logger.warning(f"Error parsing signature for {name}: {e}")
                # If we can't parse the signature, create a generic input
                tool_func.inputs = {"kwargs": {"type": Dict[str, Any], "description": f"Arguments for the {name} tool"}}
            
            # Store the function directly
            tool_objects[name] = tool_func
            
        return tool_objects

    def _create_client(self):
        """Create an MCPClient based on the connection type."""
        if self.connection_type == "sse":
            return MCPClient.create_sse_client(
                server_url=self.server_url,
                sampling_callback=self.sampling_callback
            )
        else:  # stdio
            return MCPClient(
                command=self.command,
                args=self.args,
                env=self.env,
                sampling_callback=self.sampling_callback
            )
            
    async def _process_commands(self, client):
        """Process commands from the queue."""
        while self.running:
            try:
                # Check for commands (non-blocking)
                try:
                    command = self._command_queue.get_nowait()
                except queue.Empty:
                    await asyncio.sleep(0.1)
                    continue
                    
                # Process the command
                action = command.get("action")
                
                if action == "stop":
                    break
                    
                elif action == "call_tool":
                    request_id = command.get("request_id")
                    tool_name = command.get("tool_name")
                    args = command.get("args", {})
                    
                    try:
                        # Call the tool
                        result = await client.call_tool(tool_name, args)
                        # Put the result in the result queue
                        self._result_queues[request_id].put({"success": True, "result": result})
                    except Exception as e:
                        # Put the error in the result queue
                        self._result_queues[request_id].put({"success": False, "error": str(e)})
                        
            except Exception as e:
                self.logger.error(f"Error processing command: {e}")
                
    def _submit_command(self, command):
        """Submit a command to the service."""
        self._command_queue.put(command)
        
    def _call_tool(self, tool_name, args):
        """Call a tool and wait for the result."""
        if not self.connected:
            raise RuntimeError("MCP Tool Service is not connected")
            
        # Check if tool_name refers to a callable function directly
        if tool_name in self._tool_cache:
            tool = self._tool_cache[tool_name]
            # If it's a callable function, call it directly
            if callable(tool):
                return tool(**args)
            
        # Otherwise, use the standard approach through the command queue
        with self._lock:
            # Generate a unique request ID
            request_id = self._next_request_id
            self._next_request_id += 1
            
            # Create a result queue for this request
            result_queue = queue.Queue()
            self._result_queues[request_id] = result_queue
            
        # Submit the command
        self._submit_command({
            "action": "call_tool",
            "request_id": request_id,
            "tool_name": tool_name,
            "args": args
        })
        
        # Wait for the result
        try:
            result = result_queue.get(timeout=30.0)
            
            if result.get("success"):
                return result.get("result")
            else:
                raise RuntimeError(f"Tool execution error: {result.get('error')}")
        finally:
            # Clean up
            with self._lock:
                if request_id in self._result_queues:
                    del self._result_queues[request_id]
                    
    def get_tool_functions(self) -> Dict[str, Callable]:
        """
        Get all available tools as callable functions with metadata.
        
        Returns:
            Dictionary of tool name to callable function.
        """
        if not self.connected:
            raise RuntimeError("MCP Tool Service is not connected")
            
        # Return the cached tool functions
        return self._tool_cache
        
    def get_tools(self) -> List[Callable]:
        """
        Get all available tools as a list of callable functions with metadata.
        
        Returns:
            List of callable functions with metadata.
        """
        if not self.connected:
            raise RuntimeError("MCP Tool Service is not connected")
            
        # Return the tools as a list
        return list(self._tool_cache.values())


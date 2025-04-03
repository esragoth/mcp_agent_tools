import inspect
import logging
import functools
from typing import Dict, Any, Optional, Callable, List, Tuple, Type
import sys
from mcp.types import CallToolResult
# Import MCP related classes
from .models import MCPTool
from .mcp_tool_service import MCPToolService
from .smol_tool_converter import MCPToSmolToolConverter, convert_mcp_to_smol
from smolagents.tools import ToolCollection
# Try to import SmolTool, but create a fallback if not available
try:
    from smolagents.tools import Tool as SmolTool
except ImportError:
    # Create a minimal version for testing/type checking
    class SmolTool:
        """Fallback implementation when smolagents is not installed."""
        name = ""
        description = ""
        inputs = {}
        output_type = "string"
        
        def __init__(self, **kwargs):
            pass
            
        def forward(self, **kwargs):
            pass
            
        def validate_arguments(self):
            pass

class SmolMCPToolFactory:
    """
    Factory class that converts MCPToolService tools to SmolAgents tools if needed.
    
    This class can either accept an existing MCPToolService or create a new one.
    It then provides methods to convert MCPTool objects to SmolAgents Tool objects.
    """
    
    def __init__(
        self,
        service: Optional[MCPToolService] = None,
        server_url: Optional[str] = None,
        command: Optional[str] = None,
        args: Optional[List[str]] = None,
        env: Optional[Dict[str, str]] = None,
        sampling_callback: Optional[Callable] = None,
        logger: Optional[logging.Logger] = None,
        own_service: bool = True
    ):
        """
        Initialize the SmolMCPToolFactory.
        
        You can either:
        1. Provide an existing MCPToolService via the 'service' parameter, or
        2. Provide connection parameters to create a new MCPToolService
        
        Args:
            service: An existing MCPToolService instance to use
            server_url: URL for SSE connection (if creating a new service)
            command: Command for stdio connection (if creating a new service)
            args: Arguments for stdio connection (if creating a new service)
            env: Environment variables for stdio connection (if creating a new service)
            sampling_callback: Callback for handling sampling messages (if creating a new service)
            logger: Logger instance to use
            own_service: Whether this factory owns the service and should close it on cleanup
                         (set to False if you want to manage the service lifecycle externally)
        """
        # Set up logger
        self.logger = logger or logging.getLogger(__name__)

        # Flag to track whether we own the service and should close it on cleanup
        self.own_service = own_service
        
        # Use the provided service or create a new one
        if service is not None:
            self.service = service
            self.started = service.connected  # Use the service's connection status
            if not self.started:
                self.logger.warning("Provided MCPToolService is not connected")
        else:
            # Initialize a new MCP Tool Service
            self.service = MCPToolService(
                server_url=server_url,
                command=command,
                args=args,
                env=env,
                sampling_callback=sampling_callback,
                logger=self.logger
            )
            
            # Start the service
            self.started = self.service.start()
            if not self.started:
                self.logger.error("Failed to start MCP Tool Service")
                
            # We own this service since we created it
            self.own_service = True
            
        # Dictionary to store original functions
        self.original_functions = {}
        
        # Dictionary to store wrapper functions
        self.wrapper_functions = {}
        
        # Create a converter instance
        self.converter = MCPToSmolToolConverter(logger=self.logger)
        
        # Load all tools and create wrapper functions immediately
        self._load_tools_and_create_wrappers()
    
    def _load_tools_and_create_wrappers(self):
        """
        Load all tools from the service directly.
        Since they are now enhanced callable functions with metadata, no wrappers needed.
        """
        if not self.started:
            self.logger.warning("MCP Tool Service is not started, cannot load tools")
            return
            
        try:
            # Get all tools - these are now enhanced callable functions
            functions = self._get_tools()
            
            # Store them directly in original_functions and wrapper_functions
            for func in functions:
                if hasattr(func, 'name'):
                    name = func.name
                    self.original_functions[name] = func
                    self.wrapper_functions[name] = func  # No wrapper needed
                    self.logger.debug(f"Stored enhanced function: {name}")
                    
                    # Log the inputs to help debug parameter mapping
                    if hasattr(func, 'inputs'):
                        self.logger.info(f"Tool '{name}' has inputs: {func.inputs}")
                else:
                    self.logger.warning(f"Tool function has no name attribute")
        except Exception as e:
            self.logger.error(f"Error loading tools: {e}")
    
    def __del__(self):
        """Clean up resources when the factory is garbage collected."""
        self.close()
    
    def close(self):
        """
        Stop the MCP Tool Service if we own it.
        
        If the service was provided externally and own_service is False,
        this method won't close the service.
        """
        if hasattr(self, 'service') and self.own_service:
            self.service.stop()
            self.logger.info("Closed MCPToolService owned by factory")
            
    @classmethod
    def from_service(cls, service: MCPToolService, own_service: bool = False):
        """
        Create a SmolMCPToolFactory from an existing MCPToolService.
        
        Args:
            service: The MCPToolService to use
            own_service: Whether this factory should close the service on cleanup
            
        Returns:
            A SmolMCPToolFactory instance using the provided service
        """
        return cls(service=service, own_service=own_service)
        
    @classmethod
    def create_new(cls,
        server_url: Optional[str] = None,
        command: Optional[str] = None,
        args: Optional[List[str]] = None,
        env: Optional[Dict[str, str]] = None,
        sampling_callback: Optional[Callable] = None,
        logger: Optional[logging.Logger] = None,
        connection_timeout: float = 10.0,
        max_retries: int = 3
    ):
        """
        Create a SmolMCPToolFactory with a new MCPToolService.
        
        Args:
            server_url: URL for SSE connection
            command: Command for stdio connection
            args: Arguments for stdio connection
            env: Environment variables for stdio connection
            sampling_callback: Callback for handling sampling messages
            logger: Logger instance to use
            connection_timeout: Timeout in seconds for connection attempts
            max_retries: Maximum number of connection retry attempts
            
        Returns:
            A SmolMCPToolFactory instance with a new service
        """
        return cls(
            server_url=server_url,
            command=command,
            args=args,
            env=env,
            sampling_callback=sampling_callback,
            logger=logger,
            own_service=True
        )
    
    def _get_tools(self) -> List[Callable]:
        """
        Get all available tools as callable functions with metadata.
        
        Returns:
            List of callable functions with metadata.
        """
        if not self.started:
            self.logger.warning("MCP Tool Service is not started or not connected to server")
            return []
        
        try:
            # Get the callable functions from the service
            functions = self.service.get_tools()
            self.logger.info(f"Retrieved {len(functions)} callable tool functions")
            return functions
        except Exception as e:
            self.logger.error(f"Error retrieving tools: {e}")
            return []
    
    
    def mcp_to_smolagent_tool(self, mcp_tool: Callable) -> 'SmolTool':
        """
        Convert an MCP tool (callable with metadata) to a SmolAgents Tool.
        
        Args:
            mcp_tool: The MCP tool function with metadata
            
        Returns:
            A SmolAgents Tool object

        """
        tool_info_list= []
        with ToolCollection.from_mcp({"url": "http://localhost:8000/sse"}) as tool_collection:
            for tool in tool_collection.tools:
                tool_info = {
                    "name": tool.name,
                    "description": tool.description,
                    "inputs": tool.inputs,
                    "output_type": tool.output_type
                }
                tool_info_list.append(tool_info)
            self.logger.info(f"Retrieved tool information: {tool_info_list}")
        
        # Check if we can find this tool in the collected tools by name
        for tool_info in tool_info_list:
            if tool_info['name'] == mcp_tool.name:
                # Override the inputs with what's in the tool collection
                mcp_tool.inputs = tool_info['inputs']
                self.logger.info(f"Updated inputs for tool {mcp_tool.name}")
                break
            
        # For any tool with matching name in tool_info_list, skip validation
        skip_validation = any(tool_info['name'] == mcp_tool.name for tool_info in tool_info_list)
        if skip_validation:
            self.logger.info(f"Skipping validation for tool {mcp_tool.name}")
            
        # Convert the tool
        return self.converter.convert(mcp_tool, skip_validation=skip_validation)
        
    def get_smolagent_tools(self) -> List[Any]:
        """
        Get all available tools as SmolAgents Tool objects.
        
        This is the main public API for accessing tools in this class.
        The other method (_get_tools) is a private implementation detail
        and should not be used directly.
        
        Returns:
            List of SmolAgents Tool objects for agent use
        """
            
        # Get the MCPTool objects
        mcp_tools = self._get_tools()
        
        # Convert to SmolAgents Tool objects
        smolagent_tools = []
        
        # Process all tools
        for tool in mcp_tools:
            try:
                # Convert the tool
                smolagent_tool = self.mcp_to_smolagent_tool(tool)
                smolagent_tools.append(smolagent_tool)
                self.logger.info(f"Converted tool {tool.name}")
            except Exception as e:
                self.logger.error(f"Error converting {tool.name} to SmolAgents Tool: {e}")
                
        self.logger.info(f"Converted {len(smolagent_tools)} tools")
        self.logger.info(f"Wrapper functions available: {list(self.wrapper_functions.keys())}")
        
        # Return the SmolAgents tools
        return smolagent_tools
    


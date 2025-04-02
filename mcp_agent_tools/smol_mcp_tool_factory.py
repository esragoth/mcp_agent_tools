import inspect
import logging
from typing import Dict, Any, Optional, Callable, List

# Import MCP related classes
from .models import MCPTool
from .mcp_tool_service import MCPToolService
from .exceptions import (
    MCPAgentToolsError,
    ConversionError,
    ServiceError,
    ToolNotFoundError,
)
from smolagents.tools import Tool as SmolTool

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
    
    def get_tools(self) -> List[MCPTool]:
        """
        Get all available MCP tools.
        
        Returns:
            List of MCPTool objects.
        """
        if not self.started:
            self.logger.warning("MCP Tool Service is not started or not connected to server")
            return []
        
        try:
            # Get the MCPTool objects from the service
            mcp_tools = self.service.get_tools()
            self.logger.info(f"Retrieved {len(mcp_tools)} MCPTool objects")
            return mcp_tools
        except Exception as e:
            error_msg = f"Error retrieving tools: {e}"
            self.logger.error(error_msg)
            raise ServiceError(error_msg) from e
        
    def mcp_to_smolagent_tool(self, mcp_tool: MCPTool) -> SmolTool:
        """
        Convert an MCPTool to a SmolAgents Tool using a class-based approach.
        
        Creates a dynamic class that inherits from SmolAgents Tool class with properly
        defined inputs and output.
        
        Args:
            mcp_tool: The MCPTool to convert
            
        Returns:
            A SmolAgents Tool instance
            
        Raises:
            ConversionError: If there's an error converting the tool
        """
        if not mcp_tool:
            raise ConversionError("Cannot convert None to SmolAgents Tool")
            
        if not hasattr(mcp_tool, 'name') or not mcp_tool.name:
            raise ConversionError("MCPTool must have a name")
            
        if not hasattr(mcp_tool, 'function') or not callable(mcp_tool.function):
            raise ConversionError(f"MCPTool '{mcp_tool.name}' must have a callable function")

        try:
            # Extract information from the MCPTool
            name = mcp_tool.name
            description = mcp_tool.description
            function = mcp_tool.function
            
            # Create input schema
            input_schema = {}
            param_names = []
            
            # Check if we need to rename 'kwargs' parameter (it causes issues with forward method)
            has_kwargs_param = False
            
            if hasattr(mcp_tool, 'inputs') and mcp_tool.inputs:
                for param_name, param_info in mcp_tool.inputs.items():
                    # Check if we have a parameter named 'kwargs'
                    if param_name == 'kwargs':
                        has_kwargs_param = True
                        # Rename it to avoid conflicts with the **kwargs signature
                        param_name = 'query'
                    
                    param_names.append(param_name)
                    param_type = "string"  # Default type
                    
                    # Try to convert Python type to JSON schema type
                    if 'type' in param_info:
                        python_type = param_info['type']
                        if python_type == str or python_type == 'string':
                            param_type = "string"
                        elif python_type == int or python_type == 'integer':
                            param_type = "integer"
                        elif python_type == float or python_type == 'number':
                            param_type = "number"
                        elif python_type == bool or python_type == 'boolean':
                            param_type = "boolean"
                        elif python_type == list or python_type == 'array':
                            param_type = "array"
                        elif python_type == dict or python_type == 'object':
                            param_type = "object"
                    
                    input_schema[param_name] = {
                        "type": param_type,
                        "description": param_info.get('description', f"Parameter: {param_name}")
                    }
            
            # If no parameters were found, add a default one to satisfy SmolAgents
            if not param_names:
                param_names.append("query")
                input_schema["query"] = {
                    "type": "string",
                    "description": "Input query for the tool"
                }
            
            # Create a dynamic class that inherits from SmolTool
            class DynamicMCPTool(SmolTool):
                # Set class attributes
                name = mcp_tool.name
                description = mcp_tool.description
                inputs = input_schema  # Use the renamed variable to avoid name conflict
                output_type = "string"  # Default to string, can be refined later
                
                def __init__(self, **kwargs):
                    super().__init__(**kwargs)
                    # Store a reference to the original function
                    self.mcp_function = function
                    # Store reference to whether we had a kwargs parameter that was renamed
                    self.had_kwargs_param = has_kwargs_param
            
            # Create the most appropriate forward method
            if has_kwargs_param:
                # Special case for the tool that had a 'kwargs' parameter
                # We need to map the query parameter back to 'kwargs'
                forward_code = """
def forward(self, query):
    \"\"\"Call the original MCP tool function with the provided arguments.\"\"\"
    return self.mcp_function(kwargs=query)
"""
            else:
                # Normal case - dynamically create the forward method with explicit parameters
                param_str = ", ".join(["self"] + param_names)
                kwargs_str = ", ".join([f"{name}={name}" for name in param_names])
                
                # Create the forward method code
                forward_code = f"""
def forward({param_str}):
    \"\"\"Call the original MCP tool function with the provided arguments.\"\"\"
    return self.mcp_function({kwargs_str})
"""
            
            # Create namespace for exec
            namespace = {}
            exec(forward_code, namespace)
            
            # Attach the method to the class
            DynamicMCPTool.forward = namespace["forward"]
            
            # Update class name for better debugging
            DynamicMCPTool.__name__ = f"MCPTool_{name}"
            
            # Create and return an instance of the dynamic class
            tool_instance = DynamicMCPTool()
            
            # Log information about the created tool
            self.logger.debug(f"Created SmolAgents tool using class approach: {tool_instance.__class__.__name__}")
            self.logger.debug(f"Tool inputs: {tool_instance.inputs}")
            self.logger.debug(f"Forward method signature: {inspect.signature(tool_instance.forward)}")
            
            return tool_instance
            
        except Exception as e:
            error_msg = f"Error converting MCPTool '{mcp_tool.name}' to SmolAgents Tool: {e}"
            self.logger.error(error_msg)
            raise ConversionError(error_msg) from e
        
    def get_smolagent_tools(self) -> List[Any]:
        """
        Get all available tools as SmolAgents Tool objects.
        
        This method converts the MCPTool objects to SmolAgents Tool objects
        using the SmolAgents tool decorator.
        
        Returns:
            List of SmolAgents Tool objects
            
        Raises:
            ServiceError: If there's an error with the MCP Tool Service
        """
            
        # Get the MCPTool objects
        try:
            mcp_tools = self.get_tools()
            
            # Convert to SmolAgents Tool objects
            smolagent_tools = []
            conversion_errors = []
            
            for tool in mcp_tools:
                try:
                    smolagent_tool = self.mcp_to_smolagent_tool(tool)
                    smolagent_tools.append(smolagent_tool)
                except ConversionError as e:
                    # Collect errors but continue processing other tools
                    error_msg = f"Error converting {tool.name if hasattr(tool, 'name') else 'unknown'} to SmolAgents Tool: {e}"
                    self.logger.error(error_msg)
                    conversion_errors.append(error_msg)
                    
            self.logger.info(f"Converted {len(smolagent_tools)} tools to SmolAgents Tools")
            
            # If no tools were successfully converted but we had errors, raise an exception
            if not smolagent_tools and conversion_errors:
                raise ConversionError(f"Failed to convert any tools. Errors: {', '.join(conversion_errors)}")
                
            return smolagent_tools
            
        except ServiceError:
            # Re-raise ServiceError exceptions
            raise
        except Exception as e:
            error_msg = f"Error getting SmolAgents tools: {e}"
            self.logger.error(error_msg)
            raise ServiceError(error_msg) from e


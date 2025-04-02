import inspect
from typing import Dict, Any

# Create a generic MCPTool class that represents a tool from the MCP server
class MCPTool:
    """
    A generic tool class that represents a tool from an MCP server.
    
    This class is independent of any agent framework and provides a standard
    representation for MCP tools with name, description, and function.
    """
    
    def __init__(self, name, description, function, input_descriptions=None, output_description=None):
        """
        Initialize the MCPTool.
        
        Args:
            name: The name of the tool
            description: A detailed description of what the tool does
            function: The callable function that implements the tool
            input_descriptions: Optional dictionary of parameter descriptions
            output_description: Optional description of the return value
        """
        self.name = name
        self.description = description
        self.function = function
        
        # Parse function signature to get parameter info
        self.inputs = {}
        try:
            sig = inspect.signature(function)
            for param_name, param in sig.parameters.items():
                if param_name == 'self':
                    continue
                    
                # Use provided description or generate a placeholder
                param_desc = "Parameter"
                if input_descriptions and param_name in input_descriptions:
                    param_desc = input_descriptions[param_name]
                    
                # Get type from annotation if available
                param_type = param.annotation if param.annotation != inspect.Parameter.empty else Any
                
                self.inputs[param_name] = {
                    "type": param_type,
                    "description": param_desc
                }
        except Exception:
            # If we can't parse the signature, create a generic input
            self.inputs = {"args": {"type": Dict[str, Any], "description": "Arguments for the tool"}}
            
        # Set output description
        self.output_description = output_description or "Result of the tool execution"
        
    def __call__(self, *args, **kwargs):
        """Call the tool function with the provided arguments."""
        return self.function(*args, **kwargs)
        
    def __str__(self):
        """String representation of the tool."""
        return f"MCPTool({self.name})"
        
    def __repr__(self):
        """Detailed representation of the tool."""
        return f"MCPTool(name='{self.name}', description='{self.description[:30]}...', inputs={list(self.inputs.keys())})"


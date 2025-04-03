"""
Tool converter module for translating MCP tools to SmolAgent tools.
"""

import inspect
import logging
from typing import Dict, Any, Optional, Callable, List, Type, Union, get_type_hints

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

class MCPToSmolToolConverter:
    """
    Converter for MCP tools to SmolAgent tools.
    
    This class provides methods to convert MCP tool definitions 
    (either as callable functions or objects with forward methods)
    to SmolAgent Tool objects that can be used with SmolAgent frameworks.
    """
    
    # Valid SmolAgent input types
    VALID_TYPES = [
        'string', 'boolean', 'integer', 'number', 
        'image', 'audio', 'array', 'object', 
        'any', 'null'
    ]
    
    # Common params to filter out
    FILTERED_PARAMS = ['self', 'self_or_none', 'kwargs', 'args']
    
    def __init__(self, logger: Optional[logging.Logger] = None):
        """
        Initialize the converter.
        
        Args:
            logger: Logger instance to use
        """
        # Set up logger
        self.logger = logger or logging.getLogger(__name__)
        
        # Store SmolTool class reference 
        try:
            from smolagents.tools import Tool as ImportedSmolTool
            self.SmolTool = ImportedSmolTool
        except ImportError:
            self.logger.warning("smolagents.tools.Tool not found, using fallback implementation")
            self.SmolTool = SmolTool
    
    def create_non_validating_tool(self) -> Type:
        """Create a subclass of SmolTool that skips input validation."""
        BaseTool = self.SmolTool
        
        class NoValidateSmolTool(BaseTool):
            def validate_arguments(self):
                # Skip validation
                pass
                
        return NoValidateSmolTool
    
    def _extract_function_metadata(self, func_or_method: Callable) -> Dict[str, Any]:
        """
        Extract metadata from a function or method signature.
        
        Args:
            func_or_method: The function or method to inspect
            
        Returns:
            Dictionary with parameter information
        """
        metadata = {
            'params': [],
            'optional_params': {},
            'type_hints': {},
        }
        
        try:
            # Get the signature
            sig = inspect.signature(func_or_method)
            
            # Get parameters
            for name, param in sig.parameters.items():
                # Skip filtered params
                if name in self.FILTERED_PARAMS or name.startswith('self_'):
                    continue
                    
                # Add to parameters list
                metadata['params'].append(name)
                
                # Store default values for optional parameters
                if param.default is not inspect.Parameter.empty:
                    metadata['optional_params'][name] = param.default
                    
                # Store type annotations
                if param.annotation is not inspect.Parameter.empty:
                    metadata['type_hints'][name] = param.annotation
            
            # Try to get additional type hints from function
            try:
                type_hints = get_type_hints(func_or_method)
                for name, hint in type_hints.items():
                    if name in metadata['params'] and name not in metadata['type_hints']:
                        metadata['type_hints'][name] = hint
            except Exception:
                pass
                
        except Exception as e:
            self.logger.warning(f"Error extracting function metadata: {e}")
            
        return metadata
    
    def _normalize_input_type(self, type_hint: Any) -> str:
        """
        Convert a Python type hint to a SmolAgent input type.
        
        Args:
            type_hint: Python type annotation
            
        Returns:
            SmolAgent compatible type string
        """
        # First handle common Python types
        type_str = str(type_hint)
        
        if type_str == "<class 'str'>" or "str" in type_str:
            return "string"
        elif type_str == "<class 'bool'>" or "bool" in type_str:
            return "boolean"
        elif type_str == "<class 'int'>" or "int" in type_str:
            return "integer"
        elif type_str == "<class 'float'>" or "float" in type_str:
            return "number"
        elif "list" in type_str or "List" in type_str:
            return "array"
        elif "dict" in type_str or "Dict" in type_str:
            return "object"
        elif "Any" in type_str or "any" in type_str:
            return "any"
        elif "None" in type_str or "Optional" in type_str:
            # Handle Optional[X] - extract the inner type
            if "Optional[" in type_str and "]" in type_str:
                inner_type = type_str.split("Optional[")[1].split("]")[0]
                return self._normalize_input_type(inner_type)
            return "null"
        else:
            # Default to 'any' for unknown types
            return "any"
    
    def _normalize_inputs_dict(self, inputs_dict: Dict) -> Dict:
        """
        Normalize an inputs dictionary to ensure all types are valid SmolAgent types.
        
        Args:
            inputs_dict: Raw inputs dictionary
            
        Returns:
            Normalized inputs dictionary
        """
        normalized = {}
        
        for key, value in inputs_dict.items():
            # Skip filtered parameters
            if key in self.FILTERED_PARAMS or key.startswith('self_'):
                continue
                
            if isinstance(value, dict):
                # Clone the dict so we don't modify the original
                normalized_value = value.copy()
                
                # Ensure the input has a type and it's valid
                if 'type' in normalized_value:
                    input_type = normalized_value['type']
                    
                    # Convert to valid SmolAgent type if needed
                    if input_type not in self.VALID_TYPES:
                        normalized_value['type'] = self._normalize_input_type(input_type)
                        
                normalized[key] = normalized_value
        
        return normalized
    
    def _create_inputs_dict(self, tool, metadata: Dict) -> Dict:
        """
        Create a valid inputs dictionary for the SmolAgent tool.
        
        Args:
            tool: The original MCP tool
            metadata: Extracted function metadata
            
        Returns:
            SmolAgent compatible inputs dictionary
        """
        # First check if the tool already has an inputs dict
        if hasattr(tool, 'inputs') and isinstance(tool.inputs, dict):
            # Normalize the existing inputs dict
            inputs = self._normalize_inputs_dict(tool.inputs)
            
            # Check for optional parameters and mark them as nullable
            for param in metadata['optional_params']:
                if param in inputs:
                    inputs[param]['nullable'] = True
                    
            return inputs
        
        # Otherwise create a new inputs dict from the function metadata
        inputs = {}
        
        for param in metadata['params']:
            input_def = {
                'description': f"Parameter: {param}",
                'type': 'any'
            }
            
            # Add type information if available
            if param in metadata['type_hints']:
                input_def['type'] = self._normalize_input_type(metadata['type_hints'][param])
                
            # Mark optional parameters as nullable
            if param in metadata['optional_params']:
                input_def['nullable'] = True
                
            inputs[param] = input_def
            
        return inputs
    
    def convert(self, mcp_tool: Union[Callable, Any], 
                skip_validation: bool = False, 
                constructor_args: Optional[Dict] = None) -> Any:
        """
        Convert an MCP tool to a SmolAgent Tool.
        
        Args:
            mcp_tool: The MCP tool (function or object)
            skip_validation: Whether to skip argument validation
            constructor_args: Constructor arguments for class-based tools
            
        Returns:
            A SmolAgent Tool instance
        """
        # Ensure we have the necessary attributes
        if not hasattr(mcp_tool, 'name') or not hasattr(mcp_tool, 'description'):
            raise ValueError(f"MCP tool missing required attributes: name and/or description")
            
        tool_name = mcp_tool.name
        tool_description = mcp_tool.description
        
        # Determine if this is a class-based tool or a function-based tool
        is_class_tool = hasattr(mcp_tool, 'forward') and callable(mcp_tool.forward)
        
        # Extract function metadata
        if is_class_tool:
            # For class-based tools, inspect the forward method
            func_metadata = self._extract_function_metadata(mcp_tool.forward)
            # Also check constructor parameters
            if constructor_args is None:
                constructor_args = {}
                try:
                    init_sig = inspect.signature(mcp_tool.__init__)
                    for param_name, param in init_sig.parameters.items():
                        if param_name not in self.FILTERED_PARAMS and param.default is inspect.Parameter.empty:
                            self.logger.warning(f"Tool {tool_name} requires constructor parameter: {param_name}")
                except Exception:
                    pass
        else:
            # For function-based tools, inspect the function itself
            func_metadata = self._extract_function_metadata(mcp_tool)
        
        # Create inputs dictionary
        tool_inputs = self._create_inputs_dict(mcp_tool, func_metadata)
        
        # Get output type
        tool_output_type = getattr(mcp_tool, 'output_type', 'string')
        
        # Choose the base class based on validation needs
        BaseTool = self.create_non_validating_tool() if skip_validation else self.SmolTool
        
        # Create the wrapper class using a factory function 
        # to properly capture the variables from this scope
        def create_tool_class():
            class DynamicMCPToolWrapper(BaseTool):
                name = tool_name
                description = tool_description 
                inputs = tool_inputs
                output_type = tool_output_type
                
                def __init__(self2, **kwargs):
                    # Initialize the base class
                    super().__init__(**kwargs)
                    # Store constructor args
                    self2.constructor_args = constructor_args or {}
                    # Store reference to logger
                    self2.logger = logging.getLogger(__name__)
                    # Store reference to the original tool
                    self2.original_tool = mcp_tool
                    # Store metadata
                    self2.func_metadata = func_metadata
                    
                def _parse_call_tool_result(self2, result):
                    """Parse CallToolResult objects to extract content"""
                    import json
                    from mcp.types import CallToolResult
                    
                    if not isinstance(result, CallToolResult):
                        return result
                    
                    # Check for error
                    if result.isError:
                        self2.logger.warning(f"Tool {self2.name} returned an error")
                    
                    # Extract text content from the result
                    text_contents = []
                    for item in result.content:
                        if hasattr(item, 'type') and item.type == 'text':
                            text_contents.append(item.text)
                    
                    # If there's just one text content, parse it if it looks like JSON
                    if len(text_contents) == 1:
                        text = text_contents[0]
                        try:
                            if text.strip().startswith('{') or text.strip().startswith('['):
                                return json.loads(text)
                        except json.JSONDecodeError:
                            pass
                        return text
                    
                    # Return the list of text content or empty list
                    return text_contents if text_contents else []
                    
                def forward(self2, **kwargs):
                    """
                    Forward method that routes calls to the original tool.
                    Handles parameter mapping and error reporting.
                    """
                    try:
                        # Set default values for optional parameters if not provided
                        for param, default in self2.func_metadata['optional_params'].items():
                            if param not in kwargs:
                                kwargs[param] = default
                        
                        # Call the appropriate function based on tool type
                        result = None
                        if is_class_tool:
                            # For class-based tools, instantiate and call forward
                            if isinstance(self2.original_tool, type):
                                # If it's a class, instantiate it
                                instance = self2.original_tool(**self2.constructor_args)
                                result = instance.forward(**kwargs)
                            else:
                                # If it's already an instance, call forward
                                result = self2.original_tool.forward(**kwargs)
                        else:
                            # For function-based tools, call directly
                            result = self2.original_tool(**kwargs)
                        
                        # Parse the result before returning
                        return self2._parse_call_tool_result(result)
                        
                    except TypeError as e:
                        # Handle parameter mismatches
                        error_msg = str(e)
                        self2.logger.error(f"Error calling {tool_name}: {error_msg}")
                        
                        # Attempt to fix parameter name mismatches
                        if "got an unexpected keyword argument" in error_msg:
                            # Extract the problematic parameter name
                            param_name = error_msg.split("'")[1] if "'" in error_msg else None
                            if param_name and param_name in kwargs:
                                # Try common variations (snake_case vs camelCase)
                                variations = [
                                    param_name.lower(),  # all lowercase
                                    param_name.replace('_', ''),  # remove underscores
                                    ''.join(w.capitalize() if i > 0 else w.lower() 
                                           for i, w in enumerate(param_name.split('_')))  # camelCase
                                ]
                                
                                # Check if any variation matches expected params
                                for expected in self2.func_metadata['params']:
                                    expected_lower = expected.lower()
                                    if expected_lower in variations or any(v == expected_lower for v in variations):
                                        self2.logger.warning(f"Parameter mismatch: mapping '{param_name}' to '{expected}'")
                                        kwargs[expected] = kwargs.pop(param_name)
                                        return self2.forward(**kwargs)  # Try again with fixed parameter
                        
                        # Re-raise the exception if we couldn't fix it
                        raise
                        
            return DynamicMCPToolWrapper
            
        # Create the wrapper class
        ToolClass = create_tool_class()
        
        # Create and return an instance
        return ToolClass()


def convert_mcp_to_smol(
    mcp_tool: Union[Callable, Any], 
    skip_validation: bool = False,
    constructor_args: Optional[Dict] = None,
    logger: Optional[logging.Logger] = None
) -> Any:
    """
    Convenience function to convert an MCP tool to a SmolAgent tool.
    
    Args:
        mcp_tool: The MCP tool to convert
        skip_validation: Whether to skip argument validation
        constructor_args: Constructor arguments for class-based tools
        logger: Logger instance to use
        
    Returns:
        A SmolAgent Tool instance
    """
    converter = MCPToSmolToolConverter(logger=logger)
    return converter.convert(mcp_tool, skip_validation, constructor_args) 
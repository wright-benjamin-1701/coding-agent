"""Tool registry for managing available tools."""

from typing import Dict, Any
from .base import Tool


class ToolRegistry:
    """Registry for managing available tools."""
    
    def __init__(self):
        self._tools: Dict[str, Tool] = {}
    
    def register(self, tool: Tool):
        """Register a tool."""
        self._tools[tool.name] = tool
    
    def get_tool(self, name: str) -> Tool:
        """Get a tool by name."""
        if name not in self._tools:
            raise ValueError(f"Tool '{name}' not found")
        return self._tools[name]
    
    def get_schemas(self) -> Dict[str, Dict[str, Any]]:
        """Get schemas for all registered tools."""
        schemas = {}
        for name, tool in self._tools.items():
            schemas[name] = {
                "description": tool.description,
                "parameters": tool.parameters_schema,
                "destructive": tool.is_destructive
            }
        return schemas
    
    def list_tools(self) -> list[str]:
        """List all registered tool names."""
        return list(self._tools.keys())
"""
Base tool interface for agent capabilities
"""
from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
import json


@dataclass
class ToolParameter:
    name: str
    type: str
    description: str
    required: bool = True
    default: Optional[Any] = None


@dataclass
class ToolResult:
    success: bool
    content: Optional[str] = None
    data: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


class BaseTool(ABC):
    """Abstract base class for all agent tools"""
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        self.name = self.__class__.__name__.lower().replace("tool", "")
    
    @abstractmethod
    def get_description(self) -> str:
        """Get tool description for the LLM"""
        pass
    
    @abstractmethod
    def get_parameters(self) -> List[ToolParameter]:
        """Get tool parameters schema"""
        pass
    
    @abstractmethod
    async def execute(self, **kwargs) -> ToolResult:
        """Execute the tool with given parameters"""
        pass
    
    def to_llm_function_schema(self) -> Dict[str, Any]:
        """Convert tool to LLM function calling schema"""
        parameters = self.get_parameters()
        
        properties = {}
        required = []
        
        for param in parameters:
            properties[param.name] = {
                "type": param.type,
                "description": param.description
            }
            if param.default is not None:
                properties[param.name]["default"] = param.default
            
            if param.required:
                required.append(param.name)
        
        return {
            "name": self.name,
            "description": self.get_description(),
            "parameters": {
                "type": "object",
                "properties": properties,
                "required": required
            }
        }
    
    def validate_parameters(self, kwargs: Dict[str, Any]) -> bool:
        """Validate provided parameters against schema"""
        parameters = self.get_parameters()
        
        for param in parameters:
            if param.required and param.name not in kwargs:
                return False
        
        return True
    
    def get_capabilities(self) -> Dict[str, Any]:
        """Get tool capabilities and metadata"""
        return {
            "name": self.name,
            "description": self.get_description(),
            "async": True,
            "safe": True,  # Override in dangerous tools
            "categories": ["general"]
        }
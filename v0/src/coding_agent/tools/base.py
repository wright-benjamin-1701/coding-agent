"""Base tool interface."""

from abc import ABC, abstractmethod
from typing import Dict, Any
from ..types import ToolResult


class Tool(ABC):
    """Abstract base class for tools."""
    
    @property
    @abstractmethod
    def name(self) -> str:
        """Tool name."""
        pass
    
    @property
    @abstractmethod
    def description(self) -> str:
        """Tool description."""
        pass
    
    @property
    @abstractmethod
    def parameters_schema(self) -> Dict[str, Any]:
        """Parameters schema for this tool."""
        pass
    
    @property
    @abstractmethod
    def is_destructive(self) -> bool:
        """Whether this tool makes destructive changes."""
        pass
    
    @abstractmethod
    def execute(self, **parameters) -> ToolResult:
        """Execute the tool with given parameters."""
        pass
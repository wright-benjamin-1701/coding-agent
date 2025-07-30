"""Base model provider interface."""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
from ..types import ModelResponse


class ModelProvider(ABC):
    """Abstract base class for model providers."""
    
    @abstractmethod
    def generate(self, prompt: str, **kwargs) -> ModelResponse:
        """Generate a response from the model."""
        pass
    
    @abstractmethod
    def is_available(self) -> bool:
        """Check if the provider is available."""
        pass
"""
Base provider interface for LLM abstraction
"""
from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any, AsyncGenerator
from dataclasses import dataclass


@dataclass
class ChatMessage:
    role: str  # "user", "assistant", "system"
    content: str
    metadata: Optional[Dict[str, Any]] = None


@dataclass
class ModelConfig:
    model_name: str
    max_tokens: Optional[int] = None
    temperature: Optional[float] = None
    top_p: Optional[float] = None
    stop_sequences: Optional[List[str]] = None


@dataclass
class ProviderResponse:
    content: str
    usage: Optional[Dict[str, int]] = None
    model: Optional[str] = None
    finish_reason: Optional[str] = None


class BaseLLMProvider(ABC):
    """Abstract base class for all LLM providers"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.name = self.__class__.__name__
    
    @abstractmethod
    async def chat_completion(
        self,
        messages: List[ChatMessage],
        model_config: ModelConfig,
        stream: bool = False
    ) -> ProviderResponse:
        """Generate chat completion"""
        pass
    
    @abstractmethod
    async def stream_completion(
        self,
        messages: List[ChatMessage],
        model_config: ModelConfig
    ) -> AsyncGenerator[str, None]:
        """Stream chat completion"""
        pass
    
    @abstractmethod
    def list_models(self) -> List[str]:
        """List available models"""
        pass
    
    @abstractmethod
    def validate_config(self) -> bool:
        """Validate provider configuration"""
        pass
    
    def get_model_capabilities(self, model_name: str) -> Dict[str, Any]:
        """Get model-specific capabilities"""
        return {
            "max_context": 4096,
            "supports_tools": False,
            "supports_vision": False,
            "reasoning_level": "medium"
        }
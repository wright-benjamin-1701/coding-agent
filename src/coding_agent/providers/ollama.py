"""Ollama model provider."""

import requests
from typing import Dict, Any, Optional
from .base import ModelProvider
from ..types import ModelResponse


class OllamaProvider(ModelProvider):
    """Ollama model provider implementation."""
    
    def __init__(self, model: str = "llama2", base_url: str = "http://localhost:11434"):
        self.model = model
        self.base_url = base_url
    
    def generate(self, prompt: str, **kwargs) -> ModelResponse:
        """Generate a response using Ollama."""
        try:
            response = requests.post(
                f"{self.base_url}/api/generate",
                json={
                    "model": self.model,
                    "prompt": prompt,
                    "stream": False,
                    **kwargs
                }
            )
            response.raise_for_status()
            data = response.json()
            
            return ModelResponse(
                content=data.get("response", ""),
                metadata=data
            )
        except Exception as e:
            return ModelResponse(
                content="",
                metadata={"error": str(e)}
            )
    
    def is_available(self) -> bool:
        """Check if Ollama is available."""
        try:
            response = requests.get(f"{self.base_url}/api/tags")
            return response.status_code == 200
        except:
            return False
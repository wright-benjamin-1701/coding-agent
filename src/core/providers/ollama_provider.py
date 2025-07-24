"""
Ollama provider implementation
"""
import json
import aiohttp
from typing import Dict, List, Optional, Any, AsyncGenerator
from .base import BaseLLMProvider, ChatMessage, ModelConfig, ProviderResponse


class OllamaProvider(BaseLLMProvider):
    """Ollama local LLM provider"""
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.base_url = config.get("base_url", "http://localhost:11434")
        self.timeout = config.get("timeout", 300)
    
    async def chat_completion(
        self,
        messages: List[ChatMessage],
        model_config: ModelConfig,
        stream: bool = False
    ) -> ProviderResponse:
        """Generate chat completion using Ollama API"""
        
        # Convert messages to Ollama format
        ollama_messages = [
            {"role": msg.role, "content": msg.content}
            for msg in messages
        ]
        
        payload = {
            "model": model_config.model_name,
            "messages": ollama_messages,
            "stream": stream,
            "options": self._build_options(model_config)
        }
        
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=self.timeout)) as session:
            async with session.post(
                f"{self.base_url}/api/chat",
                json=payload
            ) as response:
                if response.status != 200:
                    raise Exception(f"Ollama API error: {response.status}")
                
                result = await response.json()
                
                return ProviderResponse(
                    content=result["message"]["content"],
                    model=result.get("model"),
                    finish_reason="stop"
                )
    
    async def stream_completion(
        self,
        messages: List[ChatMessage],
        model_config: ModelConfig
    ) -> AsyncGenerator[str, None]:
        """Stream chat completion from Ollama"""
        
        ollama_messages = [
            {"role": msg.role, "content": msg.content}
            for msg in messages
        ]
        
        payload = {
            "model": model_config.model_name,
            "messages": ollama_messages,
            "stream": True,
            "options": self._build_options(model_config)
        }
        
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=self.timeout)) as session:
            async with session.post(
                f"{self.base_url}/api/chat",
                json=payload
            ) as response:
                if response.status != 200:
                    raise Exception(f"Ollama API error: {response.status}")
                
                async for line in response.content:
                    if line:
                        try:
                            chunk = json.loads(line.decode())
                            if "message" in chunk and "content" in chunk["message"]:
                                yield chunk["message"]["content"]
                        except json.JSONDecodeError:
                            continue
    
    def list_models(self) -> List[str]:
        """List available Ollama models"""
        import requests
        
        try:
            response = requests.get(f"{self.base_url}/api/tags", timeout=10)
            if response.status_code == 200:
                models = response.json()
                return [model["name"] for model in models.get("models", [])]
        except requests.RequestException:
            pass
        
        return []
    
    def validate_config(self) -> bool:
        """Validate Ollama configuration by testing connection"""
        import requests
        
        try:
            response = requests.get(f"{self.base_url}/api/tags", timeout=5)
            return response.status_code == 200
        except requests.RequestException:
            return False
    
    def _build_options(self, model_config: ModelConfig) -> Dict[str, Any]:
        """Build Ollama-specific options from model config"""
        options = {}
        
        if model_config.temperature is not None:
            options["temperature"] = model_config.temperature
        
        if model_config.top_p is not None:
            options["top_p"] = model_config.top_p
        
        if model_config.max_tokens is not None:
            options["num_predict"] = model_config.max_tokens
        
        if model_config.stop_sequences:
            options["stop"] = model_config.stop_sequences
        
        return options
    
    def get_model_capabilities(self, model_name: str) -> Dict[str, Any]:
        """Get Ollama model capabilities"""
        # Common Ollama model patterns
        capabilities = {
            "max_context": 4096,
            "supports_tools": False,
            "supports_vision": False,
            "reasoning_level": "medium"
        }
        
        # Adjust based on model name patterns
        if "coder" in model_name.lower():
            capabilities["reasoning_level"] = "high"
            capabilities["max_context"] = 8192
        
        if "llama3" in model_name.lower() or "qwen" in model_name.lower():
            capabilities["max_context"] = 8192
            
        if any(size in model_name.lower() for size in ["70b", "72b"]):
            capabilities["reasoning_level"] = "very_high"
            capabilities["max_context"] = 32768
        
        return capabilities
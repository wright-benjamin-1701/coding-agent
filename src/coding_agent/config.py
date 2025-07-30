"""Configuration management for the coding agent."""

import os
import json
from pathlib import Path
from typing import Dict, Any, Optional
from pydantic import BaseModel


class ModelConfig(BaseModel):
    """Model configuration settings."""
    provider: str = "ollama"
    model: str = "llama2"
    base_url: str = "http://localhost:11434"
    temperature: float = 0.7
    max_tokens: Optional[int] = None


class DatabaseConfig(BaseModel):
    """Database configuration settings."""
    db_path: str = ".coding_agent.db"
    max_summaries: int = 10
    cache_enabled: bool = True


class IndexerConfig(BaseModel):
    """File indexer configuration settings."""
    index_file: str = ".coding_agent_index.json"
    ignore_patterns: list = [".git", "__pycache__", "node_modules", ".env", "*.pyc"]
    watch_enabled: bool = True


class ExecutionConfig(BaseModel):
    """Execution behavior configuration settings."""
    auto_continue: bool = False
    show_tool_output: list = []


class AgentConfig(BaseModel):
    """Complete agent configuration."""
    model: ModelConfig = ModelConfig()
    database: DatabaseConfig = DatabaseConfig()
    indexer: IndexerConfig = IndexerConfig()
    execution: ExecutionConfig = ExecutionConfig()
    debug: bool = False


class ConfigManager:
    """Manages configuration loading and saving."""
    
    def __init__(self, config_path: str = None):
        self.config_path = Path(config_path or self._get_default_config_path())
        self._config = None
    
    def _get_default_config_path(self) -> str:
        """Get default configuration file path."""
        # Try local config files first
        local_configs = [
            Path("config.json"),
            Path(".coding_agent_config.json")
        ]
        
        for local_config in local_configs:
            if local_config.exists():
                return str(local_config)
        
        # User config directory
        config_dir = Path.home() / ".config" / "coding-agent"
        config_dir.mkdir(parents=True, exist_ok=True)
        return str(config_dir / "config.json")
    
    def load_config(self) -> AgentConfig:
        """Load configuration from file and environment variables."""
        if self._config is not None:
            return self._config
        
        # Start with defaults
        config_data = {}
        
        # Load from file if exists
        if self.config_path.exists():
            try:
                with open(self.config_path, 'r') as f:
                    config_data = json.load(f)
            except Exception as e:
                print(f"Warning: Could not load config file: {e}")
        
        # Override with environment variables
        config_data = self._apply_env_overrides(config_data)
        
        # Create config object
        self._config = AgentConfig(**config_data)
        return self._config
    
    def _apply_env_overrides(self, config_data: Dict[str, Any]) -> Dict[str, Any]:
        """Apply environment variable overrides."""
        env_mappings = {
            # Model settings
            "CODING_AGENT_PROVIDER": ["model", "provider"],
            "CODING_AGENT_MODEL": ["model", "model"],
            "CODING_AGENT_BASE_URL": ["model", "base_url"],
            "CODING_AGENT_TEMPERATURE": ["model", "temperature"],
            "CODING_AGENT_MAX_TOKENS": ["model", "max_tokens"],
            
            # Database settings
            "CODING_AGENT_DB_PATH": ["database", "db_path"],
            "CODING_AGENT_MAX_SUMMARIES": ["database", "max_summaries"],
            "CODING_AGENT_CACHE_ENABLED": ["database", "cache_enabled"],
            
            # Indexer settings
            "CODING_AGENT_INDEX_FILE": ["indexer", "index_file"],
            "CODING_AGENT_WATCH_ENABLED": ["indexer", "watch_enabled"],
            
            # Execution settings
            "CODING_AGENT_AUTO_CONTINUE": ["execution", "auto_continue"],
            
            # General settings
            "CODING_AGENT_DEBUG": ["debug"]
        }
        
        for env_var, path in env_mappings.items():
            value = os.getenv(env_var)
            if value is not None:
                # Convert value to appropriate type
                if path[-1] in ["temperature"]:
                    value = float(value)
                elif path[-1] in ["max_tokens", "max_summaries"]:
                    value = int(value) if value else None
                elif path[-1] in ["cache_enabled", "watch_enabled", "debug", "auto_continue"]:
                    value = value.lower() in ["true", "1", "yes", "on"]
                
                # Set nested value
                current = config_data
                for key in path[:-1]:
                    if key not in current:
                        current[key] = {}
                    current = current[key]
                current[path[-1]] = value
        
        return config_data
    
    def save_config(self, config: AgentConfig):
        """Save configuration to file."""
        try:
            # Ensure directory exists
            self.config_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Save to file
            with open(self.config_path, 'w') as f:
                json.dump(config.dict(), f, indent=2)
            
            self._config = config
            
        except Exception as e:
            print(f"Warning: Could not save config file: {e}")
    
    def create_default_config(self):
        """Create a default configuration file."""
        config = AgentConfig()
        self.save_config(config)
        return config
    
    def get_config_info(self) -> Dict[str, Any]:
        """Get information about current configuration."""
        config = self.load_config()
        return {
            "config_path": str(self.config_path),
            "config_exists": self.config_path.exists(),
            "provider": config.model.provider,
            "model": config.model.model,
            "base_url": config.model.base_url,
            "debug": config.debug
        }
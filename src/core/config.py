"""
Configuration management for the coding agent
"""
import os
import yaml
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field


@dataclass
class OllamaConfig:
    base_url: str = "http://localhost:11434"
    timeout: int = 300
    max_retries: int = 3


@dataclass
class ModelConfig:
    high_reasoning: List[str] = field(default_factory=lambda: [
        "qwen2.5-coder:32b", "deepseek-coder:33b", "qwen2.5-coder:14b", "qwen2.5-coder:7b"
    ])
    fast_completion: List[str] = field(default_factory=lambda: [
        "qwen2.5-coder:7b", "qwen2.5-coder:1.5b", "phi3:mini"
    ])
    analysis: List[str] = field(default_factory=lambda: [
        "qwen2.5-coder:14b", "qwen2.5-coder:7b"
    ])
    chat: List[str] = field(default_factory=lambda: [
        "qwen2.5-coder:7b", "llama3.1:8b"
    ])


@dataclass
class SafetyConfig:
    max_file_size_mb: int = 10
    restricted_paths: List[str] = field(default_factory=lambda: [
        "/etc", "/sys", "/proc", "/root", "~/.ssh", "~/.aws"
    ])
    dangerous_commands: List[str] = field(default_factory=lambda: [
        "rm -rf", "sudo", "format", "del /f", "shutdown", "reboot"
    ])
    sensitive_extensions: List[str] = field(default_factory=lambda: [
        ".key", ".pem", ".p12", ".env", ".secret"
    ])
    enable_path_validation: bool = True
    enable_command_validation: bool = True
    enable_content_scanning: bool = True


@dataclass
class AgentConfig:
    max_iterations: int = 10
    context_window: int = 8192
    memory_limit_mb: int = 500
    auto_save_session: bool = True
    session_dir: str = "sessions"
    enable_learning: bool = True
    learning_dir: str = "memory"


@dataclass
class ToolConfig:
    enabled: bool = True
    settings: Dict[str, Any] = field(default_factory=dict)


@dataclass
class LoggingConfig:
    level: str = "INFO"
    file: str = "logs/agent.log"
    max_size_mb: int = 100
    backup_count: int = 5
    format: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"


@dataclass
class PerformanceConfig:
    parallel_execution: bool = True
    enable_file_cache: bool = True
    cache_size_mb: int = 100
    switch_to_fast_model_after_seconds: int = 30
    switch_to_high_reasoning_for_complex_tasks: bool = True


@dataclass
class Config:
    """Main configuration class"""
    ollama: OllamaConfig = field(default_factory=OllamaConfig)
    models: ModelConfig = field(default_factory=ModelConfig)
    safety: SafetyConfig = field(default_factory=SafetyConfig)
    agent: AgentConfig = field(default_factory=AgentConfig)
    tools: Dict[str, ToolConfig] = field(default_factory=dict)
    logging: LoggingConfig = field(default_factory=LoggingConfig)
    performance: PerformanceConfig = field(default_factory=PerformanceConfig)


class ConfigManager:
    """Configuration file manager"""
    
    def __init__(self, config_path: Optional[str] = None):
        self.config_path = Path(config_path) if config_path else Path("config.yaml")
        self.config: Config = self._load_config()
    
    def _load_config(self) -> Config:
        """Load configuration from file or create default"""
        
        # Try to load from file
        if self.config_path.exists():
            try:
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    config_data = yaml.safe_load(f)
                return self._create_config_from_dict(config_data)
            except Exception as e:
                print(f"Warning: Could not load config file {self.config_path}: {e}")
                print("Using default configuration")
        
        # Create default config
        config = Config()
        
        # Override with environment variables if present
        config = self._apply_env_overrides(config)
        
        return config
    
    def _create_config_from_dict(self, data: Dict[str, Any]) -> Config:
        """Create Config object from dictionary"""
        
        config = Config()
        
        # Ollama config
        if 'ollama' in data:
            ollama_data = data['ollama']
            config.ollama = OllamaConfig(
                base_url=ollama_data.get('base_url', config.ollama.base_url),
                timeout=ollama_data.get('timeout', config.ollama.timeout),
                max_retries=ollama_data.get('max_retries', config.ollama.max_retries)
            )
        
        # Models config
        if 'models' in data:
            models_data = data['models']
            config.models = ModelConfig(
                high_reasoning=models_data.get('high_reasoning', config.models.high_reasoning),
                fast_completion=models_data.get('fast_completion', config.models.fast_completion),
                analysis=models_data.get('analysis', config.models.analysis),
                chat=models_data.get('chat', config.models.chat)
            )
        
        # Safety config
        if 'safety' in data:
            safety_data = data['safety']
            config.safety = SafetyConfig(
                max_file_size_mb=safety_data.get('max_file_size_mb', config.safety.max_file_size_mb),
                restricted_paths=safety_data.get('restricted_paths', config.safety.restricted_paths),
                dangerous_commands=safety_data.get('dangerous_commands', config.safety.dangerous_commands),
                sensitive_extensions=safety_data.get('sensitive_extensions', config.safety.sensitive_extensions),
                enable_path_validation=safety_data.get('enable_path_validation', config.safety.enable_path_validation),
                enable_command_validation=safety_data.get('enable_command_validation', config.safety.enable_command_validation),
                enable_content_scanning=safety_data.get('enable_content_scanning', config.safety.enable_content_scanning)
            )
        
        # Agent config
        if 'agent' in data:
            agent_data = data['agent']
            config.agent = AgentConfig(
                max_iterations=agent_data.get('max_iterations', config.agent.max_iterations),
                context_window=agent_data.get('context_window', config.agent.context_window),
                memory_limit_mb=agent_data.get('memory_limit_mb', config.agent.memory_limit_mb),
                auto_save_session=agent_data.get('auto_save_session', config.agent.auto_save_session),
                session_dir=agent_data.get('session_dir', config.agent.session_dir),
                enable_learning=agent_data.get('enable_learning', config.agent.enable_learning),
                learning_dir=agent_data.get('learning_dir', config.agent.learning_dir)
            )
        
        # Tools config
        if 'tools' in data:
            for tool_name, tool_data in data['tools'].items():
                config.tools[tool_name] = ToolConfig(
                    enabled=tool_data.get('enabled', True),
                    settings=tool_data
                )
        
        # Logging config
        if 'logging' in data:
            logging_data = data['logging']
            config.logging = LoggingConfig(
                level=logging_data.get('level', config.logging.level),
                file=logging_data.get('file', config.logging.file),
                max_size_mb=logging_data.get('max_size_mb', config.logging.max_size_mb),
                backup_count=logging_data.get('backup_count', config.logging.backup_count),
                format=logging_data.get('format', config.logging.format)
            )
        
        # Performance config
        if 'performance' in data:
            perf_data = data['performance']
            config.performance = PerformanceConfig(
                parallel_execution=perf_data.get('parallel_execution', config.performance.parallel_execution),
                enable_file_cache=perf_data.get('enable_file_cache', config.performance.enable_file_cache),
                cache_size_mb=perf_data.get('cache_size_mb', config.performance.cache_size_mb),
                switch_to_fast_model_after_seconds=perf_data.get('switch_to_fast_model_after_seconds', config.performance.switch_to_fast_model_after_seconds),
                switch_to_high_reasoning_for_complex_tasks=perf_data.get('switch_to_high_reasoning_for_complex_tasks', config.performance.switch_to_high_reasoning_for_complex_tasks)
            )
        
        return config
    
    def _apply_env_overrides(self, config: Config) -> Config:
        """Apply environment variable overrides"""
        
        # Ollama URL override
        if 'OLLAMA_URL' in os.environ:
            config.ollama.base_url = os.environ['OLLAMA_URL']
        
        # Logging level override  
        if 'LOG_LEVEL' in os.environ:
            config.logging.level = os.environ['LOG_LEVEL']
        
        return config
    
    def get_model_for_task(self, task_type: str, available_models: List[str]) -> Optional[str]:
        """Select best available model for task type"""
        
        # Get preferred models for task type
        if task_type == "high_reasoning":
            preferred = self.config.models.high_reasoning
        elif task_type == "fast_completion":
            preferred = self.config.models.fast_completion
        elif task_type == "analysis":
            preferred = self.config.models.analysis
        elif task_type == "chat":
            preferred = self.config.models.chat
        else:
            # Default to analysis models
            preferred = self.config.models.analysis
        
        # Find first available model from preferences
        for model in preferred:
            if model in available_models:
                return model
        
        # Fallback to any available model
        if available_models:
            return available_models[0]
        
        return None
    
    def is_path_safe(self, path: str) -> bool:
        """Check if path is safe to access"""
        
        if not self.config.safety.enable_path_validation:
            return True
        
        # Expand user home directory
        expanded_path = os.path.expanduser(path)
        
        # Check against restricted paths
        for restricted in self.config.safety.restricted_paths:
            expanded_restricted = os.path.expanduser(restricted)
            if expanded_path.startswith(expanded_restricted):
                return False
        
        return True
    
    def is_command_safe(self, command: str) -> bool:
        """Check if command is safe to execute"""
        
        if not self.config.safety.enable_command_validation:
            return True
        
        # Check against dangerous commands
        for dangerous in self.config.safety.dangerous_commands:
            if dangerous.lower() in command.lower():
                return False
        
        return True
    
    def is_file_extension_sensitive(self, filename: str) -> bool:
        """Check if file extension is sensitive"""
        
        if not self.config.safety.enable_content_scanning:
            return False
        
        file_path = Path(filename)
        extension = file_path.suffix.lower()
        
        return extension in self.config.safety.sensitive_extensions
    
    def get_tool_config(self, tool_name: str) -> Optional[ToolConfig]:
        """Get configuration for specific tool"""
        return self.config.tools.get(tool_name)
    
    def is_tool_enabled(self, tool_name: str) -> bool:
        """Check if tool is enabled"""
        tool_config = self.get_tool_config(tool_name)
        return tool_config.enabled if tool_config else True
    
    def save_config(self) -> None:
        """Save current configuration to file"""
        
        # Convert config to dictionary
        config_dict = {
            'ollama': {
                'base_url': self.config.ollama.base_url,
                'timeout': self.config.ollama.timeout,
                'max_retries': self.config.ollama.max_retries
            },
            'models': {
                'high_reasoning': self.config.models.high_reasoning,
                'fast_completion': self.config.models.fast_completion,
                'analysis': self.config.models.analysis,
                'chat': self.config.models.chat
            },
            'safety': {
                'max_file_size_mb': self.config.safety.max_file_size_mb,
                'restricted_paths': self.config.safety.restricted_paths,
                'dangerous_commands': self.config.safety.dangerous_commands,
                'sensitive_extensions': self.config.safety.sensitive_extensions,
                'enable_path_validation': self.config.safety.enable_path_validation,
                'enable_command_validation': self.config.safety.enable_command_validation,
                'enable_content_scanning': self.config.safety.enable_content_scanning
            },
            'agent': {
                'max_iterations': self.config.agent.max_iterations,
                'context_window': self.config.agent.context_window,
                'memory_limit_mb': self.config.agent.memory_limit_mb,
                'auto_save_session': self.config.agent.auto_save_session,
                'session_dir': self.config.agent.session_dir,
                'enable_learning': self.config.agent.enable_learning,
                'learning_dir': self.config.agent.learning_dir
            },
            'logging': {
                'level': self.config.logging.level,
                'file': self.config.logging.file,
                'max_size_mb': self.config.logging.max_size_mb,
                'backup_count': self.config.logging.backup_count,
                'format': self.config.logging.format
            },
            'performance': {
                'parallel_execution': self.config.performance.parallel_execution,
                'enable_file_cache': self.config.performance.enable_file_cache,
                'cache_size_mb': self.config.performance.cache_size_mb,
                'switch_to_fast_model_after_seconds': self.config.performance.switch_to_fast_model_after_seconds,
                'switch_to_high_reasoning_for_complex_tasks': self.config.performance.switch_to_high_reasoning_for_complex_tasks
            }
        }
        
        # Add tools config
        if self.config.tools:
            config_dict['tools'] = {}
            for tool_name, tool_config in self.config.tools.items():
                config_dict['tools'][tool_name] = {
                    'enabled': tool_config.enabled,
                    **tool_config.settings
                }
        
        # Write to file
        try:
            # Create directory if it doesn't exist
            self.config_path.parent.mkdir(parents=True, exist_ok=True)
            
            with open(self.config_path, 'w', encoding='utf-8') as f:
                yaml.dump(config_dict, f, default_flow_style=False, sort_keys=False)
        except Exception as e:
            print(f"Warning: Could not save config file: {e}")


# Global config manager instance
_config_manager: Optional[ConfigManager] = None


def get_config() -> ConfigManager:
    """Get global configuration manager instance"""
    global _config_manager
    if _config_manager is None:
        _config_manager = ConfigManager()
    return _config_manager


def init_config(config_path: Optional[str] = None) -> ConfigManager:
    """Initialize configuration manager with custom path"""
    global _config_manager
    _config_manager = ConfigManager(config_path)
    return _config_manager
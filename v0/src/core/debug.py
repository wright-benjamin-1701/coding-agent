"""
Debug utilities for the coding agent
"""
import os
from typing import Optional
from .config import get_config

_debug_enabled: Optional[bool] = None

def is_debug_enabled() -> bool:
    """Check if debug mode is enabled"""
    global _debug_enabled
    
    if _debug_enabled is None:
        # First check environment variable for immediate override
        if 'DEBUG_MODE' in os.environ:
            _debug_enabled = os.environ['DEBUG_MODE'].lower() in ('true', '1', 'yes', 'on')
        else:
            # Check configuration
            try:
                config = get_config()
                _debug_enabled = config.config.agent.debug_mode
            except:
                # Fallback to False if config not available
                _debug_enabled = False
    
    return _debug_enabled

def debug_print(message: str, prefix: str = "🔍 DEBUG") -> None:
    """Print debug message if debug mode is enabled"""
    if is_debug_enabled():
        print(f"{prefix}: {message}")

def reset_debug_cache() -> None:
    """Reset the debug mode cache (useful for testing)"""
    global _debug_enabled
    _debug_enabled = None

def set_debug_mode(enabled: bool) -> None:
    """Manually set debug mode (useful for testing)"""
    global _debug_enabled
    _debug_enabled = enabled
"""Tools for managing permanent directives that are injected into all prompts."""

from typing import Dict, Any
from .base import Tool
from ..types import ToolResult
from ..config import ConfigManager


class DirectiveManagementTool(Tool):
    """Tool for managing permanent directives that are automatically injected into all plan generation prompts."""
    
    def __init__(self, config_manager: ConfigManager = None):
        self.config_manager = config_manager
    
    @property
    def name(self) -> str:
        return "manage_directives"
    
    @property
    def description(self) -> str:
        return "Add, remove, or list permanent directives that are automatically injected into all plan generation prompts"
    
    @property
    def parameters_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["add", "remove", "list", "clear"],
                    "description": "Action to perform: add directive, remove directive, list all directives, or clear all directives"
                },
                "directive": {
                    "type": "string",
                    "description": "The directive text to add or remove (required for add/remove actions)"
                },
                "index": {
                    "type": "integer",
                    "description": "Index of directive to remove (alternative to directive text for remove action)"
                }
            },
            "required": ["action"]
        }
    
    @property
    def is_destructive(self) -> bool:
        return True  # Modifying directives affects all future behavior
    
    def execute(self, **parameters) -> ToolResult:
        """Execute directive management action."""
        action = parameters.get("action")
        directive = parameters.get("directive")
        index = parameters.get("index")
        
        if not self.config_manager:
            return ToolResult(
                success=False, 
                output=None, 
                error="Configuration manager not available"
            )
        
        try:
            # Load current config
            config = self.config_manager.load_config()
            directives = config.directives.permanent_directives
            
            if action == "list":
                return self._list_directives(directives)
            elif action == "add":
                return self._add_directive(config, directives, directive)
            elif action == "remove":
                return self._remove_directive(config, directives, directive, index)
            elif action == "clear":
                return self._clear_directives(config)
            else:
                return ToolResult(
                    success=False,
                    output=None,
                    error=f"Unknown action: {action}"
                )
                
        except Exception as e:
            return ToolResult(
                success=False,
                output=None,
                error=f"Error managing directives: {str(e)}"
            )
    
    def _list_directives(self, directives):
        """List all current directives."""
        if not directives:
            return ToolResult(
                success=True,
                output="No permanent directives configured.",
                action_description="Listed permanent directives (none found)"
            )
        
        output = f"Current permanent directives ({len(directives)}):\n"
        for i, directive in enumerate(directives, 1):
            output += f"{i}. {directive}\n"
        
        return ToolResult(
            success=True,
            output=output.strip(),
            action_description=f"Listed {len(directives)} permanent directives"
        )
    
    def _add_directive(self, config, directives, directive):
        """Add a new directive."""
        if not directive:
            return ToolResult(
                success=False,
                output=None,
                error="Directive text is required for add action"
            )
        
        if directive in directives:
            return ToolResult(
                success=False,
                output=None,
                error=f"Directive already exists: {directive}"
            )
        
        # Add directive and save config
        config.directives.permanent_directives.append(directive)
        self.config_manager.save_config(config)
        
        return ToolResult(
            success=True,
            output=f"Added directive: {directive}",
            action_description="Added permanent directive"
        )
    
    def _remove_directive(self, config, directives, directive, index):
        """Remove a directive by text or index."""
        if not directives:
            return ToolResult(
                success=False,
                output=None,
                error="No directives to remove"
            )
        
        if index is not None:
            # Remove by index
            if 1 <= index <= len(directives):
                removed_directive = directives.pop(index - 1)
                self.config_manager.save_config(config)
                return ToolResult(
                    success=True,
                    output=f"Removed directive {index}: {removed_directive}",
                    action_description="Removed permanent directive by index"
                )
            else:
                return ToolResult(
                    success=False,
                    output=None,
                    error=f"Invalid index: {index}. Valid range is 1-{len(directives)}"
                )
        
        elif directive:
            # Remove by text
            if directive in directives:
                directives.remove(directive)
                self.config_manager.save_config(config)
                return ToolResult(
                    success=True,
                    output=f"Removed directive: {directive}",
                    action_description="Removed permanent directive by text"
                )
            else:
                return ToolResult(
                    success=False,
                    output=None,
                    error=f"Directive not found: {directive}"
                )
        
        else:
            return ToolResult(
                success=False,
                output=None,
                error="Either directive text or index is required for remove action"
            )
    
    def _clear_directives(self, config):
        """Clear all directives."""
        count = len(config.directives.permanent_directives)
        config.directives.permanent_directives.clear()
        self.config_manager.save_config(config)
        
        return ToolResult(
            success=True,
            output=f"Cleared {count} permanent directives",
            action_description="Cleared all permanent directives"
        )
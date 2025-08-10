"""Tool for managing prompt enhancement settings."""

from typing import Dict, Any
from .base import Tool, ToolResult


class PromptEnhancementTool(Tool):
    """Tool for configuring prompt enhancement features."""
    
    def __init__(self, config_manager):
        self.config_manager = config_manager
    
    @property
    def name(self) -> str:
        return "manage_prompt_enhancement"
    
    @property
    def description(self) -> str:
        return "Configure prompt enhancement settings for business context and extensibility"
    
    @property
    def is_destructive(self) -> bool:
        return False
    
    @property
    def parameters_schema(self) -> Dict[str, Any]:
        return self.get_schema()
    
    def get_schema(self) -> Dict[str, Any]:
        """Get the tool schema for LLM."""
        return {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["show", "enable", "disable", "configure"],
                    "description": "Action to perform: show current settings, enable/disable enhancement, or configure specific features"
                },
                "business_context": {
                    "type": "boolean",
                    "description": "Enable/disable business context enhancements (only for 'configure' action)"
                },
                "extensibility_context": {
                    "type": "boolean", 
                    "description": "Enable/disable extensibility context enhancements (only for 'configure' action)"
                },
                "show_enhancements": {
                    "type": "boolean",
                    "description": "Show enhancement summaries when prompts are enhanced (only for 'configure' action)"
                }
            },
            "required": ["action"]
        }
    
    def execute(self, action: str, business_context: bool = None, 
                extensibility_context: bool = None, show_enhancements: bool = None) -> ToolResult:
        """Execute prompt enhancement management."""
        try:
            config = self.config_manager.load_config()
            
            if action == "show":
                return self._show_settings(config)
            elif action == "enable":
                return self._enable_enhancement(config)
            elif action == "disable":
                return self._disable_enhancement(config)
            elif action == "configure":
                return self._configure_enhancement(config, business_context, 
                                                 extensibility_context, show_enhancements)
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
                error=f"Error managing prompt enhancement: {str(e)}"
            )
    
    def _show_settings(self, config) -> ToolResult:
        """Show current prompt enhancement settings."""
        settings = config.prompt_enhancement
        
        output = f"""Current Prompt Enhancement Settings:
        
🔧 Overall Enhancement: {'Enabled' if settings.enabled else 'Disabled'}
🏢 Business Context: {'Enabled' if settings.business_context else 'Disabled'}
🔌 Extensibility Context: {'Enabled' if settings.extensibility_context else 'Disabled'}  
👁️ Show Enhancement Summaries: {'Enabled' if settings.show_enhancements else 'Disabled'}

When enabled, the system automatically enhances user prompts with:
- Business requirements and stakeholder considerations
- Extensibility patterns and architectural guidance
- Industry best practices for maintainable code"""
        
        return ToolResult(success=True, output=output)
    
    def _enable_enhancement(self, config) -> ToolResult:
        """Enable prompt enhancement."""
        config.prompt_enhancement.enabled = True
        self.config_manager.save_config(config)
        
        return ToolResult(
            success=True, 
            output="✅ Prompt enhancement enabled! The system will now automatically enhance prompts with business context and extensibility guidance."
        )
    
    def _disable_enhancement(self, config) -> ToolResult:
        """Disable prompt enhancement."""
        config.prompt_enhancement.enabled = False
        self.config_manager.save_config(config)
        
        return ToolResult(
            success=True,
            output="🔧 Prompt enhancement disabled. Prompts will be used as-is without additional context."
        )
    
    def _configure_enhancement(self, config, business_context, extensibility_context, show_enhancements) -> ToolResult:
        """Configure specific enhancement features."""
        changes = []
        
        if business_context is not None:
            config.prompt_enhancement.business_context = business_context
            changes.append(f"Business context: {'enabled' if business_context else 'disabled'}")
        
        if extensibility_context is not None:
            config.prompt_enhancement.extensibility_context = extensibility_context
            changes.append(f"Extensibility context: {'enabled' if extensibility_context else 'disabled'}")
        
        if show_enhancements is not None:
            config.prompt_enhancement.show_enhancements = show_enhancements
            changes.append(f"Enhancement summaries: {'enabled' if show_enhancements else 'disabled'}")
        
        if not changes:
            return ToolResult(
                success=False,
                output=None,
                error="No configuration changes specified. Use business_context, extensibility_context, or show_enhancements parameters."
            )
        
        self.config_manager.save_config(config)
        
        return ToolResult(
            success=True,
            output=f"✅ Prompt enhancement configured successfully:\n" + "\n".join(f"  • {change}" for change in changes)
        )
"""Prompt management with context injection."""

from typing import List, Dict, Any
from .types import Context


class PromptManager:
    """Manages prompt templates and context injection."""
    
    def __init__(self):
        self.system_template = self._load_system_template()
    
    def _load_system_template(self) -> str:
        """Load the single system prompt template."""
        return """You are a coding assistant that generates execution plans.

Available tools:
{tools}

Recent context:
{context}

User request: {user_prompt}

Generate a JSON plan with actions to complete this request. Return a JSON object with an "actions" array.

Example format:
{
  "actions": [
    {"type": "tool_use", "tool_name": "git_status", "parameters": {}},
    {"type": "confirmation", "message": "Continue?", "destructive": false}
  ]
}

Return ONLY the JSON object, no other text or thinking."""
    
    def build_prompt(self, context: Context, available_tools: Dict[str, Any]) -> str:
        """Build the complete prompt with context injection."""
        tools_description = self._format_tools(available_tools)
        context_description = self._format_context(context)
        
        # Use string replacement instead of .format() to avoid issues with braces in tool descriptions
        result = self.system_template
        result = result.replace("{tools}", tools_description)
        result = result.replace("{context}", context_description) 
        result = result.replace("{user_prompt}", context.user_prompt)
        return result
    
    def _format_tools(self, tools: Dict[str, Any]) -> str:
        """Format available tools for the prompt."""
        formatted = []
        for name, schema in tools.items():
            formatted.append(f"- {name}: {schema.get('description', 'No description')}")
        return "\n".join(formatted)
    
    def _format_context(self, context: Context) -> str:
        """Format context information for the prompt."""
        parts = []
        
        if context.recent_summaries:
            parts.append("Recent actions:")
            for summary in context.recent_summaries[-5:]:  # Last 5 summaries
                parts.append(f"- {summary}")
        
        if context.modified_files:
            parts.append(f"Modified files: {', '.join(context.modified_files)}")
        
        parts.append(f"Current commit: {context.current_commit}")
        
        return "\n".join(parts)
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

If previous actions have been executed, use their results to decide what to do next. You can generate follow-up actions based on the outputs from previous steps. 

Consider whether this step should be final - if the task appears complete or nearly complete, focus on verification and cleanup actions rather than new exploration.

IMPORTANT GUIDELINES:
- Only use confirmation actions for destructive operations (file writes, deletions, git commits)
- For read-only operations (searches, file reads, git status), do NOT add confirmations
- Simple information requests should complete without user intervention
- If the user asked a question and you found the answer, the task is complete

Example formats:
// For simple read-only tasks (NO confirmation needed):
{"actions": [{"type": "tool_use", "tool_name": "search_files", "parameters": {"pattern": "class", "path": "src"}}]}

// For destructive operations (confirmation needed):
{"actions": [
  {"type": "tool_use", "tool_name": "write_file", "parameters": {"file_path": "test.py", "content": "print('hello')"}},
  {"type": "confirmation", "message": "Write new file test.py?", "destructive": true}
]}

Return ONLY the JSON object, no other text or thinking."""
    
    def build_prompt(self, context: Context, available_tools: Dict[str, Any], previous_results: List = None) -> str:
        """Build the complete prompt with context injection."""
        tools_description = self._format_tools(available_tools)
        context_description = self._format_context(context, previous_results)
        
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
    
    def _format_context(self, context: Context, previous_results: List = None) -> str:
        """Format context information for the prompt."""
        parts = []
        
        # Add previous results from current session if available
        if previous_results:
            parts.append(f"Previous actions executed in this session ({len(previous_results)} actions):")
            
            # Show recent results in detail, summarize older ones
            recent_results = previous_results[-4:] if len(previous_results) > 4 else previous_results
            if len(previous_results) > 4:
                older_count = len(previous_results) - 4
                successful_older = sum(1 for r in previous_results[:-4] if hasattr(r, 'success') and r.success)
                parts.append(f"- (Earlier: {successful_older}/{older_count} actions succeeded)")
            
            for i, result in enumerate(recent_results, len(previous_results) - len(recent_results) + 1):
                action_desc = getattr(result, 'action_description', f'Action {i}')
                if hasattr(result, 'success') and result.success:
                    status = "✅"
                    output = str(result.output)[:200] + "..." if result.output and len(str(result.output)) > 200 else result.output or "No output"
                    parts.append(f"- {status} {action_desc}: {output}")
                else:
                    status = "❌" 
                    error = getattr(result, 'error', 'Unknown error')
                    parts.append(f"- {status} {action_desc}: {error}")
            parts.append("")  # Add blank line
        
        if context.recent_summaries:
            parts.append("Recent actions from previous sessions:")
            for summary in context.recent_summaries[-5:]:  # Last 5 summaries
                parts.append(f"- {summary}")
        
        if context.modified_files:
            parts.append(f"Modified files: {', '.join(context.modified_files)}")
        
        parts.append(f"Current commit: {context.current_commit}")
        
        return "\n".join(parts)
"""Plan orchestrator for generating execution plans."""

import json
import re
from typing import Dict, Any, List, Union
from .types import Plan, ToolAction, ConfirmationAction, Context
from .providers.base import ModelProvider
from .prompt_manager import PromptManager
from .tools.registry import ToolRegistry


class PlanOrchestrator:
    """Orchestrates plan generation with hybrid hardcoded + LLM approach."""
    
    def __init__(self, model_provider: ModelProvider, prompt_manager: PromptManager, 
                 tool_registry: ToolRegistry):
        self.model_provider = model_provider
        self.prompt_manager = prompt_manager
        self.tool_registry = tool_registry
    
    def generate_plan(self, context: Context) -> Plan:
        """Generate an execution plan for the user request."""
        # Step 1: Apply hardcoded pre-actions
        pre_actions = self._get_pre_actions(context)
        
        # Step 2: Generate LLM plan
        llm_actions = self._generate_llm_plan(context)
        
        # Step 3: Combine and return
        all_actions = pre_actions + llm_actions
        return Plan(actions=all_actions)
    
    def _get_pre_actions(self, context: Context) -> List[Union[ToolAction, ConfirmationAction]]:
        """Get hardcoded pre-actions based on context analysis."""
        pre_actions = []
        
        # If request mentions searching, add search brainstorming
        if any(keyword in context.user_prompt.lower() 
               for keyword in ['find', 'search', 'look for', 'locate']):
            pre_actions.append(ToolAction(
                tool_name="brainstorm_search_terms",
                parameters={"query": context.user_prompt}
            ))
        
        # If request mentions files not in modified_files, scan them first
        file_mentions = re.findall(r'[a-zA-Z0-9_./]+\.[a-zA-Z]+', context.user_prompt)
        for file_path in file_mentions:
            if file_path not in context.modified_files:
                pre_actions.append(ToolAction(
                    tool_name="read_file",
                    parameters={"file_path": file_path}
                ))
        
        return pre_actions
    
    def _generate_llm_plan(self, context: Context) -> List[Union[ToolAction, ConfirmationAction]]:
        """Generate plan using LLM."""
        prompt = self.prompt_manager.build_prompt(
            context, 
            self.tool_registry.get_schemas()
        )
        
        response = self.model_provider.generate(prompt)
        
        # Parse JSON from response
        plan_json = self._extract_json(response.content)
        if not plan_json:
            return []
        
        return self._parse_actions(plan_json.get("actions", []))
    
    def _extract_json(self, text: str) -> Dict[str, Any]:
        """Extract the largest JSON object from model response."""
        # Find all potential JSON objects
        json_matches = []
        
        # Look for objects starting with { and ending with }
        brace_count = 0
        start_pos = None
        
        for i, char in enumerate(text):
            if char == '{':
                if brace_count == 0:
                    start_pos = i
                brace_count += 1
            elif char == '}':
                brace_count -= 1
                if brace_count == 0 and start_pos is not None:
                    json_str = text[start_pos:i+1]
                    try:
                        json_obj = json.loads(json_str)
                        json_matches.append((len(json_str), json_obj))
                    except json.JSONDecodeError:
                        pass
        
        # Return the largest valid JSON object
        if json_matches:
            return max(json_matches, key=lambda x: x[0])[1]
        
        return {}
    
    def _parse_actions(self, actions_data: List[Dict[str, Any]]) -> List[Union[ToolAction, ConfirmationAction]]:
        """Parse actions from JSON data."""
        actions = []
        
        for action_data in actions_data:
            action_type = action_data.get("type")
            
            if action_type == "tool_use":
                actions.append(ToolAction(
                    tool_name=action_data.get("tool_name", ""),
                    parameters=action_data.get("parameters", {})
                ))
            elif action_type == "confirmation":
                actions.append(ConfirmationAction(
                    message=action_data.get("message", ""),
                    destructive=action_data.get("destructive", True)
                ))
        
        return actions
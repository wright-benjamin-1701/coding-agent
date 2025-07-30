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
        # Check if model provider is available first
        if not self.model_provider.is_available():
            print("⚠️  Model provider not available")
            return []
        
        prompt = self.prompt_manager.build_prompt(
            context, 
            self.tool_registry.get_schemas()
        )
        
        response = self.model_provider.generate(prompt)
        
        # Check if there was an error in the response
        if response.metadata and "error" in response.metadata:
            print(f"⚠️  Model error: {response.metadata['error']}")
            return []
        
        # Check if response is empty
        if not response.content.strip():
            print("⚠️  Empty response from model")
            self._debug_output(context, prompt, response)
            return []
        
        # Parse JSON from response
        plan_json = self._extract_json(response.content)
        
        if not plan_json:
            print(f"⚠️  Could not parse JSON from model response")
            self._debug_output(context, prompt, response)
            return []
        
        actions = self._parse_actions(plan_json.get("actions", []))
        
        # Show debug info if no actions generated
        if not actions:
            print("⚠️  No actions generated from valid JSON")
            self._debug_output(context, prompt, response)
        
        return actions
    
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
        
        if not isinstance(actions_data, list):
            print(f"Warning: Expected list of actions, got: {type(actions_data)}")
            return actions
        
        for i, action_data in enumerate(actions_data):
            try:
                if not isinstance(action_data, dict):
                    print(f"Warning: Action {i} is not a dict: {action_data}")
                    continue
                
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
                else:
                    print(f"Warning: Unknown action type: {action_type}")
            except Exception as e:
                print(f"Error parsing action {i}: {e}")
                continue
        
        return actions
    
    def _debug_output(self, context: Context, prompt: str, response):
        """Show debug information when no actions can be generated."""
        if context.debug:
            print("\n" + "="*60)
            print("🐛 DEBUG MODE - FULL PROMPT AND RESPONSE")
            print("="*60)
            print("\n📝 Full Prompt:")
            print("-" * 40)
            print(prompt)
            print("\n🤖 Model Response:")
            print("-" * 40)
            print(f"Content: {response.content}")
            print(f"Metadata: {response.metadata}")
            print("="*60 + "\n")
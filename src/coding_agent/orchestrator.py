"""Plan orchestrator for generating execution plans."""

import json
import os
import re
from typing import Dict, Any, List, Union
from .types import Plan, ToolAction, ConfirmationAction, Context, PlanMetadata
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
    
    def generate_plan(self, context: Context, previous_results: List = None, step: int = 1) -> Plan:
        """Generate an execution plan for the user request."""
        # Step 1: Apply hardcoded pre-actions (only on first iteration)
        if previous_results is None:
            pre_actions = self._get_pre_actions(context)
        else:
            pre_actions = []
        
        # Step 2: Generate LLM plan (with previous results if available)
        llm_actions = self._generate_llm_plan(context, previous_results, step)
        
        # Step 3: Combine actions
        all_actions = pre_actions + llm_actions
        
        # Step 4: Analyze plan and generate metadata
        metadata = self._analyze_plan(all_actions, previous_results, step, context)
        
        return Plan(actions=all_actions, metadata=metadata)
    
    def _get_pre_actions(self, context: Context) -> List[Union[ToolAction, ConfirmationAction]]:
        """Get hardcoded pre-actions based on context analysis."""
        pre_actions = []
        
        # Only keep minimal file-based pre-actions - let LLM handle everything else
        
        # If request mentions files or directories, handle appropriately
        file_mentions = re.findall(r'[a-zA-Z0-9_./]+(?:\.[a-zA-Z]+|/\.\.\.?)', context.user_prompt)
        for file_path in file_mentions:
            # If it's a directory pattern like "src/..." or "src/", use search_files instead
            if file_path.endswith("/...") or file_path.endswith("/"):
                directory = file_path.rstrip("/...")
                pre_actions.append(ToolAction(
                    tool_name="search_files",
                    parameters={"pattern": ".", "directory": directory}
                ))
            elif file_path not in context.modified_files:
                pre_actions.append(ToolAction(
                    tool_name="read_file",
                    parameters={"file_path": file_path}
                ))
        
        return pre_actions
    
    def _generate_llm_plan(self, context: Context, previous_results: List = None, step: int = 1) -> List[Union[ToolAction, ConfirmationAction]]:
        """Generate plan using LLM."""
        # Check if model provider is available first
        if not self.model_provider.is_available():
            print("⚠️  Model provider not available")
            return []
        
        prompt = self.prompt_manager.build_prompt(
            context, 
            self.tool_registry.get_schemas(),
            previous_results
        )
        
        response = self.model_provider.generate(prompt)
        
        # Always show debug info if debug mode is enabled
        if context.debug:
            self._debug_output(context, prompt, response)
        
        # Check if there was an error in the response
        if response.metadata and "error" in response.metadata:
            print(f"⚠️  Model error: {response.metadata['error']}")
            return []
        
        # Check if response is empty
        if not response.content.strip():
            print("⚠️  Empty response from model")
            return []
        
        # Parse JSON from response
        plan_json = self._extract_json(response.content)
        
        if not plan_json:
            # Don't show confusing JSON error to users, just return empty plan
            return []
        
        actions = self._parse_actions(plan_json.get("actions", []))
        
        # Filter out unnecessary confirmations for read-only operations
        actions = self._filter_unnecessary_confirmations(actions, context)
        
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
    
    def _filter_unnecessary_confirmations(self, actions: List[Union[ToolAction, ConfirmationAction]], context: Context) -> List[Union[ToolAction, ConfirmationAction]]:
        """Remove unnecessary confirmation actions for simple read-only operations."""
        if not actions:
            return actions
        
        # Check if all tool actions are read-only/non-destructive
        tool_actions = [a for a in actions if hasattr(a, 'tool_name')]
        read_only_tools = {
            'read_file', 'search_files', 'git_status', 'git_diff', 'git_commit_hash',
            'brainstorm_search_terms', 'run_tests', 'lint_code', 'summarize_code', 'analyze_code'
        }
        
        # If all tools are read-only, remove confirmations
        if tool_actions and all(a.tool_name in read_only_tools for a in tool_actions):
            # Remove all confirmation actions for read-only operations
            filtered_actions = [a for a in actions if not isinstance(a, ConfirmationAction)]
            if filtered_actions != actions:
                print("🔧 Removed unnecessary confirmations for read-only operation")
            return filtered_actions
        
        return actions
    
    def _analyze_plan(self, actions: List[Union[ToolAction, ConfirmationAction]], 
                     previous_results: List = None, step: int = 1, context: Context = None) -> PlanMetadata:
        """Analyze the plan and determine metadata for intelligent stopping."""
        
        # Determine if this looks like a final step
        is_final = self._is_final_step(actions, previous_results, step, context)
        
        # Calculate confidence based on action types and context
        confidence = self._calculate_confidence(actions, previous_results, step)
        
        # Determine if follow-up is expected
        expected_follow_up = self._should_expect_follow_up(actions, previous_results, step, context)
        
        # Generate reasoning
        reasoning = self._generate_reasoning(actions, previous_results, step, is_final)
        
        return PlanMetadata(
            step_number=step,
            is_final=is_final,
            confidence=confidence,
            reasoning=reasoning,
            expected_follow_up=expected_follow_up
        )
    
    def _is_final_step(self, actions: List, previous_results: List = None, step: int = 1, context: Context = None) -> bool:
        """Determine if this appears to be the final step."""
        # No actions means we think we're done
        if not actions:
            return True
        
        # Only confirmations suggest completion
        tool_actions = [a for a in actions if hasattr(a, 'tool_name')]
        if not tool_actions:
            return True
        
        # If we have many previous results and only simple actions left, likely final
        if previous_results and len(previous_results) > 3:
            simple_actions = ['git_status', 'git_diff', 'read_file']
            if all(a.tool_name in simple_actions for a in tool_actions if hasattr(a, 'tool_name')):
                return True
        
        # Check for completion-indicating actions
        completion_actions = ['run_tests', 'lint_code', 'git_commit', 'summarize_code', 'analyze_code']
        has_completion_action = any(a.tool_name in completion_actions for a in tool_actions if hasattr(a, 'tool_name'))
        
        return has_completion_action and step > 2
    
    def _calculate_confidence(self, actions: List, previous_results: List = None, step: int = 1) -> float:
        """Calculate confidence score for the plan."""
        base_confidence = 1.0
        
        # Reduce confidence for later steps
        confidence = base_confidence * (0.9 ** (step - 1))
        
        # Increase confidence if we have successful previous results
        if previous_results:
            success_rate = sum(1 for r in previous_results if hasattr(r, 'success') and r.success) / len(previous_results)
            confidence *= (0.5 + 0.5 * success_rate)
        
        # Reduce confidence if no actions
        if not actions:
            confidence *= 0.7
        
        return max(0.1, min(1.0, confidence))
    
    def _should_expect_follow_up(self, actions: List, previous_results: List = None, step: int = 1, context: Context = None) -> bool:
        """Determine if we should expect follow-up actions."""
        # No actions means no follow-up expected
        if not actions:
            return False
        
        # If we're doing exploratory actions, expect follow-up
        exploratory_actions = ['git_status', 'git_diff', 'read_file', 'search_files', 'brainstorm_search_terms']
        tool_actions = [a for a in actions if hasattr(a, 'tool_name')]
        
        if any(a.tool_name in exploratory_actions for a in tool_actions):
            return True
        
        # If we're doing write operations without completion actions, expect follow-up
        write_actions = ['write_file']
        completion_actions = ['run_tests', 'lint_code']
        
        has_write = any(a.tool_name in write_actions for a in tool_actions)
        has_completion = any(a.tool_name in completion_actions for a in tool_actions)
        
        if has_write and not has_completion:
            return True
        
        return step < 3  # Generally expect follow-up for early steps
    
    def _generate_reasoning(self, actions: List, previous_results: List = None, step: int = 1, is_final: bool = False) -> str:
        """Generate reasoning for the plan analysis."""
        if not actions:
            return f"No actions generated at step {step}, suggesting task completion"
        
        tool_actions = [a for a in actions if hasattr(a, 'tool_name')]
        action_types = [a.tool_name for a in tool_actions]
        
        if is_final:
            return f"Step {step} appears final: {', '.join(action_types)}"
        else:
            return f"Step {step} with {len(actions)} actions: {', '.join(action_types)}"
    
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
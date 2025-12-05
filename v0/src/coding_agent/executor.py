"""Plan executor for running tool execution loops."""

import hashlib
import json
from typing import List, Dict, Any, Set
from .types import Plan, ToolAction, ConfirmationAction, ToolResult
from .tools.registry import ToolRegistry
from .config import AgentConfig


class PlanExecutor:
    """Executes plans by running tools in sequence."""

    def __init__(self, tool_registry: ToolRegistry, config: AgentConfig = None):
        self.tool_registry = tool_registry
        self.config = config
        self.execution_log: List[Dict[str, Any]] = []
        self.completed_action_hashes: Set[str] = set()  # Track completed destructive actions
    
    def _generate_action_hash(self, action: ToolAction) -> str:
        """Generate a unique hash for an action based on tool name and parameters."""
        action_dict = {
            "tool_name": action.tool_name,
            "parameters": action.parameters
        }
        action_json = json.dumps(action_dict, sort_keys=True)
        return hashlib.md5(action_json.encode()).hexdigest()

    def execute_plan(self, plan: Plan) -> List[ToolResult]:
        """Execute a plan and return results."""
        results = []

        for action in plan.actions:
            if isinstance(action, ConfirmationAction):
                # Skip old-style confirmation actions - confirmation is now handled upfront in agent.py
                continue

            if isinstance(action, ToolAction):
                # Generate hash for this action
                action_hash = self._generate_action_hash(action)

                # Check if this exact action was already completed
                if action_hash in self.completed_action_hashes:
                    # Skip this action - it was already done
                    results.append(ToolResult(
                        success=True,
                        output="Action already completed in previous step",
                        action_description=f"Skipped (already done): {action.tool_name}"
                    ))
                    continue

                # Execute the tool action (confirmation already handled before plan execution)
                result = self._execute_tool_action(action)
                results.append(result)

                # Mark this action as completed if successful
                if result.success:
                    self.completed_action_hashes.add(action_hash)

                # Show tool output if configured
                self._maybe_show_tool_output(action.tool_name, result)

                # Log execution
                self.execution_log.append({
                    "action": action.dict(),
                    "result": result.dict()
                })

                # Stop on failure unless it's a non-critical tool
                if not result.success and self._is_critical_tool(action.tool_name):
                    break
        
        return results
    
    def _execute_tool_action(self, action: ToolAction) -> ToolResult:
        """Execute a single tool action."""
        try:
            tool = self.tool_registry.get_tool(action.tool_name)
            result = tool.execute(**action.parameters)
            
            # Add action description to result
            result.action_description = f"{action.tool_name}({action.parameters})"
            return result
        except Exception as e:
            return ToolResult(
                success=False,
                output=None,
                error=f"Tool execution failed: {str(e)}",
                action_description=f"{action.tool_name}({action.parameters})"
            )
    
    def _request_confirmation(self, action: ConfirmationAction) -> bool:
        """Request user confirmation for destructive actions."""
        print(f"\n⚠️  {action.message}")
        if action.destructive:
            print("This action is destructive and cannot be undone.")
        
        # Check for auto-continue setting
        if self.config and self.config.execution.auto_continue:
            print("Auto-continue enabled - proceeding automatically.")
            return True
        
        response = input("Continue? (y/N): ").strip().lower()
        return response in ['y', 'yes']
    
    def _request_confirmation_for_tool(self, message: str) -> bool:
        """Request user confirmation for destructive tool actions."""
        print(f"\n⚠️  {message}")
        print("This action will modify files or system state.")
        
        # Check for auto-continue setting
        if self.config and self.config.execution.auto_continue:
            print("Auto-continue enabled - proceeding automatically.")
            return True
        
        response = input("Continue? (y/N): ").strip().lower()
        return response in ['y', 'yes']
    
    def _maybe_show_tool_output(self, tool_name: str, result: ToolResult):
        """Show tool output if configured to do so."""
        if not self.config or not result.success:
            return
        
        show_output_tools = self.config.execution.show_tool_output
        if tool_name in show_output_tools and result.output:
            print(f"\n📋 {tool_name} output:")
            print("-" * 60)
            print(result.output)
            print("-" * 60)
    
    def _is_critical_tool(self, tool_name: str) -> bool:
        """Check if a tool failure should stop execution."""
        # Most tools are critical, but some like search can fail without stopping
        non_critical_tools = {'search_files', 'brainstorm_search_terms'}
        return tool_name not in non_critical_tools
    
    def get_execution_summary(self) -> str:
        """Get a summary of the last execution."""
        if not self.execution_log:
            return "No actions executed"
        
        successful = sum(1 for entry in self.execution_log if entry["result"]["success"])
        total = len(self.execution_log)
        
        return f"Executed {successful}/{total} actions successfully"
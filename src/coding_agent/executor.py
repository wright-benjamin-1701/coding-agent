"""Plan executor for running tool execution loops."""

from typing import List, Dict, Any
from .types import Plan, ToolAction, ConfirmationAction, ToolResult
from .tools.registry import ToolRegistry
from .config import AgentConfig


class PlanExecutor:
    """Executes plans by running tools in sequence."""
    
    def __init__(self, tool_registry: ToolRegistry, config: AgentConfig = None):
        self.tool_registry = tool_registry
        self.config = config
        self.execution_log: List[Dict[str, Any]] = []
    
    def execute_plan(self, plan: Plan) -> List[ToolResult]:
        """Execute a plan and return results."""
        results = []
        
        for action in plan.actions:
            if isinstance(action, ConfirmationAction):
                # Handle confirmation actions
                confirmed = self._request_confirmation(action)
                if not confirmed:
                    results.append(ToolResult(
                        success=False, 
                        output=None, 
                        error="User cancelled action",
                        action_description=f"Confirmation: {action.message}"
                    ))
                    break
                else:
                    results.append(ToolResult(
                        success=True, 
                        output="Confirmed",
                        action_description=f"Confirmation: {action.message}"
                    ))
            
            elif isinstance(action, ToolAction):
                # Execute tool action
                result = self._execute_tool_action(action)
                results.append(result)
                
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
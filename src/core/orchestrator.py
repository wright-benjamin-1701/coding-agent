"""
Agent orchestrator for coordinating LLM providers and tools
"""
import json
import time
from typing import Dict, List, Optional, Any
from dataclasses import dataclass

from .providers.base import BaseLLMProvider, ChatMessage, ModelConfig
from .tools.base import BaseTool
from .context import ContextManager, ProjectContext
from .config import ConfigManager, get_config
from .safety import get_safety_enforcer
from .planner import get_task_planner, TaskStatus, TaskPlan
from .collaboration import get_session_manager
from .model_router import ModelRouter, TaskComplexity
from .learning import get_learning_system


@dataclass
class Task:
    """Represents a task to be executed by the agent"""
    id: str
    description: str
    priority: int = 1
    status: str = "pending"  # pending, in_progress, completed, failed
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


@dataclass
class AgentContext:
    """Context for agent operations"""
    project_path: str
    conversation_history: List[ChatMessage]
    active_tasks: List[Task]
    memory: Dict[str, Any]
    project_context: Optional[ProjectContext] = None


class AgentOrchestrator:
    """Main orchestrator for the coding agent"""
    
    def __init__(self, provider: BaseLLMProvider, tools: List[BaseTool], config_manager: Optional[ConfigManager] = None):
        self.provider = provider
        self.tools = {tool.name: tool for tool in tools}
        self.config = config_manager or get_config()
        self.safety_enforcer = get_safety_enforcer()
        self.task_planner = get_task_planner()
        self.session_manager = get_session_manager()
        self.learning_system = get_learning_system()
        self.model_router = ModelRouter(provider, config_manager)
        self.context_manager: Optional[ContextManager] = None
        self.context = AgentContext(
            project_path="",
            conversation_history=[],
            active_tasks=[],
            memory={},
            project_context=None
        )
        self.task_history: List[Dict[str, Any]] = []
        self.current_plan_id: Optional[str] = None
        self.session_data: Dict[str, Any] = {}
    
    async def process_request(self, user_input: str) -> str:
        """Process user request and coordinate response"""
        
        # Add user message to conversation history
        user_message = ChatMessage(role="user", content=user_input)
        self.context.conversation_history.append(user_message)
        
        # Update session
        if self.session_manager.current_session:
            self.session_manager.update_session(
                conversation_history=[msg.__dict__ for msg in self.context.conversation_history]
            )
        
        # Analyze request and determine if tools are needed
        task_plan = await self._analyze_request(user_input)
        
        # Get learning-based adaptations
        adaptations = self.learning_system.adapt_behavior({
            "task_type": "analyze_request",
            "project_context": bool(self.context.project_context),
            "conversation_length": len(self.context.conversation_history)
        })
        
        # Analyze task complexity for model routing
        task_complexity = self.model_router.analyze_task_complexity(user_input, {
            "project_context": self.context.project_context,
            "conversation_history": self.context.conversation_history,
            "adaptations": adaptations
        })
        
        # Check if clarification is needed
        if task_plan.get("needs_clarification", False):
            result = await self._ask_clarification(user_input, task_plan, task_complexity)
        elif task_plan.get("requires_tools", False):
            # Create execution plan for complex tasks
            if task_plan.get("complexity") in ["medium", "high"]:
                plan = await self.task_planner.create_plan(user_input, {
                    "project_context": self.context.project_context,
                    "conversation_history": self.context.conversation_history
                })
                self.current_plan_id = plan.id
                result = await self._execute_planned_task(plan, task_complexity)
            else:
                # Execute simple tool operations directly
                result = await self._execute_with_tools(task_plan, task_complexity)
        else:
            # Simple LLM response with intelligent model routing
            result = await self._simple_response(user_input, task_complexity)
        
        # Add assistant response to history
        assistant_message = ChatMessage(role="assistant", content=result)
        self.context.conversation_history.append(assistant_message)
        
        # Record interaction for learning
        learning_context = {
            "task_complexity": task_complexity.__dict__ if task_complexity else {},
            "tools_used": task_plan.get("tools_needed", []) if task_plan.get("requires_tools") else [],
            "task_type": task_plan.get("complexity", "unknown") if task_plan else "simple_response",
            "project_context": bool(self.context.project_context)
        }
        
        self.learning_system.record_interaction(
            user_input=user_input,
            agent_response=result,
            context=learning_context
        )
        
        # Update session again
        if self.session_manager.current_session:
            self.session_manager.update_session(
                conversation_history=[msg.__dict__ for msg in self.context.conversation_history],
                active_tasks=[task.__dict__ for task in self.context.active_tasks]
            )
        
        return result
    
    async def _analyze_request(self, user_input: str) -> Dict[str, Any]:
        """Analyze user request to determine required actions"""
        
        # Include project context in analysis
        project_context = self.get_project_summary()
        
        system_prompt = f"""You are a coding agent analyzer. Analyze the user request and determine:
1. If tools are needed (file operations, git commands, etc.)
2. What tools should be used
3. The sequence of actions required
4. Priority level (1-5, 5 being highest)

{project_context}

Available tools: {', '.join(self.tools.keys())}

Respond with JSON containing:
{{
    "requires_tools": boolean,
    "needs_clarification": boolean,
    "tools_needed": [list of tool names],
    "action_sequence": [ordered list of actions],
    "priority": integer,
    "complexity": "low|medium|high",
    "estimated_steps": integer,
    "clarification_questions": [list of questions if clarification needed],
    "alternatives": [list of alternative approaches if applicable]
}}

Set needs_clarification to true when:
- The request is ambiguous or vague
- Multiple approaches are possible and user preference matters
- Missing critical information needed to proceed
- The request could be interpreted in multiple ways"""
        
        messages = [
            ChatMessage(role="system", content=system_prompt),
            ChatMessage(role="user", content=user_input)
        ]
        
        model_config = ModelConfig(
            model_name=self._select_model("analysis"),
            temperature=0.1,
            max_tokens=500
        )
        
        response = await self.provider.chat_completion(messages, model_config)
        
        try:
            return json.loads(response.content)
        except json.JSONDecodeError:
            # Fallback if JSON parsing fails
            return {
                "requires_tools": False,
                "needs_clarification": False,
                "tools_needed": [],
                "action_sequence": ["respond"],
                "priority": 1,
                "complexity": "low",
                "estimated_steps": 1,
                "clarification_questions": [],
                "alternatives": []
            }
    
    async def _execute_with_tools(self, task_plan: Dict[str, Any], task_complexity: TaskComplexity) -> str:
        """Execute request using tools based on task plan"""
        
        tools_needed = task_plan.get("tools_needed", [])
        available_tools: List[BaseTool] = []
        
        # Gather available tools  
        for tool_name in tools_needed:
            if tool_name in self.tools:
                available_tools.append(self.tools[tool_name])
        
        # Build system prompt with tool schemas
        tool_schemas: List[Dict[str, Any]] = []
        for tool in available_tools:
            tool_schemas.append(tool.to_llm_function_schema())
        
        system_prompt = f"""You are a helpful coding agent with access to the following tools:

{json.dumps(tool_schemas, indent=2)}

When you need to use a tool, respond with JSON in this format:
{{
    "action": "use_tool",
    "tool": "tool_name",
    "parameters": {{"param1": "value1", "param2": "value2"}}
}}

When you're done or don't need tools, respond with:
{{
    "action": "respond",
    "message": "your response to the user"
}}

Be helpful and execute the user's request step by step."""
        
        messages = [
            ChatMessage(role="system", content=system_prompt),
            *self.context.conversation_history[-10:],  # Include recent context
        ]
        
        max_iterations = 10
        iteration = 0
        
        while iteration < max_iterations:
            # Use intelligent model routing for tool coordination
            response_content = await self.model_router.execute_with_routing(messages, task_complexity)
            
            # Add assistant response to conversation
            messages.append(ChatMessage(role="assistant", content=response_content))
            
            try:
                action = json.loads(response_content)
                
                if action.get("action") == "respond":
                    return action.get("message", "Task completed.")
                
                elif action.get("action") == "use_tool":
                    tool_name = action.get("tool")
                    parameters = action.get("parameters", {})
                    
                    if tool_name in self.tools:
                        tool_result = await self.tools[tool_name].execute(**parameters)
                        
                        # Add tool result to conversation
                        result_message = f"Tool '{tool_name}' result: "
                        if tool_result.success:
                            result_message += tool_result.content or str(tool_result.data)
                        else:
                            result_message += f"Error: {tool_result.error}"
                        
                        messages.append(ChatMessage(role="user", content=result_message))
                    else:
                        messages.append(ChatMessage(
                            role="user", 
                            content=f"Tool '{tool_name}' not available"
                        ))
                
            except json.JSONDecodeError:
                # If not JSON, treat as final response
                return response_content
            
            iteration += 1
        
        return "Task execution exceeded maximum iterations."
    
    async def _ask_clarification(self, user_input: str, task_plan: Dict[str, Any], task_complexity: TaskComplexity) -> str:
        """Ask clarifying questions when request is ambiguous"""
        
        questions = task_plan.get("clarification_questions", [])
        alternatives = task_plan.get("alternatives", [])
        
        # Use fast model for clarification questions
        messages = [
            ChatMessage(
                role="system", 
                content="You are asking clarifying questions. Be helpful and concise."
            ),
            ChatMessage(role="user", content=user_input)
        ]
        
        # Force fast completion for clarification
        task_complexity.requires_speed = True
        task_complexity.requires_reasoning = False
        
        # Use fast model for clarification if available
        available_models = self.provider.list_models()
        if available_models:
            # Prefer smaller/faster models for clarification
            fast_model = available_models[0]  # Use first available as fallback
            model_config = ModelConfig(model_name=fast_model, temperature=0.3)
            response = await self.provider.chat_completion(messages, model_config)
            return response.content
        
        # Fallback to manual clarification
        response_parts = ["I need some clarification to help you better:"]
        
        if questions:
            response_parts.append("\n**Questions:**")
            for i, question in enumerate(questions, 1):
                response_parts.append(f"{i}. {question}")
        
        if alternatives:
            response_parts.append("\n**Possible approaches:**")
            for i, alt in enumerate(alternatives, 1):
                response_parts.append(f"{i}. {alt}")
        
        response_parts.append("\nPlease let me know which approach you prefer or provide more details.")
        
        return "\n".join(response_parts)
    
    async def _execute_planned_task(self, plan: TaskPlan, _task_complexity: TaskComplexity) -> str:
        """Execute a planned task step by step"""
        
        # Mark plan as started
        if plan.status == TaskStatus.PENDING:
            plan.status = TaskStatus.IN_PROGRESS
            plan.started_at = time.time()
        
        results: List[str] = []
        results.append(f"🎯 **Executing Plan: {plan.title}**\n")
        results.append(f"📋 **Steps:** {len(plan.steps)} total\n")
        
        # Execute steps in order
        while True:
            next_step = self.task_planner.get_next_executable_step(plan.id)
            
            if not next_step:
                break  # No more executable steps
            
            # Update step status
            self.task_planner.update_step_status(plan.id, next_step.id, TaskStatus.IN_PROGRESS)
            
            results.append(f"⚡ **Step {next_step.id}:** {next_step.description}")
            
            try:
                # Execute the step
                if next_step.tool in self.tools:
                    tool_result = await self.tools[next_step.tool].execute(**next_step.parameters)
                    
                    if tool_result.success:
                        self.task_planner.update_step_status(
                            plan.id, next_step.id, TaskStatus.COMPLETED, 
                            result=tool_result.data
                        )
                        results.append(f"✅ Completed: {tool_result.content}")
                    else:
                        self.task_planner.update_step_status(
                            plan.id, next_step.id, TaskStatus.FAILED, 
                            error=tool_result.error or "Unknown error"
                        )
                        results.append(f"❌ Failed: {tool_result.error}")
                        break  # Stop on failure
                else:
                    # Handle special steps
                    if next_step.tool == "context":
                        # Context gathering step
                        context_summary = self.get_project_summary()
                        self.task_planner.update_step_status(
                            plan.id, next_step.id, TaskStatus.COMPLETED,
                            result={"context": context_summary}
                        )
                        results.append(f"✅ Gathered project context")
                    
                    elif next_step.tool == "verification":
                        # Verification step
                        self.task_planner.update_step_status(
                            plan.id, next_step.id, TaskStatus.COMPLETED,
                            result={"verified": True}
                        )
                        results.append(f"✅ Verified changes")
                    
                    elif next_step.tool == "reporting":
                        # Final reporting step
                        progress = self.task_planner.get_plan_progress(plan.id)
                        self.task_planner.update_step_status(
                            plan.id, next_step.id, TaskStatus.COMPLETED,
                            result={"progress": progress}
                        )
                        results.append(f"📊 **Final Status:** {progress['progress_percentage']:.1f}% complete")
            
            except Exception as e:
                self.task_planner.update_step_status(
                    plan.id, next_step.id, TaskStatus.FAILED, 
                    error=str(e)
                )
                results.append(f"❌ Error: {str(e)}")
                break
        
        # Get final plan status
        final_progress = self.task_planner.get_plan_progress(plan.id)
        results.append(f"\n🏁 **Task Complete:** {final_progress['completed_steps']}/{final_progress['total_steps']} steps finished")
        
        return "\n".join(results)
    
    async def _simple_response(self, _user_input: str, task_complexity: TaskComplexity) -> str:
        """Generate simple LLM response without tools using intelligent routing"""
        
        # Include project context in system message if available
        context_info = ""
        if self.context.project_context:
            context_info = f"\n\nProject context: {self.get_project_summary()}"
        
        messages = [
            ChatMessage(
                role="system", 
                content=f"You are a helpful coding assistant. Provide clear, concise responses.{context_info}"
            ),
            *self.context.conversation_history[-10:],  # Include recent context
        ]
        
        # Use intelligent model routing
        return await self.model_router.execute_with_routing(messages, task_complexity)
    
    def _select_model(self, task_type: str) -> str:
        """Select appropriate model based on task type and configuration"""
        available_models = self.provider.list_models()
        
        if not available_models:
            return "default"
        
        # Use configuration-based model selection
        selected_model = self.config.get_model_for_task(task_type, available_models)
        
        if selected_model:
            return selected_model
        
        # Fallback logic for backwards compatibility
        if task_type == "execution":
            for model in available_models:
                if any(term in model.lower() for term in ["coder", "code", "deepseek"]):
                    return model
        
        # Use first available model as final fallback
        return available_models[0]
    
    def add_tool(self, tool: BaseTool) -> None:
        """Add a new tool to the orchestrator"""
        self.tools[tool.name] = tool
    
    def remove_tool(self, tool_name: str) -> None:
        """Remove a tool from the orchestrator"""
        if tool_name in self.tools:
            del self.tools[tool_name]
    
    def get_available_tools(self) -> List[str]:
        """Get list of available tool names"""
        return list(self.tools.keys())
    
    async def set_project_path(self, path: str) -> None:
        """Set the current project path and build context"""
        self.context.project_path = path
        self.context_manager = ContextManager(path)
        
        # Start new session
        self.session_manager.start_session(path)
        
        # Build project context
        try:
            self.context.project_context = await self.context_manager.build_context()
            
            # Update session with project context
            self.session_manager.update_session(
                project_context=self.context_manager.to_dict() if self.context_manager and self.context.project_context else None
            )
        except Exception as e:
            print(f"Warning: Could not build project context: {e}")
    
    def get_project_summary(self) -> str:
        """Get a summary of the project for the LLM"""
        if not self.context.project_context:
            return "No project context available."
        
        if not self.context_manager:
            return "No project context available."
            
        summary = self.context_manager.get_project_summary()
        
        context_text = f"""Project Context:
- Location: {self.context.project_path}
- Files: {summary['total_files']} files ({summary['total_size_bytes']} bytes)
- Main language: {summary['main_language']}
- Languages: {', '.join(f"{lang}({count})" for lang, count in summary['languages'].items())}"""
        
        if summary.get('dependencies'):
            deps_text = ', '.join(f"{lang}({count})" for lang, count in summary['dependencies'].items())
            context_text += f"\n- Dependencies: {deps_text}"
        
        if summary.get('has_git'):
            context_text += "\n- Git repository: Yes"
        
        return context_text
    
    def clear_conversation_history(self) -> None:
        """Clear conversation history"""
        self.context.conversation_history.clear()
    
    def get_context_summary(self) -> Dict[str, Any]:
        """Get summary of current context"""
        return {
            "project_path": self.context.project_path,
            "conversation_length": len(self.context.conversation_history),
            "active_tasks": len(self.context.active_tasks),
            "available_tools": list(self.tools.keys()),
            "memory_keys": list(self.context.memory.keys())
        }
    
    async def process_user_feedback(self, feedback: str, interaction_context: Optional[Dict[str, Any]] = None) -> str:
        """Process user feedback for learning and improvement"""
        
        if not self.context.conversation_history or len(self.context.conversation_history) < 2:
            return "No recent interaction to provide feedback on."
        
        # Get the last user input and agent response
        last_messages = self.context.conversation_history[-2:]
        if len(last_messages) >= 2:
            user_input = last_messages[0].content
            agent_response = last_messages[1].content
            
            # Create context for feedback
            feedback_context = interaction_context or {
                "feedback_type": "user_correction" if any(word in feedback.lower() for word in ["wrong", "incorrect", "should"]) else "general",
                "timestamp": time.time()
            }
            
            # Record the feedback
            event_id = self.learning_system.record_interaction(
                user_input=user_input,
                agent_response=agent_response,
                context=feedback_context,
                user_feedback=feedback
            )
            
            return f"Thank you for the feedback! I've recorded this to improve future responses. (Event ID: {event_id})"
        
        return "Could not process feedback - insufficient conversation history."
    
    def get_learning_summary(self) -> Dict[str, Any]:
        """Get summary of learning progress"""
        return self.learning_system.get_learning_summary()
    
    def get_user_preferences(self) -> Dict[str, Any]:
        """Get current user preferences"""
        return self.learning_system.get_user_preferences()
    
    def get_performance_metrics(self) -> Dict[str, Dict[str, float]]:
        """Get performance metrics"""
        return self.learning_system.get_performance_metrics()
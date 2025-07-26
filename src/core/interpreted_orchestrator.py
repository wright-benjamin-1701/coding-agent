"""
Enhanced orchestrator that uses the interpretation layer for better handling of small model outputs
"""
import json
import time
from typing import Dict, List, Optional, Any

from .orchestrator import AgentOrchestrator, Task, AgentContext, ChatMessage
from .interpreter import (
    RequestInterpreter, ResponseInterpreter, create_request_interpreter, 
    create_response_interpreter, IntentType, ActionType, InterpreterResult
)
from .providers.base import BaseLLMProvider, ModelConfig
from .tools.base import BaseTool
from .config import ConfigManager


class InterpretedOrchestrator(AgentOrchestrator):
    """Orchestrator enhanced with interpretation layer for small model reliability"""
    
    def __init__(self, provider: BaseLLMProvider, tools: List[BaseTool], config_manager: Optional[ConfigManager] = None):
        super().__init__(provider, tools, config_manager)
        
        # Add interpretation layer
        self.request_interpreter = create_request_interpreter(provider, config_manager)
        self.response_interpreter = create_response_interpreter(provider, config_manager)
        
        # Track interpretation results for learning
        self.interpretation_history: List[Dict[str, Any]] = []
    
    async def process_request(self, user_input: str) -> str:
        """Process user request with interpretation layer"""
        
        # Add user message to conversation history
        user_message = ChatMessage(role="user", content=user_input)
        self.context.conversation_history.append(user_message)
        
        # Update session
        if self.session_manager.current_session:
            self.session_manager.update_session(
                conversation_history=[msg.__dict__ for msg in self.context.conversation_history]
            )
        
        # INTERPRETATION PHASE: Understand the request
        interpretation_context = {
            "project_context": self.context.project_context,
            "conversation_history": self.context.conversation_history,
            "available_tools": list(self.tools.keys())
        }
        
        interpretation = await self.request_interpreter.interpret_request(
            user_input, interpretation_context
        )
        
        # Log interpretation for analysis
        self.interpretation_history.append({
            "timestamp": time.time(),
            "user_input": user_input,
            "interpretation": {
                "intent": interpretation.intent.intent_type.value,
                "confidence": interpretation.intent.confidence,
                "actions": [action.action_type.value for action in interpretation.actions]
            }
        })
        
        # Check if clarification is needed
        if interpretation.intent.requires_clarification:
            return await self._handle_clarification_request(interpretation)
        
        # CONTEXT INJECTION PHASE: Gather necessary context
        if interpretation.context_to_inject:
            await self._inject_context(interpretation.context_to_inject)
        
        # EXECUTION PHASE: Execute interpreted actions
        result = await self._execute_interpreted_actions(interpretation, user_input)
        
        # Add assistant response to history
        assistant_message = ChatMessage(role="assistant", content=result)
        self.context.conversation_history.append(assistant_message)
        
        # Record interaction for learning (enhanced with interpretation data)
        learning_context = {
            "intent_type": interpretation.intent.intent_type.value,
            "intent_confidence": interpretation.intent.confidence,
            "actions_taken": len(interpretation.actions),
            "context_injected": len(interpretation.context_to_inject),
            "project_context": bool(self.context.project_context)
        }
        
        self.learning_system.record_interaction(
            user_input=user_input,
            agent_response=result,
            context=learning_context
        )
        
        # Update session
        if self.session_manager.current_session:
            self.session_manager.update_session(
                conversation_history=[msg.__dict__ for msg in self.context.conversation_history],
                active_tasks=[task.__dict__ for task in self.context.active_tasks]
            )
        
        return result
    
    async def _handle_clarification_request(self, interpretation: InterpreterResult) -> str:
        """Handle requests that need clarification"""
        
        response_parts = ["I need some clarification to help you better:"]
        
        for i, question in enumerate(interpretation.intent.clarification_questions, 1):
            response_parts.append(f"{i}. {question}")
        
        response_parts.append("\nPlease provide more details so I can assist you properly.")
        
        return "\n".join(response_parts)
    
    async def _inject_context(self, context_files: List[str]) -> None:
        """Inject file contents into the conversation context"""
        
        context_messages = []
        
        for file_path in context_files:
            if "file" in self.tools:
                try:
                    # Read file content
                    file_result = await self.tools["file"].execute(action="read", path=file_path)
                    
                    if file_result.success and file_result.content:
                        context_message = f"Content of {file_path}:\n```\n{file_result.content}\n```"
                        context_messages.append(ChatMessage(role="system", content=context_message))
                
                except Exception as e:
                    # File doesn't exist or can't be read, continue with others
                    print(f"Could not inject context from {file_path}: {e}")
        
        # Add context messages to conversation history
        if context_messages:
            # Insert context before the current user message
            self.context.conversation_history[-1:-1] = context_messages
    
    async def _execute_interpreted_actions(self, interpretation: InterpreterResult, user_input: str) -> str:
        """Execute actions based on interpretation"""
        
        if not interpretation.actions:
            return await self._simple_interpreted_response(user_input, interpretation)
        
        # Sort actions by priority (higher first)
        sorted_actions = sorted(interpretation.actions, key=lambda x: x.priority, reverse=True)
        
        results = []
        action_results = {}  # Store results for dependent actions
        
        for action in sorted_actions:
            # Check dependencies
            if action.depends_on:
                missing_deps = [dep for dep in action.depends_on if dep not in action_results]
                if missing_deps:
                    results.append(f"⚠️ Skipping action due to missing dependencies: {missing_deps}")
                    continue
            
            # Execute action
            try:
                action_result = await self._execute_single_action(action, interpretation)
                
                if action_result:
                    results.append(action_result)
                    action_results[f"action_{len(action_results)}"] = action_result
            
            except Exception as e:
                results.append(f"❌ Error executing action: {str(e)}")
        
        # If no results, provide a fallback response
        if not results:
            return await self._simple_interpreted_response(user_input, interpretation)
        
        return "\n\n".join(results)
    
    async def _execute_single_action(self, action, interpretation: InterpreterResult) -> Optional[str]:
        """Execute a single interpreted action"""
        
        if action.action_type == ActionType.USE_TOOL:
            if action.tool_name and action.tool_name in self.tools:
                tool_result = await self.tools[action.tool_name].execute(**action.parameters)
                
                if tool_result.success:
                    return f"✅ {action.tool_name}: {tool_result.content or str(tool_result.data)}"
                else:
                    return f"❌ {action.tool_name} failed: {tool_result.error}"
        
        elif action.action_type == ActionType.READ_FILE:
            if "file" in self.tools:
                tool_result = await self.tools["file"].execute(**action.parameters)
                
                if tool_result.success:
                    return f"📄 **{action.parameters.get('path', 'File')}:**\n```\n{tool_result.content}\n```"
                else:
                    return f"❌ Could not read file: {tool_result.error}"
        
        elif action.action_type == ActionType.SEARCH_TEXT:
            if "search" in self.tools:
                tool_result = await self.tools["search"].execute(**action.parameters)
                
                if tool_result.success:
                    return f"🔍 **Search Results:**\n{tool_result.content}"
                else:
                    return f"❌ Search failed: {tool_result.error}"
        
        elif action.action_type == ActionType.PROVIDE_RESPONSE:
            # Use the modified prompt if available
            prompt = interpretation.modified_prompt or "Please provide a helpful response."
            return await self._simple_interpreted_response(prompt, interpretation)
        
        return None
    
    async def _simple_interpreted_response(self, user_input: str, interpretation: InterpreterResult) -> str:
        """Generate a simple response using interpretation context"""
        
        # Import prompt utilities
        from .prompt_utils import create_analysis_system_prompt
        
        # Build enhanced system message based on interpretation
        base_prompt_parts = ["You are a helpful coding assistant."]
        
        if interpretation.intent.intent_type != IntentType.GENERAL_QUESTION:
            intent_context = {
                IntentType.SEARCH_CODE: "The user wants to search for something in the code. Be specific about what you find.",
                IntentType.READ_FILES: "The user wants to examine file contents. Provide clear explanations.",
                IntentType.ANALYZE_PROJECT: "The user wants project analysis. Be comprehensive and structured.",
                IntentType.EDIT_CODE: "The user wants to modify code. Provide specific suggestions.",
                IntentType.DEBUG_ISSUE: "The user needs help with a problem. Be diagnostic and solution-focused."
            }
            
            context_msg = intent_context.get(interpretation.intent.intent_type, "")
            if context_msg:
                base_prompt_parts.append(context_msg)
        
        base_prompt = " ".join(base_prompt_parts)
        
        # Include project context if available  
        project_context = None
        if self.context.project_context:
            project_context = self.get_project_summary()
        
        system_prompt = create_analysis_system_prompt(project_context, user_input)
        
        messages = [
            ChatMessage(role="system", content=system_prompt),
            *self.context.conversation_history[-5:],  # Recent context
        ]
        
        # Use appropriate model based on intent complexity
        model_name = self._select_model_for_intent(interpretation.intent.intent_type)
        model_config = ModelConfig(
            model_name=model_name,
            temperature=0.3,
            max_tokens=1000 if interpretation.intent.intent_type == IntentType.ANALYZE_PROJECT else 500
        )
        
        response = await self.provider.chat_completion(messages, model_config)
        
        # Post-process response using response interpreter
        interpreted_response = await self.response_interpreter.interpret_response(response.content)
        
        # If the response interpreter found valid orchestrator format JSON, handle it
        if "action" in interpreted_response:
            if interpreted_response.get("action") == "respond":
                return interpreted_response.get("message", response.content)
            elif interpreted_response.get("action") == "use_tool":
                # Execute the tool action
                return await self._handle_structured_response(interpreted_response)
        
        # Handle other structured responses (legacy format)
        if interpreted_response.get("action") in ["edit_files"]:
            return await self._handle_structured_response(interpreted_response)
        
        # Default to the original response if no structured format found
        return interpreted_response.get("message", response.content)
    
    def _select_model_for_intent(self, intent_type: IntentType) -> str:
        """Select appropriate model based on intent type"""
        available_models = self.provider.list_models()
        
        if not available_models:
            return "default"
        
        # Map intent types to task types for configuration lookup
        intent_to_task_map = {
            IntentType.ANALYZE_PROJECT: "analysis",
            IntentType.DEBUG_ISSUE: "high_reasoning", 
            IntentType.REFACTOR_CODE: "high_reasoning",
            IntentType.SEARCH_CODE: "fast_completion",
            IntentType.READ_FILES: "fast_completion",
            IntentType.EDIT_CODE: "analysis",
            IntentType.GIT_OPERATION: "fast_completion",
            IntentType.EXECUTE_CODE: "analysis",
            IntentType.EXPLAIN_CODE: "analysis",
            IntentType.GENERAL_QUESTION: "chat"
        }
        
        task_type = intent_to_task_map.get(intent_type, "analysis")
        
        # ALWAYS prioritize configuration-based model selection
        selected_model = self.config.get_model_for_task(task_type, available_models)
        
        if selected_model:
            return selected_model
        
        # If no configured model is available, check if config has any preferred models
        all_configured_models = (
            self.config.config.models.high_reasoning +
            self.config.config.models.fast_completion + 
            self.config.config.models.analysis +
            self.config.config.models.chat
        )
        
        # Look for any configured model that's available
        for configured_model in all_configured_models:
            if configured_model in available_models:
                return configured_model
        
        # Only use fallback logic if NO configured models are available
        complex_intents = [
            IntentType.ANALYZE_PROJECT,
            IntentType.DEBUG_ISSUE,
            IntentType.REFACTOR_CODE
        ]
        
        if intent_type in complex_intents:
            # Prefer larger models for complex tasks
            for model in available_models:
                if any(term in model.lower() for term in ["coder", "code", "large", "instruct"]):
                    return model
        
        # Use first available model for simple tasks
        return available_models[0]
    
    async def _handle_structured_response(self, structured_response: Dict[str, Any]) -> str:
        """Handle structured responses from the response interpreter"""
        
        action = structured_response.get("action", "respond")
        
        if action == "use_tool":
            tool_name = structured_response.get("tool")
            parameters = structured_response.get("parameters", {})
            
            if tool_name and tool_name in self.tools:
                tool_result = await self.tools[tool_name].execute(**parameters)
                
                if tool_result.success:
                    return f"✅ Executed {tool_name}: {tool_result.content or str(tool_result.data)}"
                else:
                    return f"❌ Tool {tool_name} failed: {tool_result.error}"
            else:
                return f"❌ Tool '{tool_name}' not available. Available tools: {', '.join(self.tools.keys())}"
        
        elif action == "respond":
            return structured_response.get("message", "Task completed.")
        
        elif action == "edit_files":
            # Legacy support for edit_files action
            edits = structured_response.get("edits", [])
            results = []
            
            for edit in edits:
                file_path = edit.get("file")
                content = edit.get("content")
                
                if file_path and content and "file" in self.tools:
                    tool_result = await self.tools["file"].execute(
                        action="write", 
                        path=file_path, 
                        content=content
                    )
                    
                    if tool_result.success:
                        results.append(f"✅ Updated {file_path}")
                    else:
                        results.append(f"❌ Failed to update {file_path}: {tool_result.error}")
            
            return "\n".join(results) if results else "No files were modified."
        
        # Default fallback
        return structured_response.get("message", str(structured_response))
    
    def get_interpretation_stats(self) -> Dict[str, Any]:
        """Get statistics about interpretation performance"""
        
        if not self.interpretation_history:
            return {"total_interpretations": 0}
        
        # Analyze intent distribution
        intent_counts = {}
        confidence_scores = []
        
        for entry in self.interpretation_history:
            intent = entry["interpretation"]["intent"]
            confidence = entry["interpretation"]["confidence"]
            
            intent_counts[intent] = intent_counts.get(intent, 0) + 1
            confidence_scores.append(confidence)
        
        avg_confidence = sum(confidence_scores) / len(confidence_scores)
        
        return {
            "total_interpretations": len(self.interpretation_history),
            "intent_distribution": intent_counts,
            "average_confidence": avg_confidence,
            "low_confidence_count": sum(1 for score in confidence_scores if score < 0.5)
        }
    
    async def retrain_interpreter(self, feedback_data: List[Dict[str, Any]]) -> None:
        """Retrain interpreter based on user feedback"""
        
        # This could be enhanced to actually retrain the yes/no question system
        # For now, we'll adjust confidence thresholds based on feedback
        
        correct_interpretations = [
            item for item in feedback_data 
            if item.get("correct_interpretation", False)
        ]
        
        if correct_interpretations:
            # Could adjust the interpreter's confidence thresholds
            # or question weighting based on successful interpretations
            pass
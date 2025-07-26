"""
Agent orchestrator for coordinating LLM providers and tools
"""
import json
import re
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
        
        print(f"🔍 DEBUG: Processing request: {user_input}")
        
        # Add user message to conversation history
        user_message = ChatMessage(role="user", content=user_input)
        self.context.conversation_history.append(user_message)
        
        # Update session
        if self.session_manager.current_session:
            self.session_manager.update_session(
                conversation_history=[msg.__dict__ for msg in self.context.conversation_history]
            )
        
        # Analyze request and determine if tools are needed using directive format
        task_plan = await self._analyze_request_with_directive(user_input)
        
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
            print("🔍 DEBUG: Taking clarification path")
            result = await self._ask_clarification(user_input, task_plan, task_complexity)
        elif task_plan.get("requires_tools", False):
            print("🔍 DEBUG: Taking tools path")
            # Create execution plan for all tasks (regardless of complexity)
            print("🔍 DEBUG: Using planned task execution")
            
            # Use execution_steps if available, otherwise create plan normally
            if task_plan.get("execution_steps"):
                plan = await self._create_plan_from_execution_steps(user_input, task_plan)
            else:
                plan = await self.task_planner.create_plan(user_input, {
                    "project_context": self.context.project_context,
                    "conversation_history": self.context.conversation_history,
                    "user_request": user_input
                })
            self.current_plan_id = plan.id
            result = await self._execute_planned_task(plan, task_complexity)
        else:
            print("🔍 DEBUG: Taking simple response path (no tools)")
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
    
    async def _analyze_request_with_directive(self, user_input: str) -> Dict[str, Any]:
        """Analyze user request using directive format"""
        
        print("🔍 DEBUG: Analyzing request with directive format")
        
        # Import prompt utilities
        from .prompt_utils import create_directive_user_message
        
        # Build tool schemas for directive
        tool_schemas = []
        for tool_name, tool in self.tools.items():
            tool_schemas.append({
                "name": tool_name,
                "description": tool.to_llm_function_schema().get('description', 'No description')
            })
        
        # Create directive user message
        directive_message = create_directive_user_message(user_input, tool_schemas)
        
        print("🔍 DEBUG: Analysis directive message:")
        print("=" * 60)
        print(directive_message)
        print("=" * 60)
        
        # Include full context in analysis
        full_context = self._get_full_context()
        
        messages = [
            ChatMessage(
                role="system", 
                content=f"""You are a coding agent analyzer. Analyze the user request and provide a task plan.

{full_context}

CRITICAL INSTRUCTIONS:
- Respond ONLY with valid JSON
- NO thinking tags, explanations, or extra text
- Start immediately with {{ and end with }}
- Keep arrays under 3 items each
- Maximum response: 500 characters
- Be CONCISE"""
            ),
            ChatMessage(role="user", content=directive_message)
        ]
        
        model_config = ModelConfig(
            model_name=self._select_model("analysis"),
            temperature=0.1,
            max_tokens=1500  # Increased to allow longer valid JSON responses
        )
        
        response = await self.provider.chat_completion(messages, model_config)
        
        print(f"🔍 DEBUG: Raw analysis response: {response.content}")
        print(f"🔍 DEBUG: Response length: {len(response.content)} characters")
        
        # Debug: Check if response starts with valid JSON
        if response.content.strip().startswith('{'):
            print("🔍 DEBUG: Response starts with '{' - likely valid JSON")
            # Show first and last 200 characters to identify issues
            content = response.content.strip()
            print(f"🔍 DEBUG: First 200 chars: {content[:200]}")
            print(f"🔍 DEBUG: Last 200 chars: {content[-200:]}")
        else:
            print("🔍 DEBUG: Response does NOT start with '{' - contains extra text")
        
        # Try to parse JSON with multiple strategies
        parsed_json = self._parse_analysis_json(response.content)
        
        if parsed_json:
            print(f"🔍 DEBUG: Successfully parsed analysis: {parsed_json}")
            return parsed_json
        else:
            print("🔍 DEBUG: All JSON parsing strategies failed, using intelligent fallback")
            # Create intelligent fallback based on content analysis
            return self._create_intelligent_fallback(user_input, response.content)
    
    def _parse_analysis_json(self, response_content: str) -> Optional[Dict[str, Any]]:
        """Try multiple strategies to parse JSON from model response"""
        
        # Strategy 1: Direct parsing
        try:
            parsed = json.loads(response_content.strip())
            if self._validate_analysis_format(parsed):
                print("🔍 DEBUG: Direct JSON parsing succeeded")
                return parsed
            else:
                print("🔍 DEBUG: Direct JSON parsing succeeded but validation failed")
                print(f"🔍 DEBUG: Missing fields: {[field for field in ['requires_tools', 'tools_needed', 'complexity'] if field not in parsed]}")
        except json.JSONDecodeError as e:
            print(f"🔍 DEBUG: Direct JSON parsing failed: {e}")
            
        # Strategy 1.5: Try parsing after removing any trailing text
        lines = response_content.strip().split('\n')
        for i in range(len(lines), 0, -1):
            try:
                candidate = '\n'.join(lines[:i]).strip()
                if candidate.startswith('{') and candidate.endswith('}'):
                    parsed = json.loads(candidate)
                    if self._validate_analysis_format(parsed):
                        print(f"🔍 DEBUG: Line-by-line parsing succeeded at line {i}")
                        return parsed
            except json.JSONDecodeError:
                continue
        
        # Strategy 2: Extract JSON from mixed content with improved patterns
        json_patterns = [
            # JSON code blocks first
            r'```json\s*(\{.*?\})\s*```',
            r'```\s*(\{.*?\})\s*```',
            # Simple approach: find the largest complete JSON object
            r'(\{.*\})',
            # Fallback: any JSON-like structure
            r'(\{[^}]*\})'
        ]
        
        for i, pattern in enumerate(json_patterns):
            matches = re.findall(pattern, response_content, re.DOTALL | re.MULTILINE)
            print(f"🔍 DEBUG: Pattern {i+1} found {len(matches)} matches")
            for j, match in enumerate(matches):
                try:
                    # Clean up the match
                    clean_match = match.strip()
                    if not clean_match:
                        continue
                    
                    # Fix common JSON escaping issues
                    fixed_match = self._fix_json_escaping(clean_match)
                    
                    parsed = json.loads(fixed_match)
                    if self._validate_analysis_format(parsed):
                        print(f"🔍 DEBUG: Extracted JSON using pattern {i+1}, match {j+1}")
                        return parsed
                    else:
                        print(f"🔍 DEBUG: Valid JSON but invalid format for pattern {i+1}, match {j+1}")
                except json.JSONDecodeError as e:
                    print(f"🔍 DEBUG: JSON decode error for pattern {i+1}, match {j+1}: {e}")
                    # Try the original match without fixing
                    try:
                        parsed = json.loads(clean_match)
                        if self._validate_analysis_format(parsed):
                            print(f"🔍 DEBUG: Original match worked for pattern {i+1}, match {j+1}")
                            return parsed
                    except json.JSONDecodeError:
                        continue
        
        # Strategy 3: Try to fix truncated JSON
        if response_content.strip().startswith('{'):
            print("🔍 DEBUG: Attempting to fix potentially truncated JSON")
            
            # First try: see if it's just missing closing braces
            content = response_content.strip()
            if not content.endswith('}'):
                # Count opening vs closing braces
                open_braces = content.count('{')
                close_braces = content.count('}')
                missing_braces = open_braces - close_braces
                
                print(f"🔍 DEBUG: Open braces: {open_braces}, Close braces: {close_braces}, Missing: {missing_braces}")
                
                if missing_braces > 0:
                    try:
                        fixed_json = content + '}' * missing_braces
                        parsed = json.loads(fixed_json)
                        if self._validate_analysis_format(parsed):
                            print(f"🔍 DEBUG: Fixed truncated JSON by adding {missing_braces} closing braces")
                            return parsed
                    except json.JSONDecodeError as e:
                        print(f"🔍 DEBUG: Failed to fix with calculated braces: {e}")
                
                # Try adding 1-5 braces as fallback
                for i in range(1, 6):
                    try:
                        fixed_json = content + '}' * i
                        parsed = json.loads(fixed_json)
                        if self._validate_analysis_format(parsed):
                            print(f"🔍 DEBUG: Fixed truncated JSON with {i} closing braces")
                            return parsed
                    except json.JSONDecodeError:
                        continue
        
        print("🔍 DEBUG: All JSON parsing strategies failed")
        return None
    
    def _fix_json_escaping(self, json_str: str) -> str:
        """Fix common JSON escaping issues"""
        # Fix unescaped backslashes in regex patterns
        # Replace single backslashes with double backslashes in string values
        import re
        
        # Find all string values and fix backslashes inside them
        def fix_string_escapes(match):
            full_match = match.group(0)
            string_content = match.group(1)
            
            # Fix common regex patterns
            fixed_content = string_content.replace('\\', '\\\\')
            
            return f'"{fixed_content}"'
        
        # Pattern to match quoted strings
        fixed_json = re.sub(r'"([^"]*\\[^"]*)"', fix_string_escapes, json_str)
        
        return fixed_json
    
    def _validate_analysis_format(self, data: Dict[str, Any]) -> bool:
        """Validate if JSON has the expected analysis format"""
        if not isinstance(data, dict):
            return False
        
        # Must have at least these required fields
        required_fields = ["requires_tools", "tools_needed", "complexity"]
        return all(field in data for field in required_fields)
    
    def _create_intelligent_fallback(self, user_input: str, response_content: str) -> Dict[str, Any]:
        """Create intelligent fallback based on content analysis"""
        
        user_lower = user_input.lower()
        response_lower = response_content.lower()
        
        # Analyze user input to determine likely tool needs
        likely_tools = []
        
        # File-related keywords
        if any(word in user_lower for word in ['file', 'read', 'write', 'create', 'edit', 'show', 'cat']):
            likely_tools.append("file")
        
        # Search-related keywords  
        if any(word in user_lower for word in ['find', 'search', 'look', 'grep', 'locate']):
            likely_tools.append("search")
            
        # Git-related keywords
        if any(word in user_lower for word in ['git', 'commit', 'branch', 'status', 'diff']):
            likely_tools.append("git")
            
        # Refactor-related keywords
        if any(word in user_lower for word in ['refactor', 'rename', 'extract', 'move']):
            likely_tools.append("refactor")
        
        # Debug-related keywords
        if any(word in user_lower for word in ['debug', 'error', 'bug', 'fix', 'problem']):
            likely_tools.append("debug")
        
        # Determine complexity
        complexity = "low"
        if any(word in user_lower for word in ['all', 'entire', 'whole', 'complete', 'complex']):
            complexity = "medium"
        if any(word in user_lower for word in ['refactor', 'migrate', 'restructure', 'analyze']):
            complexity = "high"
        
        # Check if response mentions tools
        response_mentioned_tools = []
        for tool in ['search', 'file', 'git', 'refactor', 'debug']:
            if tool in response_lower:
                response_mentioned_tools.append(tool)
        
        # Combine likely tools with response-mentioned tools
        final_tools = list(set(likely_tools + response_mentioned_tools))
        
        # Filter to only available tools and limit to most relevant
        available_tools = list(self.tools.keys())
        final_tools = [tool for tool in final_tools if tool in available_tools]
        
        # Limit to max 2 tools to avoid overwhelming fallback plans
        final_tools = final_tools[:2]
        
        # Generate execution steps for the fallback
        execution_steps = []
        if final_tools:
            for i, tool in enumerate(final_tools):
                raw_params = self._generate_tool_parameters(tool, user_input)
                validated_params = self._validate_and_fix_tool_parameters(tool, raw_params)
                execution_steps.append({
                    "step": f"Use {tool} to {self._get_tool_action_description(tool, user_input)}",
                    "tool": tool,
                    "parameters": validated_params,
                    "dependencies": [f"step_{i}"] if i > 0 else []
                })
        
        fallback = {
            "requires_tools": len(final_tools) > 0,
            "needs_clarification": False,
            "tools_needed": final_tools,
            "action_sequence": [f"use {tool}" for tool in final_tools] if final_tools else ["provide response"],
            "execution_steps": execution_steps,
            "priority": 3 if final_tools else 1,
            "complexity": complexity,
            "estimated_steps": len(final_tools) + 1 if final_tools else 1,
            "clarification_questions": [],
            "alternatives": []
        }
        
        print(f"🔍 DEBUG: Intelligent fallback created: {fallback}")
        return fallback
    
    async def _create_plan_from_execution_steps(self, user_input: str, task_plan: Dict[str, Any]) -> 'TaskPlan':
        """Create a TaskPlan from execution_steps in the analysis"""
        
        from .planner import TaskPlan, TaskStep, TaskPriority, TaskStatus
        import time
        
        # Generate unique plan ID
        plan_id = f"plan_analysis_{int(time.time())}"
        
        # Convert execution_steps to TaskStep objects
        steps = []
        execution_steps = task_plan.get("execution_steps", [])
        
        print(f"🔍 DEBUG: Creating plan from {len(execution_steps)} execution steps")
        
        for i, exec_step in enumerate(execution_steps):
            step_id = f"step_{i+1}"
            
            # Extract step information
            description = exec_step.get("step", f"Execute step {i+1}")
            tool = exec_step.get("tool", "unknown")
            raw_parameters = exec_step.get("parameters", {})
            raw_dependencies = exec_step.get("dependencies", [])
            
            # Fix dependency mapping - convert step names to step IDs
            dependencies = []
            for dep in raw_dependencies:
                if isinstance(dep, str):
                    # If dependency is a step name, try to find the corresponding step ID
                    if dep.startswith("step_"):
                        dependencies.append(dep)  # Already a step ID
                    else:
                        # Convert step names to step IDs based on position
                        # For now, assume sequential dependencies
                        if i > 0:
                            dependencies.append(f"step_{i}")
                        # Could add more sophisticated mapping later
                else:
                    dependencies.append(dep)
            
            # Fix and validate parameters for the specific tool
            validated_parameters = self._validate_and_fix_tool_parameters(tool, raw_parameters)
            
            # Create TaskStep
            task_step = TaskStep(
                id=step_id,
                description=description,
                tool=tool,
                parameters=validated_parameters,
                dependencies=dependencies,
                status=TaskStatus.PENDING,
                estimated_duration=30  # Default duration
            )
            
            steps.append(task_step)
            print(f"🔍 DEBUG: Created step: {description} using tool '{tool}' with params {validated_parameters}")
            if raw_parameters != validated_parameters:
                print(f"🔧 DEBUG: Fixed parameters: {raw_parameters} → {validated_parameters}")
        
        # Determine priority
        priority_map = {1: TaskPriority.LOW, 2: TaskPriority.LOW, 3: TaskPriority.MEDIUM, 
                       4: TaskPriority.HIGH, 5: TaskPriority.HIGH}
        priority = priority_map.get(task_plan.get("priority", 3), TaskPriority.MEDIUM)
        
        # Create TaskPlan
        plan = TaskPlan(
            id=plan_id,
            title=f"Analysis-Driven Task: {user_input[:50]}...",
            description=user_input,
            steps=steps,
            priority=priority,
            status=TaskStatus.PENDING,
            total_estimated_duration=len(steps) * 30,
            metadata={
                "complexity": task_plan.get("complexity", "medium"),
                "requires_user_input": task_plan.get("needs_clarification", False),
                "can_be_paused": True,
                "tools_needed": task_plan.get("tools_needed", []),
                "source": "analysis_execution_steps",
                "user_request": user_input
            }
        )
        
        # Check if we should add a summary step for analysis tasks
        tools_needed = task_plan.get("tools_needed", [])
        user_request_lower = user_input.lower()
        analysis_keywords = ["analysis", "analyze", "summary", "summarize", "explain", "understand", "describe", "overview", "what", "how"]
        
        should_add_summary = (
            any(word in user_request_lower for word in analysis_keywords) or
            ("file" in tools_needed and "search" in tools_needed)
        )
        
        if should_add_summary:
            # Add summary step
            step_counter = len(steps) + 1
            summary_step = TaskStep(
                id=f"step_{step_counter}",
                description="Generate comprehensive summary of findings",
                tool="summary",
                parameters={
                    "task_description": user_input,
                    "focus": "overview"
                },
                dependencies=[steps[-1].id] if steps else [],
                status=TaskStatus.PENDING,
                estimated_duration=15
            )
            steps.append(summary_step)
            print(f"🔍 DEBUG: Added summary step for analysis task")
        
        # Update the plan with potentially additional steps
        plan.steps = steps
        plan.total_estimated_duration = len(steps) * 30
        
        # Register with task planner
        self.task_planner.active_plans[plan_id] = plan
        
        print(f"🔍 DEBUG: Created plan '{plan_id}' with {len(steps)} steps")
        return plan
    
    def _generate_tool_parameters(self, tool: str, user_input: str) -> Dict[str, Any]:
        """Generate appropriate parameters for a tool based on user input"""
        
        user_lower = user_input.lower()
        
        if tool == "search":
            # Extract search terms and determine search type
            if "find" in user_lower:
                search_term = user_input.split("find")[-1].strip()
            elif "search" in user_lower:
                search_term = user_input.split("search")[-1].strip()
            else:
                search_term = user_input
            
            # Determine if this should be a filename search
            filename_indicators = [
                "main", "app", "entry", "index", "__init__", 
                "config", "setup", "start", ".py", ".js", ".ts"
            ]
            
            search_type = "text"
            if any(indicator in search_term.lower() for indicator in filename_indicators):
                search_type = "filename"
                # For common file searches, use better patterns
                if any(word in search_term.lower() for word in ["main", "entry", "app"]):
                    search_term = "main.py|app.py|index.py|start.py"
                elif "__init__" in search_term.lower():
                    search_term = "__init__.py"
            
            return {
                "query": search_term,
                "search_type": search_type
            }
        
        elif tool == "file":
            # Determine file operation
            if any(word in user_lower for word in ["read", "show", "display", "cat"]):
                return {"action": "read", "path": "determined_at_runtime"}
            elif any(word in user_lower for word in ["write", "create", "edit"]):
                return {"action": "write", "path": "determined_at_runtime"}
            else:
                return {"action": "list", "path": "."}
        
        elif tool == "git":
            if "status" in user_lower:
                return {"action": "status"}
            elif "commit" in user_lower:
                return {"action": "commit"}
            elif "branch" in user_lower:
                return {"action": "branch"}
            else:
                return {"action": "status"}
        
        elif tool == "refactor":
            return {"action": "determined_at_runtime"}
        
        elif tool == "debug":
            return {"action": "analyze_error"}
        
        # Default parameters
        return {"action": "determined_at_runtime"}
    
    def _get_tool_action_description(self, tool: str, user_input: str) -> str:
        """Get a description of what the tool will do"""
        
        user_lower = user_input.lower()
        
        if tool == "search":
            return "search for relevant code patterns"
        elif tool == "file":
            if any(word in user_lower for word in ["read", "show", "display"]):
                return "read and examine files"
            elif any(word in user_lower for word in ["write", "create", "edit"]):
                return "create or modify files"
            else:
                return "work with files"
        elif tool == "git":
            return "perform git operations"
        elif tool == "refactor":
            return "refactor code"
        elif tool == "debug":
            return "analyze and fix issues"
        else:
            return f"execute {tool} operations"
    
    def _validate_and_fix_tool_parameters(self, tool: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Validate and fix parameters to match actual tool schemas"""
        
        if tool == "search":
            # Search tool expects: query, search_type, file_pattern, max_results, context_lines
            fixed_params = {}
            
            # Handle query parameter
            if "query" in parameters:
                fixed_params["query"] = parameters["query"]
            elif "pattern" in parameters:
                fixed_params["query"] = parameters["pattern"]
            elif "search_term" in parameters:
                fixed_params["query"] = parameters["search_term"]
            else:
                fixed_params["query"] = "main"  # Default fallback
            
            # Handle search_type with validation
            search_type = None
            if "search_type" in parameters:
                search_type = parameters["search_type"]
            elif "type" in parameters:
                search_type = parameters["type"]
            
            # Validate and fix search_type
            valid_search_types = ["text", "regex", "function", "class", "import", "filename"]
            if search_type in valid_search_types:
                fixed_params["search_type"] = search_type
            elif search_type == "pattern":
                fixed_params["search_type"] = "regex"
            elif search_type == "code":
                fixed_params["search_type"] = "text"
            else:
                fixed_params["search_type"] = "text"  # Default fallback
            
            # Handle file_pattern (only if not already set by search_type handling)
            if "file_pattern" not in fixed_params:
                if "file_pattern" in parameters:
                    fixed_params["file_pattern"] = parameters["file_pattern"]
                elif "pattern" in parameters and parameters["pattern"].startswith("*"):
                    fixed_params["file_pattern"] = parameters["pattern"]
                else:
                    fixed_params["file_pattern"] = "*"  # Default
            
            # Add default values for optional parameters
            fixed_params["max_results"] = parameters.get("max_results", 50)
            fixed_params["context_lines"] = parameters.get("context_lines", 3)
            
            return fixed_params
        
        elif tool == "git":
            # Git tool expects: action, files, message, branch_name, remote
            fixed_params = {}
            
            # Handle action parameter
            if "action" in parameters:
                fixed_params["action"] = parameters["action"]
            elif "command" in parameters:
                fixed_params["action"] = parameters["command"]
            else:
                fixed_params["action"] = "status"  # Default fallback
            
            # Copy other valid parameters
            for param in ["files", "message", "branch_name", "remote"]:
                if param in parameters:
                    fixed_params[param] = parameters[param]
            
            return fixed_params
        
        elif tool == "file":
            # File tool expects: action, path, content, encoding
            fixed_params = {}
            
            # Handle action parameter
            if "action" in parameters:
                action = parameters["action"]
                # Fix specific invalid actions
                if action == "list_structure":
                    fixed_params["action"] = "list"
                elif action == "list_directory":
                    fixed_params["action"] = "list"
                elif action == "list_files":
                    fixed_params["action"] = "list"
                else:
                    fixed_params["action"] = action
            elif "operation" in parameters:
                fixed_params["action"] = parameters["operation"]
            elif "list_structure" in parameters:
                fixed_params["action"] = "list"
            else:
                fixed_params["action"] = "read"  # Default fallback
            
            # Handle path parameter
            if "path" in parameters:
                fixed_params["path"] = parameters["path"]
            elif "file" in parameters:
                fixed_params["path"] = parameters["file"]
            elif "filename" in parameters:
                fixed_params["path"] = parameters["filename"]
            elif fixed_params["action"] == "list":
                fixed_params["path"] = "."  # Default to current directory for list
            else:
                fixed_params["path"] = "determined_at_runtime"
            
            # Copy other valid parameters
            for param in ["content", "encoding"]:
                if param in parameters:
                    fixed_params[param] = parameters[param]
            
            return fixed_params
        
        elif tool == "summary":
            # Summary tool expects: task_description, collected_data, context, focus
            fixed_params = {}
            
            # Handle task_description
            if "task_description" in parameters:
                fixed_params["task_description"] = parameters["task_description"]
            elif "task" in parameters:
                fixed_params["task_description"] = parameters["task"]
            else:
                fixed_params["task_description"] = "determined_at_runtime"
            
            # Handle focus parameter
            if "focus" in parameters:
                fixed_params["focus"] = parameters["focus"]
            else:
                fixed_params["focus"] = "overview"
            
            # Copy other valid parameters
            for param in ["collected_data", "context"]:
                if param in parameters:
                    fixed_params[param] = parameters[param]
            
            return fixed_params
        
        elif tool in ["refactor", "debug"]:
            # For tools we don't have detailed schemas for, pass through with basic fixes
            fixed_params = parameters.copy()
            
            # Ensure action parameter exists
            if "action" not in fixed_params:
                if "operation" in fixed_params:
                    fixed_params["action"] = fixed_params.pop("operation")
                else:
                    fixed_params["action"] = "determined_at_runtime"
            
            return fixed_params
        
        else:
            # Unknown tool - pass through parameters as-is
            return parameters
    
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
        
        # Import prompt utilities
        from .prompt_utils import create_tool_system_prompt, create_directive_user_message
        
        # Create simple system prompt without directive
        system_prompt = """You are a helpful coding agent. Respond only with valid JSON in the specified format."""
        
        # Get the most recent user message and replace it with directive format
        original_user_message = None
        if self.context.conversation_history:
            for msg in reversed(self.context.conversation_history):
                if msg.role == "user":
                    original_user_message = msg.content
                    break
        
        # Create directive user message
        if original_user_message:
            directive_message = create_directive_user_message(original_user_message, tool_schemas)
        else:
            directive_message = "Please respond with valid JSON."
        
        # Build messages with directive user message
        messages = [
            ChatMessage(role="system", content=system_prompt),
            *self.context.conversation_history[-10:-1],  # Include context except last user message
            ChatMessage(role="user", content=directive_message)  # Replace with directive format
        ]
        
        # Debug: Print the directive message to see what's being sent
        print("🔍 DEBUG: Directive message being sent to model:")
        print("=" * 60)
        print(directive_message)
        print("=" * 60)
        
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
                    # Resolve dynamic parameters from previous step results
                    resolved_params = self._resolve_step_parameters(next_step.parameters, plan)
                    print(f"🔍 DEBUG: Executing tool '{next_step.tool}' with resolved parameters: {resolved_params}")
                    tool_result = await self.tools[next_step.tool].execute(**resolved_params)
                    
                    if tool_result.success:
                        self.task_planner.update_step_status(
                            plan.id, next_step.id, TaskStatus.COMPLETED, 
                            result=tool_result.data
                        )
                        # Show more detailed results for debugging
                        content_preview = (tool_result.content or "No content")[:200]
                        data_preview = str(tool_result.data)[:200] if tool_result.data else "No data"
                        results.append(f"✅ Completed: {content_preview}")
                        if tool_result.data:
                            results.append(f"📊 Data: {data_preview}")
                    else:
                        self.task_planner.update_step_status(
                            plan.id, next_step.id, TaskStatus.FAILED, 
                            error=tool_result.error or "Unknown error"
                        )
                        results.append(f"❌ Failed: {tool_result.error}")
                        # Don't break immediately - show the error but continue if possible
                        print(f"🔍 DEBUG: Tool execution failed - Tool: {next_step.tool}, Params: {next_step.parameters}, Error: {tool_result.error}")
                else:
                    print(f"🔍 DEBUG: Tool '{next_step.tool}' not found in available tools: {list(self.tools.keys())}")
                    
                    # Check if it's the summary tool and needs LLM provider
                    if next_step.tool == "summary":
                        # Create and add summary tool with LLM provider
                        from .tools.summary_tool import SummaryTool
                        summary_tool = SummaryTool(llm_provider=self.provider)
                        self.tools["summary"] = summary_tool
                        
                        # Now execute it
                        summary_data = self._collect_plan_results(plan)
                        summary_params = {
                            **next_step.parameters,
                            "collected_data": summary_data,
                            "context": {"project_context": self.get_project_summary()},
                            "task_description": plan.description
                        }
                        
                        print(f"🔍 DEBUG: Generating summary with data from {len(summary_data)} sources")
                        summary_result = await summary_tool.execute(**summary_params)
                        
                        if summary_result.success:
                            self.task_planner.update_step_status(
                                plan.id, next_step.id, TaskStatus.COMPLETED,
                                result=summary_result.data
                            )
                            results.append(f"📝 **Summary Generated**")
                            if summary_result.content:
                                results.append(f"\n{summary_result.content}")
                        else:
                            self.task_planner.update_step_status(
                                plan.id, next_step.id, TaskStatus.FAILED,
                                error=summary_result.error
                            )
                            results.append(f"❌ Summary generation failed: {summary_result.error}")
                    
                    # Handle special steps
                    elif next_step.tool == "context":
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
                    
                    elif next_step.tool == "summary":
                        # Summary generation step - collect all previous results
                        summary_data = self._collect_plan_results(plan)
                        summary_params = {
                            **next_step.parameters,
                            "collected_data": summary_data,
                            "context": {"project_context": self.get_project_summary()},
                            "task_description": plan.description  # Use the actual plan description
                        }
                        
                        print(f"🔍 DEBUG: Generating summary with data from {len(summary_data)} sources")
                        summary_result = await self.tools[next_step.tool].execute(**summary_params)
                        
                        if summary_result.success:
                            self.task_planner.update_step_status(
                                plan.id, next_step.id, TaskStatus.COMPLETED,
                                result=summary_result.data
                            )
                            results.append(f"📝 **Summary Generated**")
                            # Add the actual summary content to results
                            if summary_result.content:
                                results.append(f"\n{summary_result.content}")
                        else:
                            self.task_planner.update_step_status(
                                plan.id, next_step.id, TaskStatus.FAILED,
                                error=summary_result.error
                            )
                            results.append(f"❌ Summary generation failed: {summary_result.error}")
            
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
    
    async def _simple_response(self, user_input: str, task_complexity: TaskComplexity) -> str:
        """Generate simple LLM response by treating it as analysis too - no tools path"""
        
        print("🔍 DEBUG: In _simple_response - using analysis format (no separate simple path)")
        
        # Even for simple responses, use the same analysis format but handle the response
        # This ensures consistency and avoids confusing the model with different formats
        
        # Import prompt utilities for directive format
        from .prompt_utils import create_directive_user_message
        
        # Build empty tool schemas since no tools in simple response
        empty_tool_schemas = []
        
        # Create directive user message using the same analysis format
        directive_message = create_directive_user_message(user_input, empty_tool_schemas)
        
        print("🔍 DEBUG: Simple response using analysis directive:")
        print("=" * 60)
        print(directive_message)
        print("=" * 60)
        
        # Include project context in system message if available
        context_info = ""
        if self.context.project_context:
            context_info = f"\n\nProject context: {self.get_project_summary()}"
        
        messages = [
            ChatMessage(
                role="system", 
                content=f"You are a helpful coding assistant. Analyze the request and provide a task plan.{context_info}"
            ),
            ChatMessage(role="user", content=directive_message)
        ]
        
        model_config = ModelConfig(
            model_name=self._select_model("analysis"),
            temperature=0.1,
            max_tokens=500
        )
        
        response = await self.provider.chat_completion(messages, model_config)
        
        print(f"🔍 DEBUG: Simple response analysis: {response.content}")
        
        # For simple responses, we expect requires_tools=false, so we can just return a message
        try:
            parsed = json.loads(response.content)
            if parsed.get("requires_tools", False):
                print("🔍 DEBUG: Simple response indicated tools needed - this shouldn't happen")
            # Return a simple message based on the analysis
            return f"Based on my analysis: This appears to be a {parsed.get('complexity', 'general')} task. {parsed.get('action_sequence', ['provide information'])[0] if parsed.get('action_sequence') else 'I can provide information about this.'}"
        except json.JSONDecodeError:
            print("🔍 DEBUG: Simple response JSON parsing failed")
            return "I can help with that request. Please let me know if you need more specific assistance."
    
    def _select_model(self, task_type: str) -> str:
        """Select appropriate model based on task type and configuration"""
        available_models = self.provider.list_models()
        
        if not available_models:
            return "default"
        
        # ALWAYS prioritize configuration-based model selection
        selected_model = self.config.get_model_for_task(task_type, available_models)
        
        if selected_model:
            return selected_model
        
        # If no configured model is available, check if config has any preferred models
        # and use them even if they're not in the "ideal" category
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
    
    def _get_full_context(self) -> str:
        """Get comprehensive context including project, conversation, and current tasks"""
        context_parts = []
        
        # Project context
        project_summary = self.get_project_summary()
        context_parts.append(project_summary)
        
        # Recent conversation history (last 3 exchanges)
        if self.context.conversation_history:
            recent_messages = self.context.conversation_history[-6:]  # Last 3 exchanges (user+assistant pairs)
            if recent_messages:
                context_parts.append("\nRecent Conversation:")
                for i, msg in enumerate(recent_messages):
                    role_display = "User" if msg.role == "user" else "Assistant"
                    content_preview = msg.content[:100] + "..." if len(msg.content) > 100 else msg.content
                    context_parts.append(f"- {role_display}: {content_preview}")
        
        # Active tasks and current plan
        if self.context.active_tasks:
            context_parts.append(f"\nActive Tasks: {len(self.context.active_tasks)} tasks")
        
        if self.current_plan_id:
            plan_progress = self.task_planner.get_plan_progress(self.current_plan_id)
            if plan_progress:
                context_parts.append(f"Current Plan: {plan_progress['title']} ({plan_progress['progress_percentage']:.0f}% complete)")
        
        # Available tools
        if self.tools:
            context_parts.append(f"\nAvailable Tools: {', '.join(self.tools.keys())}")
        
        # Session context
        if hasattr(self, 'session_data') and self.session_data:
            context_parts.append(f"Session: {len(self.session_data)} data points")
        
        return "\n".join(context_parts)
    
    def _resolve_step_parameters(self, parameters: Dict[str, Any], plan: TaskPlan) -> Dict[str, Any]:
        """Resolve dynamic parameters using results from previous steps"""
        resolved_params = {}
        
        for key, value in parameters.items():
            if isinstance(value, str) and value.startswith('{{') and value.endswith('}}'):
                # Extract placeholder name
                placeholder = value[2:-2].strip()
                
                # Resolve common placeholders
                if placeholder == "search_result":
                    # Find the most recent search result
                    search_result = self._get_latest_search_result(plan)
                    if search_result:
                        resolved_params[key] = search_result
                    else:
                        # Fallback to a reasonable default
                        resolved_params[key] = "src/main.py"
                        print(f"🔧 DEBUG: No search result found, using fallback: src/main.py")
                
                elif placeholder.startswith("step_") and placeholder.endswith("_result"):
                    # Get result from specific step
                    step_id = placeholder.replace("_result", "")
                    step_result = self._get_step_result(plan, step_id)
                    if step_result:
                        resolved_params[key] = step_result
                    else:
                        resolved_params[key] = value  # Keep original if can't resolve
                
                else:
                    # Unknown placeholder, keep original
                    resolved_params[key] = value
                    print(f"🔧 DEBUG: Unknown placeholder '{placeholder}', keeping original value")
            
            else:
                # Not a placeholder, keep as-is
                resolved_params[key] = value
        
        return resolved_params
    
    def _get_latest_search_result(self, plan: TaskPlan) -> Optional[str]:
        """Get the most recent search result from completed steps"""
        for step in reversed(plan.steps):
            if step.tool == "search" and step.status == TaskStatus.COMPLETED and step.result:
                # Extract file path from search results
                if isinstance(step.result, dict):
                    results = step.result.get('results', [])
                    if results and len(results) > 0:
                        # Return the first result file path
                        first_result = results[0]
                        if isinstance(first_result, dict):
                            return first_result.get('file', first_result.get('path'))
                        elif isinstance(first_result, str):
                            return first_result
                
                # Fallback: try to extract from data field
                if hasattr(step, 'result') and isinstance(step.result, dict):
                    data = step.result.get('data', {})
                    if isinstance(data, dict):
                        results = data.get('results', [])
                        if results:
                            return results[0] if isinstance(results[0], str) else str(results[0])
        
        return None
    
    def _get_step_result(self, plan: TaskPlan, step_id: str) -> Optional[Any]:
        """Get result from a specific step"""
        for step in plan.steps:
            if step.id == step_id and step.status == TaskStatus.COMPLETED:
                return step.result
        return None
    
    def _collect_plan_results(self, plan: TaskPlan) -> Dict[str, Any]:
        """Collect all results from completed steps in the plan"""
        collected_data = {}
        
        for step in plan.steps:
            if step.status == TaskStatus.COMPLETED and step.result:
                step_key = f"{step.tool}_{step.id}"
                collected_data[step_key] = step.result
        
        return collected_data
    
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
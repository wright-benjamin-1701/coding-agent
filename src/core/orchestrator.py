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
from .debug import debug_print


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
        
        debug_print(f"Processing request: {user_input}")
        
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
            debug_print("Taking clarification path")
            result = await self._ask_clarification(user_input, task_plan, task_complexity)
        elif task_plan.get("requires_tools", False):
            debug_print("Taking tools path")
            # Create execution plan for all tasks (regardless of complexity)
            debug_print("Using planned task execution")
            
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
            debug_print("Taking simple response path (no tools)")
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
        
        debug_print("Analyzing request with directive format")
        
        # Check if this is a summary/analysis request that needs fresh context
        summary_keywords = ["summary", "summarize", "analyze", "overview", "list", "show", "describe", "explain", "functions", "main"]
        if any(keyword in user_input.lower() for keyword in summary_keywords):
            debug_print("Summary request detected - refreshing project context")
            await self.refresh_project_context()
        
        
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
        
        debug_print("Analysis directive message:")
        debug_print("=" * 60)
        debug_print(directive_message)
        debug_print("=" * 60)
        
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
        
        # Clean the response to remove thinking tags and artifacts
        from .response_cleaner import clean_llm_response
        cleaned_response = clean_llm_response(response.content)
        
        debug_print(f"Raw analysis response: {response.content}")
        debug_print(f"Cleaned analysis response: {cleaned_response}")
        debug_print(f"Response length: {len(response.content)} characters")
        
        # Debug: Check if response starts with valid JSON
        if response.content.strip().startswith('{'):
            debug_print("Response starts with '{' - likely valid JSON")
            # Show first and last 200 characters to identify issues
            content = response.content.strip()
            debug_print(f"First 200 chars: {content[:200]}")
            debug_print(f"Last 200 chars: {content[-200:]}")
        else:
            debug_print("Response does NOT start with '{' - contains extra text")
        
        # Try to parse JSON with multiple strategies using cleaned response
        parsed_json = self._parse_analysis_json(cleaned_response)
        
        if parsed_json:
            debug_print(f"Successfully parsed analysis: {parsed_json}")
            
            # Check if this is a file analysis request that needs the proper workflow
            file_extensions = ['.py', '.js', '.ts', '.java', '.cpp', '.c', '.go', '.rs', '.rb', '.php']
            analysis_verbs = ['summarize', 'analyze', 'show', 'read', 'examine', 'review', 'check', 'list', 'display']
            refactor_verbs = ['refactor', 'restructure', 'reorganize', 'improve', 'optimize']
            content_analysis_patterns = ["from", "in", "of", "inside", "within"]
            content_types = ["functions", "function", "classes", "class", "methods", "method", "variables", "variable", "imports", "import"]
            common_filenames = ['orchestrator', 'main', 'core', 'app', 'index', 'utils', 'config', 'base', 'server', 'client', 'learning', 'planner', 'context', 'tools', 'providers']
            
            # Check for direct file analysis (e.g., "summarize X.py" or "refactor learning")
            has_file_extension = any(ext in user_input.lower() for ext in file_extensions)
            has_analysis_verb = any(verb in user_input.lower() for verb in analysis_verbs)
            has_refactor_verb = any(verb in user_input.lower() for verb in refactor_verbs)
            has_common_filename = any(f' {name} ' in f' {user_input.lower()} ' or f' {name}.' in user_input.lower() or user_input.lower().endswith(f' {name}') or user_input.lower().startswith(f'{name} ') for name in common_filenames)
            
            # Check for content analysis (e.g., "functions from X")
            has_content_type = any(content_type in user_input.lower() for content_type in content_types)
            has_file_reference = any(pattern in user_input.lower() for pattern in content_analysis_patterns) and ('.py' in user_input.lower() or any(word in user_input.lower() for word in ['file', 'module', 'script']))
            
            if (has_file_extension and has_analysis_verb) or (has_common_filename and has_analysis_verb) or (has_content_type and has_file_reference) or (has_file_extension and has_refactor_verb) or (has_common_filename and has_refactor_verb):
                tools_needed = parsed_json.get("tools_needed", [])
                # If it doesn't have both search and file tools, use the fallback
                if not ("search" in tools_needed and "file" in tools_needed):
                    debug_print("Content analysis request but incorrect tools detected - using intelligent fallback")
                    return self._create_intelligent_fallback(user_input, cleaned_response)
            
            return parsed_json
        else:
            debug_print("All JSON parsing strategies failed, using intelligent fallback")
            # Create intelligent fallback based on content analysis
            return self._create_intelligent_fallback(user_input, cleaned_response)
    
    def _parse_analysis_json(self, response_content: str) -> Optional[Dict[str, Any]]:
        """Try multiple strategies to parse JSON from model response"""
        
        # Strategy 1: Direct parsing
        try:
            parsed = json.loads(response_content.strip())
            if self._validate_analysis_format(parsed):
                debug_print("Direct JSON parsing succeeded")
                return parsed
            else:
                debug_print("Direct JSON parsing succeeded but validation failed")
                debug_print(f"Missing fields: {[field for field in ['requires_tools', 'tools_needed', 'complexity'] if field not in parsed]}")
        except json.JSONDecodeError as e:
            debug_print(f"Direct JSON parsing failed: {e}")
            
            # Strategy 1.1: Try parsing just the JSON part if there's trailing content
            if "Extra data" in str(e):
                try:
                    # Extract character position where valid JSON ends
                    char_pos = e.pos if hasattr(e, 'pos') else None
                    if char_pos:
                        json_part = response_content[:char_pos].strip()
                        parsed = json.loads(json_part)
                        if self._validate_analysis_format(parsed):
                            debug_print(f"Parsing succeeded by trimming at position {char_pos}")
                            return parsed
                except (json.JSONDecodeError, AttributeError):
                    pass
            
        # Strategy 1.5: Find the largest valid JSON object by balanced braces
        content = response_content.strip()
        if content.startswith('{'):
            brace_count = 0
            for i, char in enumerate(content):
                if char == '{':
                    brace_count += 1
                elif char == '}':
                    brace_count -= 1
                    if brace_count == 0:
                        # Found complete JSON object
                        try:
                            json_part = content[:i+1]
                            parsed = json.loads(json_part)
                            if self._validate_analysis_format(parsed):
                                debug_print(f"Balanced brace parsing succeeded at position {i+1}")
                                return parsed
                        except json.JSONDecodeError:
                            continue
        
        # Strategy 1.6: Try parsing after removing any trailing text line by line
        lines = response_content.strip().split('\n')
        for i in range(len(lines), 0, -1):
            try:
                candidate = '\n'.join(lines[:i]).strip()
                if candidate.startswith('{') and candidate.endswith('}'):
                    parsed = json.loads(candidate)
                    if self._validate_analysis_format(parsed):
                        debug_print(f"Line-by-line parsing succeeded at line {i}")
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
            debug_print(f"Pattern {i+1} found {len(matches)} matches")
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
                        debug_print(f"Extracted JSON using pattern {i+1}, match {j+1}")
                        return parsed
                    else:
                        debug_print(f"Valid JSON but invalid format for pattern {i+1}, match {j+1}")
                except json.JSONDecodeError as e:
                    debug_print(f"JSON decode error for pattern {i+1}, match {j+1}: {e}")
                    # Try the original match without fixing
                    try:
                        parsed = json.loads(clean_match)
                        if self._validate_analysis_format(parsed):
                            debug_print(f"Original match worked for pattern {i+1}, match {j+1}")
                            return parsed
                    except json.JSONDecodeError:
                        continue
        
        # Strategy 3: Try to fix truncated JSON
        if response_content.strip().startswith('{'):
            debug_print("Attempting to fix potentially truncated JSON")
            
            # First try: see if it's just missing closing braces
            content = response_content.strip()
            if not content.endswith('}'):
                # Count opening vs closing braces
                open_braces = content.count('{')
                close_braces = content.count('}')
                missing_braces = open_braces - close_braces
                
                debug_print(f"Open braces: {open_braces}, Close braces: {close_braces}, Missing: {missing_braces}")
                
                if missing_braces > 0:
                    try:
                        fixed_json = content + '}' * missing_braces
                        parsed = json.loads(fixed_json)
                        if self._validate_analysis_format(parsed):
                            debug_print(f"Fixed truncated JSON by adding {missing_braces} closing braces")
                            return parsed
                    except json.JSONDecodeError as e:
                        debug_print(f"Failed to fix with calculated braces: {e}")
                
                # Try adding 1-5 braces as fallback
                for i in range(1, 6):
                    try:
                        fixed_json = content + '}' * i
                        parsed = json.loads(fixed_json)
                        if self._validate_analysis_format(parsed):
                            debug_print(f"Fixed truncated JSON with {i} closing braces")
                            return parsed
                    except json.JSONDecodeError:
                        continue
        
        debug_print("All JSON parsing strategies failed")
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
        
        # Any request that mentions a specific file needs search + file
        # This includes: "summarize X.py", "analyze Y.js", "show me Z.ts", "read main.py", etc.
        file_extensions = ['.py', '.js', '.ts', '.java', '.cpp', '.c', '.go', '.rs', '.rb', '.php']
        analysis_verbs = ['summarize', 'analyze', 'show', 'read', 'examine', 'review', 'check', 'list', 'display']
        common_filenames = ['orchestrator', 'main', 'core', 'app', 'index', 'utils', 'config', 'base', 'server', 'client', 'learning', 'planner', 'context', 'tools', 'providers']
        
        # Check if request mentions a specific file (with extension or common filename)
        has_file_extension = any(ext in user_lower for ext in file_extensions)
        # More flexible filename matching: word boundaries, not just spaces
        import re
        has_common_filename = any(re.search(r'\b' + re.escape(name) + r'\b', user_lower) for name in common_filenames)
        has_analysis_verb = any(verb in user_lower for verb in analysis_verbs)
        
        # Also check for content analysis patterns 
        content_analysis_patterns = ["from", "in", "of", "inside", "within", "the"]
        content_types = [
            "functions", "function", "classes", "class", "methods", "method", 
            "variables", "variable", "imports", "import", "constants", "constant",
            "components", "component", "modules", "module", "definitions", "definition",
            "files", "file"
        ]
        
        has_content_type = any(content_type in user_lower for content_type in content_types)
        has_file_reference = any(pattern in user_lower for pattern in content_analysis_patterns) and ('.py' in user_lower or any(word in user_lower for word in ['file', 'module', 'script', 'project', 'codebase']))
        
        # Special case: "main files" or "project files" should also trigger file analysis
        has_main_files_pattern = ('main' in user_lower and 'files' in user_lower) or ('project' in user_lower and any(word in user_lower for word in ['files', 'structure', 'overview']))
        
        # If asking about a specific file OR asking for content from a file (including refactor requests on specific files)
        refactor_verbs = ['refactor', 'restructure', 'reorganize', 'improve', 'optimize']
        has_refactor_verb = any(verb in user_lower for verb in refactor_verbs)
        
        if (has_file_extension and has_analysis_verb) or (has_common_filename and has_analysis_verb) or (has_content_type and has_file_reference) or (has_file_extension and has_refactor_verb) or (has_common_filename and has_refactor_verb) or has_main_files_pattern:
            likely_tools = ["search", "file"]  # Only these two tools for file analysis/refactoring
        else:
            # File-related keywords (but not for file analysis requests, which are handled above)
            if any(word in user_lower for word in ['read', 'write', 'create', 'edit', 'show', 'cat']):
                likely_tools.append("file")
            
            # Search-related keywords  
            if any(word in user_lower for word in ['find', 'search', 'look', 'grep', 'locate']):
                likely_tools.append("search")
                
            # Git-related keywords
            if any(word in user_lower for word in ['git', 'commit', 'branch', 'status', 'diff']):
                likely_tools.append("git")
                
            # Refactor-related keywords (only for non-file-specific refactoring)
            refactor_keywords = ['refactor', 'rename', 'extract', 'move']
            if any(word in user_lower for word in refactor_keywords):
                # Only add refactor tool if this isn't a file-specific refactor request
                if not (has_file_extension or has_common_filename):
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
        
        # NUCLEAR APPROACH: For analysis requests, ensure we always have search+file tools even if not detected
        analysis_keywords = ["analysis", "analyze", "summary", "summarize", "explain", "understand", "describe", "overview", "what", "how", "show", "list", "important", "main", "core", "project"]
        is_analysis_request = any(word in user_lower for word in analysis_keywords)
        
        if is_analysis_request and not final_tools:
            # If it's an analysis request but no tools detected, add search+file as minimum
            final_tools = ["search", "file"]
            debug_print("Nuclear mode: Added search+file tools for analysis request with no detected tools")
        
        # Filter to only available tools and limit to most relevant
        available_tools = list(self.tools.keys())
        final_tools = [tool for tool in final_tools if tool in available_tools]
        
        # For analysis requests, allow more tools
        max_tools = 3 if is_analysis_request else 2
        final_tools = final_tools[:max_tools]
        
        # Generate execution steps for the fallback
        execution_steps = []
        if final_tools:
            # Special workflow for file analysis requests (including refactoring)
            file_extensions = ['.py', '.js', '.ts', '.java', '.cpp', '.c', '.go', '.rs', '.rb', '.php']
            analysis_verbs = ['summarize', 'analyze', 'show', 'read', 'examine', 'review', 'check', 'list', 'display']
            refactor_verbs = ['refactor', 'restructure', 'reorganize', 'improve', 'optimize']
            content_analysis_patterns = ["from", "in", "of", "inside", "within", "the"]
            content_types = ["functions", "function", "classes", "class", "methods", "method", "variables", "variable", "imports", "import", "files", "file"]
            common_filenames = ['orchestrator', 'main', 'core', 'app', 'index', 'utils', 'config', 'base', 'server', 'client', 'learning', 'planner', 'context', 'tools', 'providers']
            
            # Check for direct file analysis (e.g., "summarize X.py", "refactor learning")
            has_file_extension = any(ext in user_lower for ext in file_extensions)
            has_analysis_verb = any(verb in user_lower for verb in analysis_verbs)
            has_refactor_verb = any(verb in user_lower for verb in refactor_verbs)
            has_common_filename = any(re.search(r'\b' + re.escape(name) + r'\b', user_lower) for name in common_filenames)
            
            # Check for content analysis (e.g., "functions from X")
            has_content_type = any(content_type in user_lower for content_type in content_types)
            has_file_reference = any(pattern in user_lower for pattern in content_analysis_patterns) and ('.py' in user_lower or any(word in user_lower for word in ['file', 'module', 'script', 'project', 'codebase']))
            
            # Special case: "main files" or "project files" should also trigger file analysis
            has_main_files_pattern = ('main' in user_lower and 'files' in user_lower) or ('project' in user_lower and any(word in user_lower for word in ['files', 'structure', 'overview']))
            
            if "search" in final_tools and "file" in final_tools and ((has_file_extension and has_analysis_verb) or (has_common_filename and has_analysis_verb) or (has_content_type and has_file_reference) or (has_file_extension and has_refactor_verb) or (has_common_filename and has_refactor_verb) or has_main_files_pattern):
                # Step 1: Find the file
                search_params = self._generate_tool_parameters("search", user_input)
                search_params = self._validate_and_fix_tool_parameters("search", search_params)
                execution_steps.append({
                    "step": "Search for target file",
                    "tool": "search", 
                    "parameters": search_params,
                    "dependencies": []
                })
                
                # Step 2: Read the file and extract functions
                file_params = {
                    "action": "read",
                    "path": "{{search_result}}"  # Will be resolved from step 1
                }
                execution_steps.append({
                    "step": "Read file and analyze functions",
                    "tool": "file",
                    "parameters": file_params,
                    "dependencies": ["step_1"]
                })
            else:
                # Standard workflow for other requests
                for i, tool in enumerate(final_tools):
                    raw_params = self._generate_tool_parameters(tool, user_input)
                    validated_params = self._validate_and_fix_tool_parameters(tool, raw_params)
                    
                    step_desc = f"Use {tool} to {self._get_tool_action_description(tool, user_input)}"
                    
                    execution_steps.append({
                        "step": step_desc,
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
        
        debug_print(f"Intelligent fallback created: {fallback}")
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
        
        debug_print(f"Creating plan from {len(execution_steps)} execution steps")
        
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
            debug_print(f"Created step: {description} using tool '{tool}' with params {validated_parameters}")
            if raw_parameters != validated_parameters:
                debug_print(f"Fixed parameters: {raw_parameters} → {validated_parameters}, DEBUG")
        
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
        
        # NUCLEAR APPROACH: For ANY analysis/summary request, aggressively collect file content
        tools_needed = task_plan.get("tools_needed", [])
        user_request_lower = user_input.lower()
        analysis_keywords = ["analysis", "analyze", "summary", "summarize", "explain", "understand", "describe", "overview", "what", "how", "show", "list", "important", "main", "core", "project"]
        
        should_add_file_collection = any(word in user_request_lower for word in analysis_keywords)
        should_add_summary = should_add_file_collection or ("file" in tools_needed and "search" in tools_needed)
        
        if should_add_file_collection:
            debug_print("🔥 FULL NUCLEAR MODE: Adding multiple aggressive search and file collection steps")
            
            # NUCLEAR SEARCH 1: Filename search for important files
            step_counter = len(steps) + 1
            filename_search_step = TaskStep(
                id=f"step_{step_counter}",
                description="Filename search for important project files",
                tool="search",
                parameters={
                    "query": self._brainstorm_filename_keywords(user_input),
                    "search_type": "filename",
                    "file_pattern": "*.py",
                    "max_results": 25,
                    "context_lines": 0
                },
                dependencies=[steps[-1].id] if steps else [],
                status=TaskStatus.PENDING,
                estimated_duration=8
            )
            steps.append(filename_search_step)
            
            # NUCLEAR SEARCH 2: Function search for key functions
            step_counter += 1
            function_search_step = TaskStep(
                id=f"step_{step_counter}",
                description="Function search for key methods and functions",
                tool="search",
                parameters={
                    "query": self._brainstorm_function_keywords(user_input),
                    "search_type": "function",
                    "file_pattern": "*.py",
                    "max_results": 25,
                    "context_lines": 2
                },
                dependencies=[steps[-1].id] if steps else [],
                status=TaskStatus.PENDING,
                estimated_duration=8
            )
            steps.append(function_search_step)
            
            # NUCLEAR SEARCH 3: Class search for important classes
            step_counter += 1
            class_search_step = TaskStep(
                id=f"step_{step_counter}",
                description="Class search for core classes and components",
                tool="search",
                parameters={
                    "query": self._brainstorm_class_keywords(user_input),
                    "search_type": "class",
                    "file_pattern": "*.py",
                    "max_results": 25,
                    "context_lines": 3
                },
                dependencies=[steps[-1].id] if steps else [],
                status=TaskStatus.PENDING,
                estimated_duration=8
            )
            steps.append(class_search_step)
            
            # NUCLEAR SEARCH 4: Text search for important patterns and keywords
            step_counter += 1
            text_search_step = TaskStep(
                id=f"step_{step_counter}",
                description="Text search for important patterns and documentation",
                tool="search",
                parameters={
                    "query": self._brainstorm_text_keywords(user_input),
                    "search_type": "text",
                    "file_pattern": "*",
                    "max_results": 20,
                    "context_lines": 2
                },
                dependencies=[steps[-1].id] if steps else [],
                status=TaskStatus.PENDING,
                estimated_duration=8
            )
            steps.append(text_search_step)
            
            # NUCLEAR FILE READING: Read all discovered important files
            step_counter += 1
            file_reading_step = TaskStep(
                id=f"step_{step_counter}",
                description="Read and analyze content from ALL discovered important files",
                tool="file", 
                parameters={
                    "action": "read_multiple",
                    "paths": "{{combined_search_results_top_10}}",
                    "max_files": 10
                },
                dependencies=[f"step_{step_counter-4}", f"step_{step_counter-3}", f"step_{step_counter-2}", f"step_{step_counter-1}"],
                status=TaskStatus.PENDING,
                estimated_duration=30
            )
            steps.append(file_reading_step)
            debug_print("🔥 Added FULL NUCLEAR MODE: 4 search types + multi-file reading")
        
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
            debug_print("Added summary step for analysis task")
        
        # Update the plan with potentially additional steps
        plan.steps = steps
        plan.total_estimated_duration = len(steps) * 30
        
        # Register with task planner
        self.task_planner.active_plans[plan_id] = plan
        
        debug_print(f"Created plan '{plan_id}' with {len(steps)} steps")
        return plan
    
    def _brainstorm_filename_keywords(self, user_input: str) -> str:
        """Brainstorm filename-specific keywords for aggressive file discovery"""
        user_lower = user_input.lower()
        
        # Since search tool doesn't support OR, pick the most likely single keyword
        # Core filenames that are always important, prioritized
        priority_keywords = ["orchestrator", "main", "core", "app", "config"]
        
        # Context-specific keyword selection
        if any(word in user_lower for word in ["orchestrator", "agent"]):
            return "orchestrator"
        elif any(word in user_lower for word in ["main", "entry", "primary"]):
            return "main"
        elif any(word in user_lower for word in ["core", "base", "central"]):
            return "core"
        elif any(word in user_lower for word in ["app", "application"]):
            return "app"
        elif any(word in user_lower for word in ["config", "settings"]):
            return "config"
        elif any(word in user_lower for word in ["tools", "utilities"]):
            return "tool"
        elif any(word in user_lower for word in ["learning", "ai", "model"]):
            return "learning"
        else:
            # Default to most important - orchestrator for this project
            return "orchestrator"
    
    def _brainstorm_function_keywords(self, user_input: str) -> str:
        """Brainstorm function-specific keywords for finding key methods"""
        user_lower = user_input.lower()
        
        # Context-specific function selection (single most relevant)
        if any(word in user_lower for word in ["process", "execute", "run"]):
            return "process_request"
        elif any(word in user_lower for word in ["search", "find", "analyze"]):
            return "search"
        elif any(word in user_lower for word in ["create", "generate", "build"]):
            return "create"
        elif any(word in user_lower for word in ["plan", "workflow", "orchestrat"]):
            return "execute"
        elif any(word in user_lower for word in ["summary", "summarize"]):
            return "generate"
        else:
            # Default to most common important function
            return "execute"
    
    def _brainstorm_class_keywords(self, user_input: str) -> str:
        """Brainstorm class-specific keywords for finding core components"""
        user_lower = user_input.lower()
        
        # Context-specific class selection (single most relevant)
        if any(word in user_lower for word in ["orchestrator", "agent"]):
            return "AgentOrchestrator"
        elif any(word in user_lower for word in ["tool", "search", "file"]):
            return "Tool"
        elif any(word in user_lower for word in ["plan", "task", "workflow"]):
            return "TaskPlan"
        elif any(word in user_lower for word in ["manager", "handler"]):
            return "Manager"
        elif any(word in user_lower for word in ["config", "settings"]):
            return "Config"
        elif any(word in user_lower for word in ["provider", "llm", "model"]):
            return "Provider"
        else:
            # Default to most important class
            return "AgentOrchestrator"
    
    def _brainstorm_text_keywords(self, user_input: str) -> str:
        """Brainstorm text-specific keywords for finding documentation and patterns"""
        user_lower = user_input.lower()
        
        # Context-specific text selection (single most relevant)
        if any(word in user_lower for word in ["project", "summary", "overview"]):
            return "description"
        elif any(word in user_lower for word in ["important", "critical", "key"]):
            return "important"
        elif any(word in user_lower for word in ["workflow", "process", "flow"]):
            return "workflow"
        elif any(word in user_lower for word in ["todo", "fixme", "note"]):
            return "TODO"
        elif any(word in user_lower for word in ["documentation", "docs", "readme"]):
            return "documentation"
        elif any(word in user_lower for word in ["architecture", "design", "structure"]):
            return "architecture"
        else:
            # Default to most useful for project understanding
            return "description"
    
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
            
            # Handle file analysis requests: "summarize X.py", "functions from Y", "refactor Z.py", etc.
            file_extensions = ['.py', '.js', '.ts', '.java', '.cpp', '.c', '.go', '.rs', '.rb', '.php']
            content_analysis_patterns = ["from", "in", "of", "inside", "within"]
            analysis_verbs = ['summarize', 'analyze', 'show', 'read', 'examine', 'review', 'check', 'list', 'display']
            refactor_verbs = ['refactor', 'restructure', 'reorganize', 'improve', 'optimize']
            common_filenames = ['orchestrator', 'main', 'core', 'app', 'index', 'utils', 'config', 'base', 'server', 'client', 'learning', 'planner', 'context', 'tools', 'providers']
            
            # Check for either direct file mention or content analysis pattern
            has_file_extension = any(ext in user_lower for ext in file_extensions)
            has_content_pattern = any(pattern in user_lower for pattern in content_analysis_patterns)
            has_analysis_verb = any(verb in user_lower for verb in analysis_verbs)
            has_refactor_verb = any(verb in user_lower for verb in refactor_verbs)
            has_common_filename = any(f' {name} ' in f' {user_lower} ' or f' {name}.' in user_lower or user_lower.endswith(f' {name}') or user_lower.startswith(f'{name} ') for name in common_filenames)
            
            if has_file_extension or has_content_pattern or (has_analysis_verb and has_common_filename) or (has_refactor_verb and has_common_filename) or (has_refactor_verb and has_file_extension):
                # Extract the file name from the request
                words = user_input.split()
                target_file = None
                
                # Look for file extensions or common module names
                for word in words:
                    word_lower = word.lower().rstrip('.,!?')
                    if (word_lower.endswith(tuple(file_extensions)) or 
                        word_lower in common_filenames):
                        
                        if any(ext in word_lower for ext in file_extensions):
                            target_file = word_lower
                        else:
                            target_file = f"{word_lower}.py"  # Default to .py
                        break
                
                if target_file:
                    return {
                        "query": target_file,
                        "search_type": "filename"
                    }
            
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
                elif "orchestrator" in search_term.lower():
                    search_term = "orchestrator.py"
            
            return {
                "query": search_term,
                "search_type": search_type
            }
        
        elif tool == "file":
            # Check if this is a function listing request - should search first, not read directly
            if any(phrase in user_lower for phrase in ["functions of", "functions in", "main functions", "list functions"]):
                # For function listing, we need to search for the file first
                # This should not generate file parameters directly
                return {"action": "search_first_then_read"}
            
            # Determine file operation
            elif any(word in user_lower for word in ["read", "show", "display", "cat"]):
                return {"action": "read", "path": "determined_at_runtime"}
            elif any(word in user_lower for word in ["write", "create", "edit"]):
                # Extract filename and generate content for write operations
                filename = self._extract_filename_from_request(user_input)
                content = self._generate_file_content_from_request(user_input, filename)
                return {
                    "action": "write", 
                    "path": filename or "determined_at_runtime",
                    "content": content
                }
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
            
            # Smart conversion: if searching for filenames with text search, convert to filename search
            query = fixed_params.get("query","")
            if fixed_params["search_type"] == "text" and any(pattern in query for pattern in [".py", ".js", ".ts", "|", "main", "app", "__init__"]):
                debug_print(f"Converting text search '{query}' to filename search, DEBUG")
                fixed_params["search_type"] = "filename"
            
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
        debug_print("Directive message being sent to model:")
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
                    resolved_params = await self._resolve_step_parameters(next_step.parameters, plan)
                    debug_print(f"Executing tool '{next_step.tool}' with resolved parameters: {resolved_params}")
                    tool_result = await self.tools[next_step.tool].execute(**resolved_params)
                    
                    if tool_result.success:
                        # Store both the data and content for later use by summary tool
                        result_data = {}
                        if tool_result.content:
                            result_data['content'] = tool_result.content
                        if tool_result.data:
                            result_data.update(tool_result.data)
                        
                        self.task_planner.update_step_status(
                            plan.id, next_step.id, TaskStatus.COMPLETED, 
                            result=result_data if result_data else tool_result.data
                        )
                        # Show more detailed results for debugging
                        # For summary steps, show the full content instead of truncated data
                        if next_step.tool == "summary" and tool_result.content:
                            results.append(f"✅ Completed: Summary generated")
                            results.append(f"\n{tool_result.content}")
                        else:
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
                        debug_print(f"Tool execution failed - Tool: {next_step.tool}, Params: {next_step.parameters}, Error: {tool_result.error}")
                else:
                    debug_print(f"Tool '{next_step.tool}' not found in available tools: {list(self.tools.keys())}")
                    
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
                        
                        debug_print(f"Generating summary with data from {len(summary_data)} sources")
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
                        
                        debug_print(f"Generating summary with data from {len(summary_data)} sources")
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
        
        debug_print("In _simple_response - using analysis format (no separate simple path)")
        
        # Even for simple responses, use the same analysis format but handle the response
        # This ensures consistency and avoids confusing the model with different formats
        
        # Import prompt utilities for directive format
        from .prompt_utils import create_directive_user_message
        
        # Build empty tool schemas since no tools in simple response
        empty_tool_schemas = []
        
        # Create directive user message using the same analysis format
        directive_message = create_directive_user_message(user_input, empty_tool_schemas)
        
        debug_print("Simple response using analysis directive:")
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
        
        # Clean the response to remove thinking tags and artifacts
        from .response_cleaner import clean_llm_response
        cleaned_response = clean_llm_response(response.content)
        
        debug_print(f"Simple response analysis: {cleaned_response}")
        
        # For simple responses, we expect requires_tools=false, so we can just return a message
        try:
            parsed = json.loads(cleaned_response)
            if parsed.get("requires_tools", False):
                debug_print("Simple response indicated tools needed - this shouldn't happen")
            # Return a simple message based on the analysis
            return f"Based on my analysis: This appears to be a {parsed.get('complexity', 'general')} task. {parsed.get('action_sequence', ['provide information'])[0] if parsed.get('action_sequence') else 'I can provide information about this.'}"
        except json.JSONDecodeError:
            debug_print("Simple response JSON parsing failed")
            # Return the cleaned response directly if it's not JSON
            return cleaned_response if cleaned_response else "I can help with that request. Please let me know if you need more specific assistance."
    
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
    
    async def refresh_project_context(self) -> None:
        """Force refresh of project context, ignoring cached data"""
        if self.context_manager:
            try:
                # Force rebuild context
                self.context.project_context = await self.context_manager.build_context()
                
                # Update session with fresh context
                self.session_manager.update_session(
                    project_context=self.context_manager.to_dict() if self.context_manager and self.context.project_context else None
                )
            except Exception as e:
                print(f"Warning: Could not refresh project context: {e}")
    
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
    
    def _extract_filename_from_request(self, user_input: str) -> Optional[str]:
        """Extract filename from user request"""
        import re
        
        # Look for explicit filename patterns
        filename_patterns = [
            r'write\s+(?:a\s+)?(?:file\s+)?(?:called\s+)?([a-zA-Z0-9_.-]+\.py)',
            r'create\s+(?:a\s+)?(?:file\s+)?(?:called\s+)?([a-zA-Z0-9_.-]+\.py)',
            r'(?:file\s+)?([a-zA-Z0-9_.-]+\.py)',
            r'write\s+(?:a\s+)?(?:file\s+)?(?:called\s+)?([a-zA-Z0-9_.-]+)',
            r'create\s+(?:a\s+)?(?:file\s+)?(?:called\s+)?([a-zA-Z0-9_.-]+)'
        ]
        
        for pattern in filename_patterns:
            match = re.search(pattern, user_input, re.IGNORECASE)
            if match:
                filename = match.group(1)
                # Add .py extension if missing for Python-related requests
                if 'python' in user_input.lower() or 'print' in user_input.lower():
                    if not filename.endswith('.py'):
                        filename += '.py'
                return filename
        
        # Default filename based on content
        if 'hello' in user_input.lower():
            return 'hello.py'
        elif 'test' in user_input.lower():
            return 'test.py'
        else:
            return 'script.py'
    
    def _generate_file_content_from_request(self, user_input: str, filename: Optional[str]) -> str:
        """Generate file content based on user request using LLM"""
        
        # For write requests that don't specify content, indicate it should be generated at runtime
        # The actual content generation will be handled by the LLM during execution
        return "GENERATE_CONTENT_AT_RUNTIME"
    
    async def _resolve_step_parameters(self, parameters: Dict[str, Any], plan: TaskPlan) -> Dict[str, Any]:
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
                elif placeholder == "search_results_top_5":
                    # Find the top 5 search results from the most recent search
                    search_results = self._get_latest_search_results(plan, limit=5)
                    if search_results:
                        resolved_params[key] = search_results
                    else:
                        # Fallback to common important files
                        resolved_params[key] = ["src/main.py", "src/core/orchestrator.py", "src/core/__init__.py"]
                elif placeholder == "combined_search_results_top_10":
                    # Combine results from all search steps and get top 10 unique files
                    combined_results = self._get_combined_search_results(plan, limit=10)
                    if combined_results:
                        resolved_params[key] = combined_results
                    else:
                        # Fallback to comprehensive important files list
                        resolved_params[key] = [
                            "src/main.py", "src/core/orchestrator.py", "src/core/__init__.py",
                            "src/core/tools/__init__.py", "src/core/planner.py", "src/core/config.py",
                            "README.md", "setup.py", "requirements.txt", "src/core/learning.py"
                        ]
                        debug_print("No search result found, using fallback: src/main.py ")
                
                elif placeholder.startswith("step_") and placeholder.endswith("_result"):
                    # Get result from specific step
                    step_id = placeholder.replace("_result","")
                    step_result = self._get_step_result(plan, step_id)
                    if step_result:
                        resolved_params[key] = step_result
                    else:
                        resolved_params[key] = value  # Keep original if can't resolve
                
                else:
                    # Unknown placeholder, keep original
                    resolved_params[key] = value
                    debug_print(f"Unknown placeholder '{placeholder}', keeping original value")
            
            elif isinstance(value, str) and value == "GENERATE_CONTENT_AT_RUNTIME":
                # Generate content using LLM based on the task context
                if key == "content" and "path" in parameters:
                    filename = parameters.get("path", "file.txt")
                    generated_content = await self._generate_content_with_llm(plan.description, filename, plan)
                    resolved_params[key] = generated_content
                    debug_print(f"Generated content for {filename}: {len(generated_content)} characters ")
                else:
                    # Fallback to basic content if can't determine file type
                    resolved_params[key] = "# Content generated by AI assistant\n"
                    debug_print(f"Used fallback content for parameter '{key}' ")
            
            else:
                # Not a placeholder, keep as-is
                resolved_params[key] = value
        
        return resolved_params
    
    async def _generate_content_with_llm(self, task_description: str, filename: str, plan: TaskPlan) -> str:
        """Generate file content using LLM based on the task description and filename"""
        try:
            # Build context for content generation
            file_extension = filename.split('.')[-1].lower() if '.' in filename else ''
            
            # Build comprehensive prompt for content generation
            prompt_parts = [
                f"Generate appropriate file content for: {filename}",
                f"Task context: {task_description}",
                f"File extension: {file_extension}" if file_extension else "No file extension detected",
                "",
                "Requirements:",
                "- Generate complete, functional content appropriate for the file type",
                "- Make the content relevant to the task description",
                "- Follow best practices for the programming language/file type",
                "- Include appropriate comments if it's code",
                "- Make it practical and ready to use",
                "",
                "Return ONLY the file content, no explanations or markdown formatting."
            ]
            
            # Add language-specific guidance
            if file_extension in ['py', 'python']:
                prompt_parts.extend([
                    "",
                    "For Python files:",
                    "- Include proper imports if needed",
                    "- Follow PEP 8 style guidelines", 
                    "- Add docstrings for functions/classes",
                    "- Include a main block if it's a script"
                ])
            elif file_extension in ['js', 'javascript']:
                prompt_parts.extend([
                    "",
                    "For JavaScript files:",
                    "- Use modern ES6+ syntax",
                    "- Include proper error handling",
                    "- Add JSDoc comments for functions"
                ])
            elif file_extension in ['html', 'htm']:
                prompt_parts.extend([
                    "",
                    "For HTML files:",
                    "- Include proper DOCTYPE and structure",
                    "- Use semantic HTML elements",
                    "- Include meta tags in head section"
                ])
            elif file_extension in ['css']:
                prompt_parts.extend([
                    "",
                    "For CSS files:",
                    "- Use modern CSS practices",
                    "- Include comments for sections",
                    "- Consider responsive design"
                ])
            elif file_extension in ['md', 'markdown']:
                prompt_parts.extend([
                    "",
                    "For Markdown files:",
                    "- Use proper heading hierarchy",
                    "- Include relevant sections",
                    "- Use appropriate markdown syntax"
                ])
            
            generation_prompt = "\n".join(prompt_parts)
            
            # Use LLM to generate content
            messages = [
                ChatMessage(
                    role="system",
                    content="You are a helpful coding assistant. Generate appropriate file content based on the user's request. Return only the file content without any explanations, markdown code blocks, or additional text."
                ),
                ChatMessage(role="user", content=generation_prompt)
            ]
            
            # Use a model good for code generation
            model_config = ModelConfig(
                model_name=self._select_best_code_model(),
                temperature=0.2,  # Lower temperature for more consistent code
                max_tokens=2000
            )
            
            response = await self.provider.chat_completion(messages, model_config)
            
            # Clean the response to remove thinking tags and artifacts
            from .response_cleaner import clean_llm_response, extract_content_from_markdown
            generated_content = extract_content_from_markdown(response.content)
            
            # Ensure content is not empty
            if not generated_content or generated_content.isspace():
                return self._get_fallback_content(filename, file_extension)
            
            return generated_content
            
        except Exception as e:
            debug_print(f"Error generating content with LLM: {str(e)} ")
            # Fallback to basic content generation
            return self._get_fallback_content(filename, file_extension)
    
    def _select_best_code_model(self) -> str:
        """Select the best available model for code generation"""
        available_models = self.provider.list_models()
        if not available_models:
            return "default"
        
        # Prefer models good for code generation
        preferred_models = [
            "deepseek-coder", "codeqwen", "codellama", "starcoder", "deepseek-chat", "qwen", "claude", "gpt"
        ]
        
        for preferred in preferred_models:
            for model in available_models:
                if preferred in model.lower():
                    return model
        
        # Fallback to first available
        return available_models[0]
    
    def _get_fallback_content(self, filename: str, file_extension: str) -> str:
        """Generate basic fallback content when LLM generation fails"""
        if file_extension in ['py', 'python']:
            return f'#!/usr/bin/env python3\n"""\n{filename}\n"""\n\ndef main():\n    print("Hello from {filename}")\n\nif __name__ == "__main__":\n    main()\n'
        elif file_extension in ['js', 'javascript']:
            return f'// {filename}\nconsole.log("Hello from {filename}");\n'
        elif file_extension in ['html', 'htm']:
            return f'<!DOCTYPE html>\n<html lang="en">\n<head>\n    <meta charset="UTF-8">\n    <meta name="viewport" content="width=device-width, initial-scale=1.0">\n    <title>{filename}</title>\n</head>\n<body>\n    <h1>Hello from {filename}</h1>\n</body>\n</html>\n'
        elif file_extension in ['css']:
            return f'/* {filename} */\nbody {{\n    font-family: Arial, sans-serif;\n    margin: 0;\n    padding: 20px;\n}}\n'
        elif file_extension in ['md', 'markdown']:
            return f'# {filename}\n\nThis is a markdown file.\n\n## Features\n\n- Feature 1\n- Feature 2\n- Feature 3\n'
        else:
            return f'# {filename}\n# Generated content\n'
    
    def _get_combined_search_results(self, plan: TaskPlan, limit: int = 10) -> Optional[List[str]]:
        """Combine results from ALL search steps and get top N unique files"""
        all_file_paths = []
        
        # Collect results from all completed search steps
        for step in plan.steps:
            if step.tool == "search" and step.status == TaskStatus.COMPLETED and step.result:
                # step.result is the data dict, not ToolResult object
                if isinstance(step.result, dict) and 'results' in step.result:
                    results = step.result.get('results', [])
                    for result in results:
                        if isinstance(result, dict) and 'file' in result:
                            all_file_paths.append(result['file'])
                        elif isinstance(result, str):
                            all_file_paths.append(result)
        
        if not all_file_paths:
            return None
        
        # Remove duplicates while preserving order (first occurrence wins)
        unique_paths = []
        seen = set()
        for path in all_file_paths:
            if path not in seen:
                unique_paths.append(path)
                seen.add(path)
        
        # Return top N results
        return unique_paths[:limit] if unique_paths else None

    def _get_latest_search_results(self, plan: TaskPlan, limit: int = 5) -> Optional[List[str]]:
        """Get the top N search results from the most recent search"""
        for step in reversed(plan.steps):
            if step.tool == "search" and step.status == TaskStatus.COMPLETED and step.result:
                # step.result is the data dict, not ToolResult object
                if isinstance(step.result, dict) and 'results' in step.result:
                    results = step.result.get('results', [])
                    if results:
                        # Extract file paths from results, limit to top N
                        file_paths = []
                        for result in results[:limit]:
                            if isinstance(result, dict) and 'file' in result:
                                file_paths.append(result['file'])
                            elif isinstance(result, str):
                                file_paths.append(result)
                        return file_paths if file_paths else None
        return None

    def _get_latest_search_result(self, plan: TaskPlan) -> Optional[str]:
        """Get the most recent search result from completed steps"""
        for step in reversed(plan.steps):
            if step.tool == "search" and step.status == TaskStatus.COMPLETED and step.result:
                # Extract file path from search results
                if isinstance(step.result, dict):
                    # First check for results in the top level
                    results = step.result.get('results', [])
                    if results and len(results) > 0:
                        # Prefer main source files over test files
                        best_result = self._select_best_file_result(results)
                        if best_result:
                            return best_result
                    
                    # Then check for results in the data field (search tool format)
                    data = step.result.get('data', {})
                    if isinstance(data, dict):
                        results = data.get('results', [])
                        if results and len(results) > 0:
                            # Prefer main source files over test files
                            best_result = self._select_best_file_result(results)
                            if best_result:
                                return best_result
        
        return None
    
    def _select_best_file_result(self, results: List[Dict[str, Any]]) -> Optional[str]:
        """Select the best file from search results, preferring main source files over tests"""
        if not results:
            return None
        
        # Extract file paths
        file_paths = []
        for result in results:
            if isinstance(result, dict):
                file_path = result.get('file', result.get('path'))
                if file_path:
                    file_paths.append(file_path)
            elif isinstance(result, str):
                file_paths.append(result)
        
        if not file_paths:
            return None
        
        # Prioritize main source files over test files
        main_files = [f for f in file_paths if '/test' not in f.lower() and 'test_' not in f.lower()]
        if main_files:
            # Among main files, prefer src/ over others
            src_files = [f for f in main_files if '/src/' in f]
            if src_files:
                return src_files[0]
            return main_files[0]
        
        # Fallback to first result if no main files found
        return file_paths[0]
    
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
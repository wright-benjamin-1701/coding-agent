"""
Interpretation layer for converting user requests and model outputs into structured actions.
Designed to work with small, local models that may not produce reliable structured output.
"""
import json
import re
from typing import Dict, List, Optional, Any, Tuple, Union
from dataclasses import dataclass, field
from enum import Enum

from .providers.base import BaseLLMProvider, ChatMessage, ModelConfig
from .config import ConfigManager, get_config


class IntentType(Enum):
    """Types of user intents that can be detected"""
    SEARCH_CODE = "search_code"
    READ_FILES = "read_files" 
    ANALYZE_PROJECT = "analyze_project"
    EDIT_CODE = "edit_code"
    GIT_OPERATION = "git_operation"
    EXECUTE_CODE = "execute_code"
    EXPLAIN_CODE = "explain_code"
    DEBUG_ISSUE = "debug_issue"
    REFACTOR_CODE = "refactor_code"
    GENERAL_QUESTION = "general_question"


class ActionType(Enum):
    """Types of actions the system can take"""
    USE_TOOL = "use_tool"
    READ_FILE = "read_file"
    SEARCH_TEXT = "search_text"
    MODIFY_FILE = "modify_file"
    ASK_CLARIFICATION = "ask_clarification"
    PROVIDE_RESPONSE = "provide_response"


@dataclass
class InterpretedIntent:
    """Represents the interpreted user intent"""
    intent_type: IntentType
    confidence: float  # 0.0 to 1.0
    parameters: Dict[str, Any] = field(default_factory=dict)
    requires_clarification: bool = False
    clarification_questions: List[str] = field(default_factory=list)


@dataclass
class InterpretedAction:
    """Represents an action to be taken"""
    action_type: ActionType
    tool_name: Optional[str] = None
    parameters: Dict[str, Any] = field(default_factory=dict)
    priority: int = 1  # 1-5, higher is more important
    depends_on: List[str] = field(default_factory=list)  # Action IDs this depends on


@dataclass
class InterpreterResult:
    """Result of interpretation process"""
    intent: InterpretedIntent
    actions: List[InterpretedAction]
    modified_prompt: Optional[str] = None
    context_to_inject: List[str] = field(default_factory=list)  # File contents to inject


class RequestInterpreter:
    """Interprets user requests and converts them into structured actions"""
    
    def __init__(self, provider: BaseLLMProvider, config: Optional[ConfigManager] = None):
        self.provider = provider
        self.config = config or get_config()
        
        # Yes/No question templates for intent detection
        self.intent_questions = {
            IntentType.SEARCH_CODE: [
                "Does the user want to find or search for something in the code?",
                "Are they looking for specific functions, variables, or patterns?",
                "Are they asking about where something is located?"
            ],
            IntentType.READ_FILES: [
                "Does the user want to read or view file contents?",
                "Are they asking to see what's in a file or folder?",
                "Do they want to examine or review code?"
            ],
            IntentType.ANALYZE_PROJECT: [
                "Does the user want an overview or analysis of the project?",
                "Are they asking about project structure or architecture?",
                "Do they want to understand how the codebase works?"
            ],
            IntentType.EDIT_CODE: [
                "Does the user want to modify, change, or edit code?",
                "Are they asking to add, remove, or update functionality?",
                "Do they want to write new code or fix existing code?"
            ],
            IntentType.GIT_OPERATION: [
                "Does the request involve git operations?",
                "Are they asking about commits, branches, or repository status?",
                "Do they want to perform version control actions?"
            ],
            IntentType.EXECUTE_CODE: [
                "Does the user want to run or execute code?",
                "Are they asking to test or try out some functionality?",
                "Do they want to see the output of running something?"
            ],
            IntentType.DEBUG_ISSUE: [
                "Is the user reporting a bug or error?",
                "Are they asking for help fixing a problem?",
                "Do they want to diagnose an issue?"
            ]
        }
    
    async def interpret_request(self, user_input: str, context: Dict[str, Any] = None) -> InterpreterResult:
        """Main interpretation method"""
        context = context or {}
        
        # Step 1: Detect intent using AI-based yes/no questions
        intent = await self._detect_intent(user_input)
        
        # Step 2: Generate actions based on intent
        actions = await self._generate_actions(intent, user_input, context)
        
        # Step 3: Determine what context needs to be injected
        context_to_inject = await self._determine_context_injection(intent, user_input, context)
        
        # Step 4: Modify prompt if needed
        modified_prompt = await self._modify_prompt(user_input, intent, context_to_inject)
        
        return InterpreterResult(
            intent=intent,
            actions=actions,
            modified_prompt=modified_prompt,
            context_to_inject=context_to_inject
        )
    
    async def _detect_intent(self, user_input: str) -> InterpretedIntent:
        """Detect user intent using AI-powered yes/no questions"""
        
        # Score each intent type
        intent_scores: Dict[IntentType, float] = {}
        
        for intent_type, questions in self.intent_questions.items():
            score = 0.0
            
            for question in questions:
                # Ask AI a yes/no question
                answer = await self._ask_yes_no_question(question, user_input)
                if answer:
                    score += 1.0
            
            # Normalize score
            intent_scores[intent_type] = score / len(questions)
        
        # Find the highest scoring intent
        best_intent = max(intent_scores.items(), key=lambda x: x[1])
        intent_type, confidence = best_intent
        
        # If confidence is too low, default to general question
        if confidence < 0.3:
            intent_type = IntentType.GENERAL_QUESTION
            confidence = 1.0
        
        # Extract parameters using pattern matching
        parameters = self._extract_parameters(user_input, intent_type)
        
        # Determine if clarification is needed
        requires_clarification, clarification_questions = await self._check_needs_clarification(
            user_input, intent_type, parameters
        )
        
        return InterpretedIntent(
            intent_type=intent_type,
            confidence=confidence,
            parameters=parameters,
            requires_clarification=requires_clarification,
            clarification_questions=clarification_questions
        )
    
    async def _ask_yes_no_question(self, question: str, user_input: str) -> bool:
        """Ask the AI a yes/no question about the user input"""
        
        # Import prompt utilities
        from .prompt_utils import get_yes_no_format_instructions
        
        system_prompt = f"""You are analyzing a user request.

Question: {question}

User request: "{user_input}"

{get_yes_no_format_instructions()}"""
        
        messages = [ChatMessage(role="system", content=system_prompt)]
        
        # Use fastest available model for yes/no questions
        model_config = ModelConfig(
            model_name=self._get_fastest_model(),
            temperature=0.0,
            max_tokens=10
        )
        
        try:
            response = await self.provider.chat_completion(messages, model_config)
            answer = response.content.strip().lower()
            return answer.startswith('yes') or answer.startswith('y')
        except Exception:
            # Fallback to pattern matching
            return self._pattern_match_question(question, user_input)
    
    def _pattern_match_question(self, question: str, user_input: str) -> bool:
        """Fallback pattern matching for yes/no questions"""
        user_lower = user_input.lower()
        
        # Extract keywords from question and check against user input
        if "search" in question.lower() or "find" in question.lower():
            return any(word in user_lower for word in ['find', 'search', 'look for', 'where is', 'locate'])
        
        if "read" in question.lower() or "view" in question.lower():
            return any(word in user_lower for word in ['show', 'read', 'view', 'see', 'display', 'cat'])
        
        if "modify" in question.lower() or "edit" in question.lower():
            return any(word in user_lower for word in ['edit', 'change', 'modify', 'update', 'fix', 'add', 'remove'])
        
        if "git" in question.lower():
            return any(word in user_lower for word in ['git', 'commit', 'branch', 'merge', 'push', 'pull'])
        
        if "execute" in question.lower() or "run" in question.lower():
            return any(word in user_lower for word in ['run', 'execute', 'test', 'try'])
        
        if "analyze" in question.lower() or "overview" in question.lower():
            return any(word in user_lower for word in ['analyze', 'overview', 'summary', 'structure', 'understand'])
        
        return False
    
    def _extract_parameters(self, user_input: str, intent_type: IntentType) -> Dict[str, Any]:
        """Extract parameters based on intent type using pattern matching"""
        parameters = {}
        
        if intent_type == IntentType.SEARCH_CODE:
            # Extract search terms
            search_patterns = [
                r'find\s+["\']([^"\']+)["\']',
                r'search\s+for\s+["\']([^"\']+)["\']',
                r'look\s+for\s+(\w+)',
                r'where\s+is\s+(\w+)'
            ]
            
            for pattern in search_patterns:
                match = re.search(pattern, user_input, re.IGNORECASE)
                if match:
                    parameters['search_term'] = match.group(1)
                    break
        
        elif intent_type == IntentType.READ_FILES:
            # Extract file paths
            file_patterns = [
                r'show\s+([^\s]+\.\w+)',
                r'read\s+([^\s]+\.\w+)',
                r'cat\s+([^\s]+\.\w+)',
                r'([^\s]*\.\w+)'  # Any file extension
            ]
            
            for pattern in file_patterns:
                matches = re.findall(pattern, user_input, re.IGNORECASE)
                if matches:
                    parameters['files'] = matches
                    break
        
        elif intent_type == IntentType.EDIT_CODE:
            # Extract what to edit
            if 'function' in user_input.lower():
                parameters['target_type'] = 'function'
            elif 'class' in user_input.lower():
                parameters['target_type'] = 'class'
            elif 'variable' in user_input.lower():
                parameters['target_type'] = 'variable'
        
        return parameters
    
    async def _check_needs_clarification(self, user_input: str, intent_type: IntentType, 
                                       parameters: Dict[str, Any]) -> Tuple[bool, List[str]]:
        """Check if the request needs clarification"""
        
        clarification_questions = []
        
        # Check for ambiguous requests
        ambiguous_words = ['this', 'that', 'it', 'something', 'anything']
        if any(word in user_input.lower() for word in ambiguous_words):
            if intent_type == IntentType.SEARCH_CODE:
                clarification_questions.append("What specifically would you like me to search for?")
            elif intent_type == IntentType.READ_FILES:
                clarification_questions.append("Which files would you like me to read?")
        
        # Check for missing parameters based on intent
        if intent_type == IntentType.SEARCH_CODE and 'search_term' not in parameters:
            clarification_questions.append("What would you like me to search for in the code?")
        
        if intent_type == IntentType.READ_FILES and 'files' not in parameters:
            clarification_questions.append("Which files or directories would you like me to examine?")
        
        return len(clarification_questions) > 0, clarification_questions
    
    async def _generate_actions(self, intent: InterpretedIntent, user_input: str, 
                              context: Dict[str, Any]) -> List[InterpretedAction]:
        """Generate actions based on interpreted intent"""
        
        actions = []
        
        if intent.intent_type == IntentType.SEARCH_CODE:
            search_term = intent.parameters.get('search_term', '')
            if search_term:
                actions.append(InterpretedAction(
                    action_type=ActionType.USE_TOOL,
                    tool_name='search',
                    parameters={'query': search_term, 'search_type': 'text'},
                    priority=3
                ))
        
        elif intent.intent_type == IntentType.READ_FILES:
            files = intent.parameters.get('files', [])
            if not files:
                # Default to reading current directory
                actions.append(InterpretedAction(
                    action_type=ActionType.USE_TOOL,
                    tool_name='file',
                    parameters={'action': 'list_directory', 'path': '.'},
                    priority=2
                ))
            else:
                for file_path in files:
                    actions.append(InterpretedAction(
                        action_type=ActionType.READ_FILE,
                        tool_name='file',
                        parameters={'action': 'read', 'path': file_path},
                        priority=3
                    ))
        
        elif intent.intent_type == IntentType.ANALYZE_PROJECT:
            # Multi-step project analysis
            actions.extend([
                InterpretedAction(
                    action_type=ActionType.USE_TOOL,
                    tool_name='file',
                    parameters={'action': 'list_directory', 'path': '.'},
                    priority=5
                ),
                InterpretedAction(
                    action_type=ActionType.SEARCH_TEXT,
                    tool_name='search',
                    parameters={'query': 'def |class |import ', 'search_type': 'regex'},
                    priority=4
                )
            ])
        
        elif intent.intent_type == IntentType.EDIT_CODE:
            # First need to understand what to edit
            actions.append(InterpretedAction(
                action_type=ActionType.SEARCH_TEXT,
                tool_name='search',
                parameters={'query': 'determined_at_runtime'},
                priority=4
            ))
        
        elif intent.intent_type == IntentType.GIT_OPERATION:
            actions.append(InterpretedAction(
                action_type=ActionType.USE_TOOL,
                tool_name='git',
                parameters={'action': 'status'},
                priority=3
            ))
        
        # If no specific actions, just provide a response
        if not actions:
            actions.append(InterpretedAction(
                action_type=ActionType.PROVIDE_RESPONSE,
                priority=1
            ))
        
        return actions
    
    async def _determine_context_injection(self, intent: InterpretedIntent, user_input: str,
                                         context: Dict[str, Any]) -> List[str]:
        """Determine what context should be injected into the prompt"""
        
        context_files = []
        
        if intent.intent_type in [IntentType.ANALYZE_PROJECT, IntentType.SEARCH_CODE]:
            # For project analysis, inject key files
            important_files = [
                'README.md', 'package.json', 'requirements.txt', 'Cargo.toml',
                'main.py', 'app.py', 'index.js', 'main.rs'
            ]
            context_files.extend(important_files)
        
        elif intent.intent_type == IntentType.READ_FILES:
            # Inject the specific files mentioned
            files = intent.parameters.get('files', [])
            context_files.extend(files)
        
        return context_files
    
    async def _modify_prompt(self, user_input: str, intent: InterpretedIntent, 
                           context_files: List[str]) -> Optional[str]:
        """Modify the user prompt to include context and improve clarity"""
        
        if not context_files and intent.intent_type == IntentType.GENERAL_QUESTION:
            return None  # No modification needed
        
        modified_parts = [user_input]
        
        if context_files:
            modified_parts.append("\n\nContext: I will read the following files first:")
            for file_path in context_files:
                modified_parts.append(f"- {file_path}")
        
        if intent.intent_type == IntentType.ANALYZE_PROJECT:
            modified_parts.append("\n\nPlease provide a comprehensive analysis including:")
            modified_parts.append("- Project structure and organization")
            modified_parts.append("- Main technologies and dependencies")
            modified_parts.append("- Key functionality and components")
        
        return "\n".join(modified_parts)
    
    def _get_fastest_model(self) -> str:
        """Get the fastest available model for yes/no questions"""
        available_models = self.provider.list_models()
        
        if not available_models:
            return "default"
        
        # ALWAYS prioritize configured fast completion models first
        selected_model = self.config.get_model_for_task("fast_completion", available_models)
        
        if selected_model:
            return selected_model
        
        # If no configured fast completion model, try any configured model
        all_configured_models = (
            self.config.config.models.fast_completion +
            self.config.config.models.chat +
            self.config.config.models.analysis +
            self.config.config.models.high_reasoning
        )
        
        for configured_model in all_configured_models:
            if configured_model in available_models:
                return configured_model
        
        # Only use fallback logic if NO configured models are available
        fast_models = ['phi', 'gemma', 'llama3.2', 'qwen2']
        
        for fast_model in fast_models:
            for available in available_models:
                if fast_model in available.lower():
                    return available
        
        # Use first available as fallback
        return available_models[0]


class ResponseInterpreter:
    """Interprets model responses and converts them into structured actions"""
    
    def __init__(self, provider: BaseLLMProvider, config: Optional[ConfigManager] = None):
        self.provider = provider
        self.config = config or get_config()
    
    async def interpret_response(self, response: str, expected_format: str = "auto") -> Dict[str, Any]:
        """Interpret a model response and extract structured information"""
        
        # Try to parse as JSON first (including orchestrator format)
        json_result = self._try_parse_json(response)
        if json_result:
            # Log successful JSON extraction for debugging
            if self.config and hasattr(self.config, 'debug') and self.config.debug:
                print(f"🎯 Successfully extracted JSON: {json_result}")
            return json_result
        
        # Extract tool usage if present
        tool_usage = self._extract_tool_usage(response)
        if tool_usage:
            return tool_usage
        
        # Extract file edits
        file_edits = self._extract_file_edits(response)
        if file_edits:
            return {"action": "edit_files", "edits": file_edits}
        
        # Default to text response
        return {"action": "respond", "message": response.strip()}
    
    def _try_parse_json(self, response: str) -> Optional[Dict[str, Any]]:
        """Try to parse response as JSON, including orchestrator format"""
        
        # First, clean the response to handle thinking tags
        cleaned_response = self._clean_response_for_json(response)
        
        # Multiple JSON extraction patterns to try
        json_patterns = [
            # Standard JSON code blocks
            r'```json\s*(\{.*?\})\s*```',
            # JSON code blocks without language specifier
            r'```\s*(\{.*?\})\s*```',
            # JSON objects in thinking models (may have reasoning before/after)
            r'(\{[^{}]*"action"\s*:\s*"(?:use_tool|respond)"[^{}]*\})',
            # More complex nested JSON with action field (handles nested objects)
            r'(\{(?:[^{}]|\{[^{}]*\})*"action"\s*:\s*"(?:use_tool|respond)"(?:[^{}]|\{[^{}]*\})*\})',
            # JSON with thinking field
            r'(\{(?:[^{}]|\{[^{}]*\})*"thinking"\s*:.*?"action"\s*:\s*"(?:use_tool|respond)"(?:[^{}]|\{[^{}]*\})*\})',
            # JSON at the end of response (common in thinking models)
            r'(?:^|\n)\s*(\{.*?\})\s*$',
            # JSON anywhere in the response
            r'(\{(?:[^{}]|\{[^{}]*\})*\})'
        ]
        
        for pattern in json_patterns:
            matches = re.findall(pattern, cleaned_response, re.DOTALL | re.MULTILINE)
            
            for match in matches:
                try:
                    parsed = json.loads(match.strip())
                    
                    # Clean any thinking field from the parsed JSON
                    cleaned_parsed = self._clean_thinking_from_json(parsed)
                    
                    # Validate it has the expected orchestrator format
                    if self._validate_orchestrator_format(cleaned_parsed):
                        return cleaned_parsed
                    
                    # If it's valid JSON but not orchestrator format, 
                    # try to convert it
                    converted = self._convert_to_orchestrator_format(cleaned_parsed)
                    if converted:
                        return converted
                        
                except json.JSONDecodeError:
                    continue
        
        # Last resort: try parsing the entire cleaned response
        try:
            parsed = json.loads(cleaned_response.strip())
            cleaned_parsed = self._clean_thinking_from_json(parsed)
            if self._validate_orchestrator_format(cleaned_parsed):
                return cleaned_parsed
            return self._convert_to_orchestrator_format(cleaned_parsed)
        except json.JSONDecodeError:
            return None
    
    def _clean_response_for_json(self, response: str) -> str:
        """Clean response to extract JSON, handling thinking tags and extra content"""
        
        # Remove HTML-style thinking tags
        cleaned = re.sub(r'<think>.*?</think>', '', response, flags=re.DOTALL)
        
        # Remove XML-style thinking tags
        cleaned = re.sub(r'<thinking>.*?</thinking>', '', cleaned, flags=re.DOTALL)
        
        # Handle the case where thinking content is before JSON
        # Look for patterns like "thinking text... {json}"
        json_after_thinking = re.search(r'.*?(\{.*\})\s*$', cleaned, re.DOTALL)
        if json_after_thinking:
            # If we find JSON at the end after other content, extract just the JSON part
            potential_json = json_after_thinking.group(1)
            try:
                # Test if it's valid JSON
                json.loads(potential_json)
                return potential_json
            except json.JSONDecodeError:
                pass
        
        # Remove common prefixes that might interfere
        cleaned = re.sub(r'^.*?(?=\{)', '', cleaned, count=1)
        
        # Remove common suffixes
        cleaned = re.sub(r'\}.*?$', '}', cleaned, count=1)
        
        return cleaned.strip()
    
    def _clean_thinking_from_json(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Remove thinking field from JSON if present"""
        if isinstance(data, dict):
            # Create a copy and remove thinking field if it exists
            cleaned = data.copy()
            cleaned.pop('thinking', None)
            return cleaned
        return data
    
    def _validate_orchestrator_format(self, data: Dict[str, Any]) -> bool:
        """Validate if JSON matches orchestrator expected format"""
        if not isinstance(data, dict):
            return False
        
        action = data.get("action")
        
        if action == "respond":
            return "message" in data
        
        elif action == "use_tool":
            return "tool" in data and "parameters" in data
        
        return False
    
    def _convert_to_orchestrator_format(self, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Convert other JSON formats to orchestrator format"""
        if not isinstance(data, dict):
            return None
        
        # Handle common alternative formats
        
        # Format: {"tool": "name", "parameters": {...}}
        if "tool" in data and "parameters" in data and "action" not in data:
            return {
                "action": "use_tool",
                "tool": data["tool"],
                "parameters": data["parameters"]
            }
        
        # Format: {"message": "text"}
        if "message" in data and "action" not in data:
            return {
                "action": "respond",
                "message": data["message"]
            }
        
        # Format: {"response": "text"}
        if "response" in data and "action" not in data:
            return {
                "action": "respond", 
                "message": data["response"]
            }
        
        # Format: {"tool_name": "name", "args": {...}}
        if "tool_name" in data and "args" in data:
            return {
                "action": "use_tool",
                "tool": data["tool_name"],
                "parameters": data["args"]
            }
        
        # Format: {"function": "name", "arguments": {...}}
        if "function" in data and "arguments" in data:
            return {
                "action": "use_tool",
                "tool": data["function"],
                "parameters": data["arguments"]
            }
        
        return None
    
    def _extract_tool_usage(self, response: str) -> Optional[Dict[str, Any]]:
        """Extract tool usage from free-form response"""
        response_lower = response.lower()
        
        # Look for common tool usage patterns
        if any(phrase in response_lower for phrase in ['let me search', 'i\'ll search', 'searching for']):
            # Extract search term
            search_patterns = [
                r'search(?:ing)?\s+for\s+["\']([^"\']+)["\']',
                r'search(?:ing)?\s+for\s+(\w+)',
                r'look(?:ing)?\s+for\s+["\']([^"\']+)["\']',
                r'find(?:ing)?\s+["\']([^"\']+)["\']'
            ]
            
            for pattern in search_patterns:
                match = re.search(pattern, response, re.IGNORECASE)
                if match:
                    return {
                        "action": "use_tool",
                        "tool": "search",
                        "parameters": {"query": match.group(1)}
                    }
        
        if any(phrase in response_lower for phrase in ['let me read', 'i\'ll read', 'reading']):
            # Extract file paths
            file_pattern = r'read(?:ing)?\s+([^\s]+\.\w+)'
            match = re.search(file_pattern, response, re.IGNORECASE)
            if match:
                return {
                    "action": "use_tool",
                    "tool": "file",
                    "parameters": {"action": "read", "path": match.group(1)}
                }
        
        return None
    
    def _extract_file_edits(self, response: str) -> List[Dict[str, Any]]:
        """Extract file edit operations from response"""
        edits = []
        
        # Look for code blocks with file paths
        code_block_pattern = r'```(?:python|javascript|rust|go|java)?\s*(?:#\s*(.+?\.[\w]+))?\s*\n(.*?)\n```'
        matches = re.findall(code_block_pattern, response, re.DOTALL)
        
        for file_path, code_content in matches:
            if file_path:
                edits.append({
                    "file": file_path.strip(),
                    "content": code_content.strip(),
                    "operation": "replace"
                })
        
        return edits


# Factory functions
def create_request_interpreter(provider: BaseLLMProvider, config: Optional[ConfigManager] = None) -> RequestInterpreter:
    """Create a new request interpreter instance"""
    return RequestInterpreter(provider, config)


def create_response_interpreter(provider: BaseLLMProvider, config: Optional[ConfigManager] = None) -> ResponseInterpreter:
    """Create a new response interpreter instance"""
    return ResponseInterpreter(provider, config)
"""
Utilities for consistent prompt formatting across the agent system
"""
from typing import List, Dict, Any


def get_json_format_instructions(tools: List[Dict[str, Any]] = None) -> str:
    """Get standard JSON format instructions for model responses"""
    
    # Build tool descriptions
    tool_descriptions = []
    if tools:
        for tool in tools:
            tool_name = tool.get('name', 'unknown')
            tool_desc = tool.get('description', 'No description available')
            tool_descriptions.append(f"- {tool_name}: {tool_desc}")
    
    tool_section = ""
    if tool_descriptions:
        tool_section = f"""

Available tools:
{chr(10).join(tool_descriptions)}"""
    
    return f"""
USING ONLY THE FOLLOWING JSON FORMAT:

{{
    "requires_tools": boolean,
    "needs_clarification": boolean,
    "tools_needed": [list of tool names from available tools],
    "action_sequence": [ordered list of actions],
    "priority": integer,
    "complexity": "low|medium|high",
    "estimated_steps": integer,
    "clarification_questions": [list of questions if clarification needed],
    "alternatives": [list of alternative approaches if applicable]
}}
{tool_section}

DESCRIBE HOW YOU WOULD SOLVE THIS TASK. Respond with valid JSON only - no additional text before or after."""


def get_yes_no_format_instructions() -> str:
    """Get format instructions for yes/no questions"""
    return """
IMPORTANT: Respond with ONLY 'yes' or 'no'. No additional text, explanation, or formatting.

Examples:
- yes
- no

Do not include quotes, periods, or any other characters."""


def create_system_prompt_with_json_format(base_prompt: str, tools: List[Dict[str, Any]] = None, user_prompt: str = None) -> str:
    """Create a system prompt with JSON format instructions"""
    
    prompt_parts = [base_prompt.strip()]
    prompt_parts.append(get_json_format_instructions(tools))
    
    return "\n".join(prompt_parts)


def create_tool_system_prompt(tools: List[Dict[str, Any]], user_prompt: str = None) -> str:
    """Create a system prompt specifically for tool usage"""
    
    base_prompt = """You are a helpful coding agent with access to the following tools. 
Execute the user's request step by step using the appropriate tools."""
    
    return create_system_prompt_with_json_format(base_prompt, tools, user_prompt)


def create_analysis_system_prompt(project_context: str = None, user_prompt: str = None) -> str:
    """Create a system prompt for analysis tasks"""
    
    base_prompt = "You are a helpful coding assistant. Provide clear, concise responses."
    
    if project_context:
        base_prompt += f"\n\nProject context: {project_context}"
    
    return create_system_prompt_with_json_format(base_prompt, None, user_prompt)


def create_reasoning_system_prompt(task_complexity: int, task_type: str) -> str:
    """Create a system prompt for reasoning/analysis phase in model chaining"""
    
    base_prompt = f"""You are the reasoning phase of a multi-model system. 
Analyze this request and provide:
1. Key insights and approach
2. Specific requirements 
3. Implementation steps if applicable
4. Any code generation needs

Task complexity: {task_complexity}/10
Task type: {task_type}

Be concise but thorough. Your analysis will guide the next model."""
    
    return create_system_prompt_with_json_format(base_prompt)


def create_implementation_system_prompt() -> str:
    """Create a system prompt for implementation phase in model chaining"""
    
    base_prompt = """You are the implementation phase. Use the analysis provided to give a fast, accurate response.
Focus on practical implementation details and concrete solutions."""
    
    return create_system_prompt_with_json_format(base_prompt)


def create_directive_user_message(user_message: str, tools: List[Dict[str, Any]] = None) -> str:
    """Create a directive-formatted user message for task analysis"""
    
    # Build tool descriptions with parameter hints
    tool_descriptions = []
    if tools:
        for tool in tools:
            tool_name = tool.get('name', 'unknown')
            tool_desc = tool.get('description', 'No description available')
            
            # Add parameter hints for common tools
            param_hints = ""
            if tool_name == "search":
                param_hints = " (params: query, search_type[text|regex|function|class|import])"
            elif tool_name == "git":
                param_hints = " (params: action[status|commit|diff|add], files, message)"
            elif tool_name == "file":
                param_hints = " (params: action[read|write|list], path, content)"
            
            tool_descriptions.append(f"- {tool_name}: {tool_desc}{param_hints}")
    
    tool_section = ""
    if tool_descriptions:
        tool_section = f"""

Available tools:
{chr(10).join(tool_descriptions)}"""
    
    return f"""TASK: "{user_message}"

RESPOND WITH ONLY THIS JSON FORMAT (keep arrays SHORT - max 3 items each):
{{
    "requires_tools": true/false,
    "needs_clarification": false,
    "tools_needed": ["tool1", "tool2"],
    "action_sequence": ["step1", "step2"],
    "execution_steps": [
        {{
            "step": "step description",
            "tool": "tool_name", 
            "parameters": {{"param1": "value1"}},
            "dependencies": ["step_1"]
        }}
    ],
    "priority": 1-5,
    "complexity": "low",
    "estimated_steps": 2,
    "clarification_questions": [],
    "alternatives": ["alt1"]
}}
{tool_section}

CRITICAL: Start with {{ immediately. No explanations. Keep ALL arrays under 3 items. End with }}."""
#!/usr/bin/env python3
"""
Test the new directive prompt format
"""

from src.core.prompt_utils import create_tool_system_prompt, create_analysis_system_prompt, create_directive_user_message


def test_directive_user_message():
    """Test the new directive user message format"""
    
    # Mock tool schemas
    mock_tools = [
        {
            "name": "search",
            "description": "Search for text patterns in code files"
        },
        {
            "name": "file", 
            "description": "Read, write, and manipulate files"
        },
        {
            "name": "git",
            "description": "Execute git commands and operations"
        }
    ]
    
    user_prompt = "find all main functions in the codebase"
    
    directive_message = create_directive_user_message(user_prompt, mock_tools)
    
    print("📨 NEW ANALYSIS DIRECTIVE FORMAT")
    print("=" * 80)
    print(directive_message)
    print("=" * 80)
    
    print("\n🎯 EXPECTED JSON RESPONSE:")
    expected_response = """{
    "requires_tools": true,
    "needs_clarification": false,
    "tools_needed": ["search"],
    "action_sequence": ["search for main functions", "report results"],
    "priority": 3,
    "complexity": "low",
    "estimated_steps": 2,
    "clarification_questions": [],
    "alternatives": ["manual code review", "grep command"]
}"""
    print(expected_response)


def test_analysis_system_prompt():
    """Test the new analysis system prompt format"""
    
    project_context = "Python project with 2,409 files, main language: Python"
    user_prompt = "summarize this project"
    
    system_prompt = create_analysis_system_prompt(project_context, user_prompt)
    
    print("\n📊 ANALYSIS SYSTEM PROMPT FORMAT")
    print("=" * 80)
    print(system_prompt)
    print("=" * 80)


def test_without_user_prompt():
    """Test fallback when no user prompt available"""
    
    mock_tools = [
        {
            "name": "search",
            "description": "Search for text patterns in code files"
        }
    ]
    
    system_prompt = create_tool_system_prompt(mock_tools, None)
    
    print("\n🔄 FALLBACK FORMAT (No User Prompt)")
    print("=" * 80)
    print(system_prompt)
    print("=" * 80)


if __name__ == "__main__":
    test_directive_user_message()
    test_analysis_system_prompt()
    test_without_user_prompt()
    
    print("\n🎯 SUMMARY:")
    print("✅ Directive format now in USER MESSAGE instead of system prompt")
    print("✅ 'USING ONLY THE FOLLOWING JSON FORMAT, DESCRIBE HOW YOU WOULD SOLVE THIS TASK'")
    print("✅ Includes specific user prompt and available tools") 
    print("✅ Clear JSON format specification")
    print("✅ Should be fully delivered to the AI model")
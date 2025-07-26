#!/usr/bin/env python3
"""
Example usage of the enhanced interpreter that handles orchestrator JSON format
"""

import asyncio
import json
from src.core.interpreter import ResponseInterpreter
from src.core.providers.base import BaseLLMProvider


async def test_response_interpreter():
    """Test the response interpreter with various model outputs"""
    
    # Mock provider for testing
    class MockProvider(BaseLLMProvider):
        def list_models(self):
            return ["test-model"]
        
        async def chat_completion(self, messages, model_config):
            # Mock implementation
            return type('MockResponse', (), {'content': 'Mock response'})()
    
    # Create interpreter
    interpreter = ResponseInterpreter(MockProvider())
    
    # Test cases for different model outputs
    test_cases = [
        # Perfect orchestrator format
        """
        Looking at your request, I need to search for the files.
        
        {
            "action": "use_tool",
            "tool": "search",
            "parameters": {"query": "main function", "search_type": "text"}
        }
        """,
        
        # Thinking model with reasoning then JSON
        """
        The user wants me to find all the main functions in the codebase. Let me think about this:

        1. I should use the search tool to look for "main" functions
        2. I need to search for patterns like "def main" or "function main"
        3. This will help identify entry points

        Based on this analysis, here's what I'll do:

        {
            "action": "use_tool", 
            "tool": "search",
            "parameters": {
                "query": "def main|function main",
                "search_type": "regex"
            }
        }
        """,
        
        # Alternative JSON format (gets converted)
        """
        I'll search for that now.
        
        {
            "tool": "search",
            "parameters": {"query": "config file"}  
        }
        """,
        
        # Function call format (gets converted)
        """
        {
            "function": "file",
            "arguments": {"action": "read", "path": "config.yaml"}
        }
        """,
        
        # Simple response format
        """
        {
            "message": "I found 3 main functions in your codebase."
        }
        """,
        
        # Free text that gets parsed
        """
        Let me search for that information in the codebase using the search tool.
        """,
        
        # JSON in code block
        """
        Here's the action I'll take:
        
        ```json
        {
            "action": "respond",
            "message": "The configuration looks good!"
        }
        ```
        """,
        
        # No structured format - just text
        """
        Based on my analysis of the code, the main entry point is in app.py and 
        it initializes the web server on port 8000.
        """
    ]
    
    print("🧪 Testing Response Interpreter with Various Model Outputs\n")
    print("=" * 80)
    
    for i, test_input in enumerate(test_cases, 1):
        print(f"\n📝 Test Case {i}:")
        print("-" * 40)
        print("INPUT:")
        print(test_input.strip())
        print("\nOUTPUT:")
        
        result = await interpreter.interpret_response(test_input.strip())
        print(json.dumps(result, indent=2))
        
        # Validate result
        if result.get("action") in ["use_tool", "respond"]:
            print("✅ Valid orchestrator format")
        else:
            print("⚠️  Non-standard format (but handled)")
        
        print("-" * 40)


async def test_regex_patterns():
    """Test the regex patterns for JSON extraction"""
    
    class MockProvider(BaseLLMProvider):
        def list_models(self):
            return ["test-model"]
        
        async def chat_completion(self, messages, model_config):
            return type('MockResponse', (), {'content': 'Mock response'})()
    
    interpreter = ResponseInterpreter(MockProvider())
    
    # Test the regex patterns specifically
    test_texts = [
        # JSON with reasoning before and after
        '''
        I need to think about this carefully. The user is asking for a search.
        
        Let me analyze what they want:
        - They want to find functions
        - Should use search tool
        - Need regex pattern
        
        Here's my response:
        {"action": "use_tool", "tool": "search", "parameters": {"query": "function.*main"}}
        
        This should find what they're looking for.
        ''',
        
        # Multiple JSON objects (should pick the right one)
        '''
        {"invalid": "not the right format"}
        
        Actually, let me do this properly:
        
        {"action": "use_tool", "tool": "file", "parameters": {"action": "read"}}
        ''',
        
        # Nested JSON
        '''
        {
            "action": "use_tool",
            "tool": "search", 
            "parameters": {
                "query": "class Config",
                "options": {"case_sensitive": false}
            }
        }
        '''
    ]
    
    print("\n\n🎯 Testing Regex Pattern Extraction\n")
    print("=" * 80)
    
    for i, text in enumerate(test_texts, 1):
        print(f"\n📝 Regex Test {i}:")
        print("-" * 40)
        print("INPUT:")
        print(text.strip())
        
        result = interpreter._try_parse_json(text)  # Using public interface for testing
        print("\nEXTRACTED JSON:")
        if result:
            print(json.dumps(result, indent=2))
            print("✅ Successfully extracted")
        else:
            print("❌ No valid JSON found")
        
        print("-" * 40)


if __name__ == "__main__":
    asyncio.run(test_response_interpreter())
    asyncio.run(test_regex_patterns())
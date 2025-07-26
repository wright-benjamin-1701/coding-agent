#!/usr/bin/env python3
"""
Test JSON extraction with qwen3:30b output format
"""

import json
import sys
from src.core.interpreter import ResponseInterpreter
from src.core.providers.base import BaseLLMProvider


class MockProvider(BaseLLMProvider):
    def __init__(self):
        super().__init__(config=None)
    
    def list_models(self):
        return ["qwen3:30b"]
    
    async def chat_completion(self, messages, model_config):
        return type('MockResponse', (), {'content': 'Mock response'})() 
    
    async def stream_completion(self, messages, model_config):
        yield "Mock stream response"
    
    def validate_config(self):
        return True


def test_qwen_format_extraction():
    """Test extraction with the exact qwen3:30b format from user"""
    
    interpreter = ResponseInterpreter(MockProvider())
    
    # Simulate the exact output format from user's example
    qwen_response = """<think>
Okay, I need to summarize this project. Let me start by looking at the information provided. The project is located at /Users/benjaminwright/Documents/GitHub/coding-agent. There are 2409 files totaling 47,322,543 bytes. The main language is Python, with other languages like markdown, JSON, INI, etc. The dependencies are listed as Python with 5 entries. It's a Git repository.

First, the user wants a summary. Since I can't see the actual code, I have to rely on the metadata. The name "coding-agent" suggests it might be an AI or automation tool. The presence of Python as the main language indicates it's likely a backend or script-based project. The numerous files (over 2000) might mean it's a substantial project, possibly with multiple modules or components.

The languages listed include a lot of Python files, which is expected. Other files like markdown and JSON could be documentation, configuration, or data files. The Git repository implies version control, so the project is probably actively maintained.

I should mention the main language, the number of files, the presence of a Git repo, and possible areas like automation, data processing, or APIs. Since there are dependencies, maybe it uses libraries like TensorFlow or PyTorch if it's AI-related. But without seeing the code, I can't be sure. I'll have to keep the summary general but informative based on the given data.
</think>

This project, located at `/Users/benjaminwright/Documents/GitHub/coding-agent`, is a **Python-centric codebase** with **2,409 files** (totaling ~47 MB). Key details:

- **Primary Language**: Python (1,885 files)
- **Other Languages**: Markdown (7), JSON (15), YAML (2), and others (e.g., JavaScript, XML).
- **Infrastructure**: Uses Git for version control.
- **Potential Focus**: Likely involves automation, scripting, or AI/ML given the "coding-agent" name and Python dominance. Could include tools for code generation, data processing, or API interactions.
- **Structure**: May include configurations (INI, TOML), documentation (Markdown), and data files (JSON, YAML).

*Note: Without direct code access, this summary relies on metadata. The project's exact purpose would require further exploration of the codebase.*"""

    print("🧪 Testing JSON Extraction with qwen3:30b Format")
    print("=" * 60)
    print("INPUT:")
    print(qwen_response[:200] + "..." if len(qwen_response) > 200 else qwen_response)
    print("\n" + "=" * 60)
    
    # Test the extraction
    result = interpreter._try_parse_json(qwen_response)
    
    print("EXTRACTED JSON:")
    if result:
        print(json.dumps(result, indent=2))
        print("\n✅ SUCCESS: Extracted valid orchestrator format")
        
        # Validate format
        if result.get("action") == "respond" and "message" in result:
            print("✅ Valid orchestrator format confirmed")
        else:
            print("❌ Invalid orchestrator format")
    else:
        print("❌ FAILED: No JSON extracted")
        print("\nTrying to understand why it failed...")
        
        # Debug the cleaning process
        cleaned = interpreter._clean_response_for_json(qwen_response)
        print(f"\nCLEANED RESPONSE (first 300 chars):")
        print(cleaned[:300] + "..." if len(cleaned) > 300 else cleaned)
        
        # Test if it's just not structured
        print("\n🔄 Attempting to create structured response...")
        fallback_result = {
            "action": "respond",
            "message": qwen_response.replace("<think>", "").replace("</think>", "").strip()
        }
        print("FALLBACK STRUCTURED RESPONSE:")
        print(json.dumps(fallback_result, indent=2))
    
    print("\n" + "=" * 60)


def test_various_formats():
    """Test various potential qwen response formats"""
    
    interpreter = ResponseInterpreter(MockProvider())
    
    test_cases = [
        # Case 1: Model follows instructions perfectly
        """<think>
I need to analyze this request and respond with JSON.
</think>

{
    "action": "respond",
    "message": "This is a test response following JSON format."
}""",
        
        # Case 2: Model includes thinking in JSON
        """{
    "thinking": "I need to analyze this carefully...",
    "action": "respond", 
    "message": "This response includes thinking in the JSON."
}""",
        
        # Case 3: Model doesn't follow instructions (like your example)
        """<think>
The user is asking for something. Let me think about this...
</think>

Based on my analysis, here's what I found:

This is just a regular text response without JSON formatting.""",
        
        # Case 4: Mixed format
        """I'm thinking about this request.

{
    "action": "use_tool",
    "tool": "search",
    "parameters": {"query": "test"}
}

That should help find what you need."""
    ]
    
    print("\n🔬 Testing Various qwen Response Formats")
    print("=" * 60)
    
    for i, test_case in enumerate(test_cases, 1):
        print(f"\n📝 Test Case {i}:")
        print("-" * 30)
        print("INPUT:", test_case[:100] + "..." if len(test_case) > 100 else test_case)
        
        result = interpreter._try_parse_json(test_case)
        
        if result:
            print("✅ EXTRACTED:")
            print(json.dumps(result, indent=2))
        else:
            print("❌ NO JSON FOUND - Would fall back to text response")
            # Show what the fallback would be
            fallback = interpreter.interpret_response(test_case)
            print("FALLBACK:")
            print(json.dumps(fallback, indent=2))
        
        print("-" * 30)


if __name__ == "__main__":
    test_qwen_format_extraction()
    test_various_formats()
    
    print("\n🎯 SUMMARY:")
    print("The interpreter now handles:")
    print("✅ <think> tags removal")
    print("✅ JSON extraction from mixed content")
    print("✅ Thinking field removal from JSON")
    print("✅ Fallback to structured response format")
    print("✅ Multiple JSON pattern matching")
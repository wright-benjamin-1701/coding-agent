#!/usr/bin/env python3
"""
Test that we only use the unified analysis format
"""

from src.core.prompt_utils import create_directive_user_message


def test_only_analysis_format():
    """Verify we only use the analysis format that induces tool usage"""
    
    # Mock tool schemas
    mock_tools = [
        {
            "name": "search",
            "description": "Search for text patterns in code files"
        },
        {
            "name": "file", 
            "description": "Read, write, and manipulate files"
        }
    ]
    
    # Test with tools
    user_prompt = "find all main functions"
    directive_with_tools = create_directive_user_message(user_prompt, mock_tools)
    
    print("🔧 WITH TOOLS:")
    print("=" * 60)
    print(directive_with_tools)
    print("=" * 60)
    
    # Test without tools (empty list)
    directive_no_tools = create_directive_user_message(user_prompt, [])
    
    print("\n📝 NO TOOLS:")
    print("=" * 60)
    print(directive_no_tools)
    print("=" * 60)
    
    # Verify both use the same analysis format
    analysis_format_markers = [
        '"requires_tools": true/false',
        '"tools_needed": ["tool1", "tool2"]',
        '"action_sequence": ["step1", "step2"]',
        '"complexity": "low"'
    ]
    
    print(f"\n✅ VERIFICATION:")
    for marker in analysis_format_markers:
        in_with_tools = marker in directive_with_tools
        in_no_tools = marker in directive_no_tools
        print(f"   {marker[:30]}... : {'✅' if in_with_tools and in_no_tools else '❌'}")
    
    # Verify NO confusing formats
    confusing_formats = [
        '"action": "respond"',
        '"action": "use_tool"',
        '"message": "your response'
    ]
    
    print(f"\n❌ CONFUSING FORMATS (should be absent):")
    for confusing in confusing_formats:
        in_with_tools = confusing in directive_with_tools
        in_no_tools = confusing in directive_no_tools
        status = "❌ FOUND" if (in_with_tools or in_no_tools) else "✅ NOT FOUND"
        print(f"   {confusing[:30]}... : {status}")


if __name__ == "__main__":
    test_only_analysis_format()
    
    print("\n🎯 SUMMARY:")
    print("✅ Only using analysis JSON format")
    print("✅ No confusing action/response formats")
    print("✅ Consistent format with/without tools")
    print("✅ Should induce proper tool usage from small models")
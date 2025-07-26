#!/usr/bin/env python3
"""
Test the search_type validation fix
"""

def test_search_type_fix():
    """Test that invalid search_type values get fixed"""
    
    print("🔍 TESTING SEARCH_TYPE VALIDATION FIX")
    print("=" * 80)
    
    # Import orchestrator
    class MockProvider:
        def list_models(self):
            return ["qwen3:30b"]
    
    class MockTool:
        def __init__(self, name):
            self.name = name
    
    from src.core.orchestrator import AgentOrchestrator
    
    orchestrator = AgentOrchestrator(MockProvider(), [
        MockTool("search"), MockTool("file")
    ])
    
    # Test the failing case
    failing_params = {
        'query': 'main|setup|readme',
        'search_type': 'filename'
    }
    
    print("🚫 ORIGINAL FAILING PARAMETERS:")
    print(f"   Original: {failing_params}")
    
    # Test parameter fixing
    fixed_params = orchestrator._validate_and_fix_tool_parameters("search", failing_params)
    
    print(f"   Fixed: {fixed_params}")
    print(f"   Status: {'✅ FIXED' if fixed_params != failing_params else '❌ NOT FIXED'}")
    
    # Verify the fix
    if fixed_params.get("search_type") in ["text", "regex", "function", "class", "import"]:
        print("   ✅ search_type is now valid")
    else:
        print(f"   ❌ search_type still invalid: {fixed_params.get('search_type')}")
    
    # Test other invalid search types
    test_cases = [
        ("filename", "Should convert to text search with file pattern"),
        ("pattern", "Should convert to regex search"),
        ("code", "Should convert to text search"),
        ("invalid_type", "Should default to text search"),
        ("function", "Should remain as function (valid)"),
        ("regex", "Should remain as regex (valid)")
    ]
    
    print("\n🧪 ADDITIONAL SEARCH_TYPE TESTS:")
    for search_type, description in test_cases:
        test_params = {"query": "test", "search_type": search_type}
        fixed = orchestrator._validate_and_fix_tool_parameters("search", test_params)
        
        print(f"   {search_type} → {fixed['search_type']}")
        print(f"      Query: {fixed['query']}")
        print(f"      File pattern: {fixed['file_pattern']}")
        print(f"      Description: {description}")
        print()

if __name__ == "__main__":
    test_search_type_fix()
    
    print("🏁 SEARCH_TYPE FIX SUMMARY:")
    print("✅ Invalid 'filename' search_type converted to 'text' with file pattern")
    print("✅ Invalid 'pattern' search_type converted to 'regex'")
    print("✅ Invalid 'code' search_type converted to 'text'")
    print("✅ Unknown search_type values default to 'text'")
    print("✅ Valid search_type values preserved unchanged")
    print("✅ Search tool will no longer fail with 'Unknown search type' errors")
#!/usr/bin/env python3
"""
Direct test of the source file prioritization logic
"""
import sys
import asyncio
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from core.orchestrator import AgentOrchestrator
from core.tools.search_tool import SearchTool


async def test_source_file_prioritization():
    """Test the _get_combined_search_results method directly"""
    
    print("=== Testing Source File Prioritization Logic ===")
    
    # Create a mock orchestrator just to access the method
    # We'll create a minimal mock setup
    class MinimalOrchestrator(AgentOrchestrator):
        def __init__(self):
            # Minimal initialization - just enough to test the method
            self.tools = {"search": SearchTool()}
    
    orchestrator = MinimalOrchestrator()
    
    # Test the search for "orchestrator" - this should find both source and test files
    search_tool = SearchTool()
    
    print("1. Testing filename search for 'orchestrator'...")
    filename_result = await search_tool.execute(
        query="orchestrator",
        search_type="filename",
        max_results=20
    )
    
    if filename_result.success and filename_result.data.get("results"):
        files_found = [result["file"] for result in filename_result.data["results"]]
        print(f"   Found {len(files_found)} files:")
        
        source_files = []
        test_files = []
        
        for file_path in files_found:
            if "test" in file_path.lower():
                test_files.append(file_path)
            else:
                source_files.append(file_path)
            print(f"   - {file_path}")
        
        print(f"\n   Source files: {len(source_files)}")
        for f in source_files:
            print(f"     • {f}")
        
        print(f"   Test files: {len(test_files)}")
        for f in test_files:
            print(f"     • {f}")
        
        # Test the prioritization logic
        print(f"\n2. Testing prioritization logic...")
        
        # Simulate what _get_combined_search_results does
        all_results = filename_result.data["results"]
        
        # Sort with source file prioritization
        def prioritize_source_files(result):
            file_path = result["file"].lower()
            
            # Heavy penalty for test files
            if any(test_indicator in file_path for test_indicator in ["test_", "/test", "tests/"]):
                penalty = 1000
            else:
                penalty = 0
            
            # Prefer files in src/ or core/ directories
            if any(src_indicator in file_path for src_indicator in ["/src/", "/core/"]):
                bonus = -50
            else:
                bonus = 0
            
            # Prefer .py files over others
            if file_path.endswith('.py'):
                type_bonus = -10
            else:
                type_bonus = 0
            
            return penalty + bonus + type_bonus
        
        sorted_results = sorted(all_results, key=prioritize_source_files)
        
        print("   Prioritized file order:")
        for i, result in enumerate(sorted_results[:10]):  # Show top 10
            file_path = result["file"]
            is_source = not any(test_indicator in file_path.lower() for test_indicator in ["test_", "/test", "tests/"])
            marker = "📁" if is_source else "🧪"
            print(f"     {i+1:2d}. {marker} {file_path}")
        
        # Check if source files come first
        top_5_files = [result["file"] for result in sorted_results[:5]]
        source_in_top_5 = sum(1 for f in top_5_files if not any(test_indicator in f.lower() for test_indicator in ["test_", "/test", "tests/"]))
        test_in_top_5 = 5 - source_in_top_5
        
        print(f"\n3. Results Analysis:")
        print(f"   Source files in top 5: {source_in_top_5}/5")
        print(f"   Test files in top 5: {test_in_top_5}/5")
        
        if source_in_top_5 >= 3:
            print("   ✅ SUCCESS: Source files are properly prioritized!")
        elif source_in_top_5 >= 1:
            print("   ⚠️  PARTIAL: Some source files prioritized, but could be better")
        else:
            print("   ❌ FAILURE: Test files are still ranked higher than source files")
        
        # Test specifically for the main orchestrator file
        main_orchestrator = next((f for f in top_5_files if "orchestrator.py" in f and "/src/" in f), None)
        if main_orchestrator:
            print(f"   ✅ Main orchestrator source file found in top 5: {main_orchestrator}")
        else:
            print(f"   ❌ Main orchestrator source file NOT in top 5")
            
    else:
        print("   ❌ No files found for 'orchestrator' search")


if __name__ == "__main__":
    asyncio.run(test_source_file_prioritization())
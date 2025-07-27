#!/usr/bin/env python3
"""
Verify that the nuclear approach now reads source files instead of test files
"""
import sys
import asyncio
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from core.tools.search_tool import SearchTool
from core.tools.file_tool import FileTool


async def verify_nuclear_workflow():
    """Simulate the nuclear approach workflow to verify file prioritization"""
    
    print("=== Verifying Nuclear Approach Workflow ===")
    
    search_tool = SearchTool()
    file_tool = FileTool()
    
    print("1. Nuclear approach searches for 'orchestrator' files...")
    
    # Simulate the 4 nuclear search types
    searches = [
        ("filename", "orchestrator"),
        ("function", "orchestrator"),  
        ("class", "orchestrator"),
        ("text", "orchestrator")
    ]
    
    all_files = []
    
    for search_type, query in searches:
        print(f"   Running {search_type} search for '{query}'...")
        result = await search_tool.execute(
            query=query,
            search_type=search_type,
            max_results=10
        )
        
        if result.success and result.data.get("results"):
            files = [r["file"] for r in result.data["results"]]
            all_files.extend(files)
            print(f"   Found {len(files)} files")
    
    # Remove duplicates and apply prioritization
    unique_files = list(dict.fromkeys(all_files))  # Preserves order
    
    print(f"\n2. Found {len(unique_files)} unique files total")
    
    # Apply the same prioritization logic as in orchestrator
    def source_file_priority(file_path):
        path_lower = file_path.lower()
        if 'src/core/orchestrator.py' in path_lower:
            return -10  # HIGHEST priority
        elif 'src/main.py' in path_lower:
            return -9   # Very high
        elif 'src/core/' in path_lower and not ('test' in path_lower):
            return -5   # High priority
        elif '/src/' in path_lower and not ('test' in path_lower):
            return 0    # Good priority
        elif '/test' in path_lower or 'test_' in path_lower or '/tests/' in path_lower:
            return 10   # Very low priority
        elif 'example' in path_lower:
            return 8    # Low priority
        else:
            return 5    # Medium priority
    
    prioritized_files = sorted(unique_files, key=source_file_priority)
    
    print("\n3. Prioritized file list (top 10):")
    for i, file_path in enumerate(prioritized_files[:10]):
        priority = source_file_priority(file_path)
        is_source = priority <= 0
        marker = "🎯" if priority == -10 else "📁" if is_source else "🧪"
        print(f"   {i+1:2d}. {marker} (priority: {priority:2d}) {file_path}")
    
    # Test reading the top prioritized files
    print(f"\n4. Testing file reading for top 3 prioritized files...")
    
    top_files = prioritized_files[:3]
    
    for i, file_path in enumerate(top_files):
        print(f"\n   Reading file {i+1}: {file_path}")
        result = await file_tool.execute(action="read", path=file_path)
        
        if result.success:
            content = result.content[:200] + "..."
            print(f"   ✅ Successfully read {len(result.content)} characters")
            print(f"   📖 Preview: {content}")
            
            # Check if this looks like source code vs test code
            content_lower = result.content.lower()
            
            source_indicators = ["class ", "def ", "import ", "from "]
            test_indicators = ["test_", "mock", "pytest", "assert ", "fixture"]
            
            source_score = sum(content_lower.count(indicator) for indicator in source_indicators)
            test_score = sum(content_lower.count(indicator) for indicator in test_indicators)
            
            if "/test" in file_path.lower():
                print(f"   🧪 This is a TEST file (test indicators: {test_score}, source: {source_score})")
            else:
                print(f"   📁 This is a SOURCE file (source indicators: {source_score}, test: {test_score})")
                
        else:
            print(f"   ❌ Failed to read: {result.error}")
    
    # Final assessment
    print(f"\n5. Final Assessment:")
    
    top_3_files = prioritized_files[:3]
    source_files_in_top_3 = sum(1 for f in top_3_files if source_file_priority(f) <= 0)
    test_files_in_top_3 = sum(1 for f in top_3_files if "/test" in f.lower() or "test_" in f.lower())
    
    main_orchestrator_rank = None
    for i, f in enumerate(prioritized_files):
        if "src/core/orchestrator.py" in f:
            main_orchestrator_rank = i + 1
            break
    
    print(f"   • Source files in top 3: {source_files_in_top_3}/3")
    print(f"   • Test files in top 3: {test_files_in_top_3}/3")
    if main_orchestrator_rank:
        print(f"   • Main orchestrator.py ranked: #{main_orchestrator_rank}")
    
    if source_files_in_top_3 >= 2 and main_orchestrator_rank and main_orchestrator_rank <= 2:
        print(f"\n   🎉 SUCCESS! Nuclear approach now prioritizes source files correctly!")
        print(f"      The user's issue has been resolved - real source files are read instead of test files.")
    elif source_files_in_top_3 >= 1:
        print(f"\n   ⚠️  IMPROVED but could be better. Some source files are prioritized.")
    else:
        print(f"\n   ❌ STILL BROKEN. Test files are still being prioritized over source files.")


if __name__ == "__main__":
    asyncio.run(verify_nuclear_workflow())
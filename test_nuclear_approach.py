#!/usr/bin/env python3
"""
Test script to verify the nuclear approach properly prioritizes source files over test files
"""
import sys
import asyncio
from pathlib import Path
from unittest.mock import Mock, AsyncMock, patch

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from core.orchestrator import AgentOrchestrator
from core.providers.base import BaseLLMProvider, ChatMessage, ModelConfig, ProviderResponse
from core.tools.base import BaseTool, ToolResult
from core.tools.search_tool import SearchTool
from core.tools.file_tool import FileTool
from core.tools.summary_tool import SummaryTool


class MockProvider(BaseLLMProvider):
    """Mock LLM provider for testing"""
    
    def __init__(self):
        self.models = ["test-model"]
        self.call_count = 0
        # Mock responses for the nuclear approach workflow
        self.responses = [
            # Initial analysis response
            """
            Based on the user request "explain the orchestrator file", I need to:
            1. Search for orchestrator-related files
            2. Read the main orchestrator file
            3. Provide a comprehensive analysis
            
            This requires nuclear approach with multiple search strategies and file reading.
            """,
            # Final summary response
            """
            The orchestrator file contains the main AgentOrchestrator class which coordinates between different tools and manages the workflow execution. Key components include task planning, tool execution, and response generation.
            """
        ]
    
    def validate_config(self) -> bool:
        return True
    
    def list_models(self) -> list:
        return self.models
    
    async def chat_completion(self, messages, config) -> ProviderResponse:
        response_content = self.responses[min(self.call_count, len(self.responses) - 1)]
        self.call_count += 1
        return ProviderResponse(
            content=response_content,
            model=config.model_name,
            usage={"tokens": 100}
        )
    
    async def stream_completion(self, messages, config):
        """Mock stream completion - not used in this test"""
        yield self.responses[0]


async def test_nuclear_approach():
    """Test that the nuclear approach prioritizes source files over test files"""
    
    print("=== Testing Nuclear Approach File Prioritization ===")
    
    # Create real tools
    search_tool = SearchTool()
    file_tool = FileTool()
    summary_tool = SummaryTool()
    
    # Create mock provider
    provider = MockProvider()
    summary_tool.set_llm_provider(provider)
    
    # Create orchestrator with real tools
    tools = [search_tool, file_tool, summary_tool]
    
    with patch('core.orchestrator.get_config'), \
         patch('core.orchestrator.get_safety_enforcer'), \
         patch('core.orchestrator.get_task_planner'), \
         patch('core.orchestrator.get_session_manager'), \
         patch('core.orchestrator.get_learning_system'):
        
        orchestrator = AgentOrchestrator(provider, tools)
        
        # Test the request that should trigger nuclear approach
        print("Processing request: 'explain the orchestrator file'")
        result = await orchestrator.process_request("explain the orchestrator file")
        
        print(f"Request success: {result.success}")
        print(f"Response length: {len(result.content)}")
        print("First 300 characters of response:")
        print(result.content[:300])
        print("...")
        
        # Check if the response contains actual file analysis rather than generic content
        response_lower = result.content.lower()
        
        # Look for signs that actual source file was read
        actual_file_indicators = [
            "agentorchestrator",  # Class name from actual file
            "process_request",    # Method name from actual file  
            "provider",          # Attribute from actual file
            "tools",             # Attribute from actual file
            "def __init__",      # Constructor pattern
            "async def"          # Async method pattern
        ]
        
        # Look for signs of test file content (should NOT be present)
        test_file_indicators = [
            "mock",
            "pytest",
            "test_",
            "fixture",
            "assert",
            "def test_"
        ]
        
        actual_indicators_found = sum(1 for indicator in actual_file_indicators if indicator in response_lower)
        test_indicators_found = sum(1 for indicator in test_file_indicators if indicator in response_lower)
        
        print(f"\nAnalysis Results:")
        print(f"- Actual file indicators found: {actual_indicators_found}/{len(actual_file_indicators)}")
        print(f"- Test file indicators found: {test_indicators_found}/{len(test_file_indicators)}")
        
        if actual_indicators_found >= 3 and test_indicators_found == 0:
            print("✅ SUCCESS: Nuclear approach properly prioritized source file over test files!")
            print("   The response contains actual orchestrator implementation details.")
        elif test_indicators_found > 0:
            print("❌ FAILURE: Response contains test file content instead of source file")
            print("   The nuclear approach is still reading test files.")
        else:
            print("⚠️  UNCLEAR: Response doesn't clearly indicate source vs test file content")
            print("   The response may be too generic or missing file content entirely.")
        
        return result


if __name__ == "__main__":
    result = asyncio.run(test_nuclear_approach())
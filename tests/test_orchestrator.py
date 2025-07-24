"""
Tests for the AgentOrchestrator class
"""
import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch
from typing import List, Dict, Any

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from core.orchestrator import AgentOrchestrator, Task, AgentContext
from core.providers.base import BaseLLMProvider, ChatMessage, ModelConfig, ProviderResponse
from core.tools.base import BaseTool, ToolResult


class MockProvider(BaseLLMProvider):
    """Mock LLM provider for testing"""
    
    def __init__(self):
        self.models = ["test-model-1", "test-model-2"]
        self.responses = ["Test response"]
    
    def validate_config(self) -> bool:
        return True
    
    def list_models(self) -> List[str]:
        return self.models
    
    async def chat_completion(self, messages: List[ChatMessage], config: ModelConfig) -> ProviderResponse:
        return ProviderResponse(
            content=self.responses[0] if self.responses else "Default response",
            model=config.model_name,
            usage={"tokens": 100}
        )


class MockTool(BaseTool):
    """Mock tool for testing"""
    
    def __init__(self, name: str = "mock_tool"):
        self.name = name
        self.description = "Mock tool for testing"
        self.result = ToolResult(success=True, content="Mock tool executed")
    
    async def execute(self, **kwargs) -> ToolResult:
        return self.result
    
    def to_llm_function_schema(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "parameters": {
                "type": "object",
                "properties": {},
                "required": []
            }
        }


@pytest.fixture
def mock_provider():
    """Create a mock provider"""
    return MockProvider()


@pytest.fixture
def mock_tools():
    """Create mock tools"""
    return [MockTool("file_tool"), MockTool("git_tool")]


@pytest.fixture
def orchestrator(mock_provider, mock_tools):
    """Create an orchestrator with mock dependencies"""
    with patch('core.orchestrator.get_config'), \
         patch('core.orchestrator.get_safety_enforcer'), \
         patch('core.orchestrator.get_task_planner'), \
         patch('core.orchestrator.get_session_manager'), \
         patch('core.orchestrator.get_learning_system'):
        return AgentOrchestrator(mock_provider, mock_tools)


class TestAgentOrchestrator:
    """Test cases for AgentOrchestrator"""
    
    def test_initialization(self, orchestrator, mock_tools):
        """Test orchestrator initialization"""
        assert orchestrator.provider is not None
        assert len(orchestrator.tools) == 2
        assert "file_tool" in orchestrator.tools
        assert "git_tool" in orchestrator.tools
        assert orchestrator.context.project_path == ""
        assert len(orchestrator.context.conversation_history) == 0
    
    def test_add_tool(self, orchestrator):
        """Test adding a tool"""
        new_tool = MockTool("new_tool")
        orchestrator.add_tool(new_tool)
        
        assert "new_tool" in orchestrator.tools
        assert orchestrator.tools["new_tool"] == new_tool
    
    def test_remove_tool(self, orchestrator):
        """Test removing a tool"""
        orchestrator.remove_tool("file_tool")
        
        assert "file_tool" not in orchestrator.tools
        assert len(orchestrator.tools) == 1
    
    def test_get_available_tools(self, orchestrator):
        """Test getting available tools"""
        tools = orchestrator.get_available_tools()
        
        assert isinstance(tools, list)
        assert "file_tool" in tools
        assert "git_tool" in tools
        assert len(tools) == 2
    
    @pytest.mark.asyncio
    async def test_simple_request_processing(self, orchestrator, mock_provider):
        """Test processing a simple request"""
        mock_provider.responses = ["Hello! How can I help you?"]
        
        # Mock the analyze request to return simple response
        with patch.object(orchestrator, '_analyze_request') as mock_analyze:
            mock_analyze.return_value = {
                "requires_tools": False,
                "needs_clarification": False,
                "complexity": "low"
            }
            
            response = await orchestrator.process_request("Hello")
            
            assert response == "Hello! How can I help you?"
            assert len(orchestrator.context.conversation_history) == 2  # User + Assistant
            assert orchestrator.context.conversation_history[0].role == "user"
            assert orchestrator.context.conversation_history[1].role == "assistant"
    
    @pytest.mark.asyncio
    async def test_request_with_tools(self, orchestrator, mock_provider):
        """Test processing a request that requires tools"""
        mock_provider.responses = ['{"action": "use_tool", "tool": "file_tool", "parameters": {}}']
        
        # Mock the analyze request to return tool requirement
        with patch.object(orchestrator, '_analyze_request') as mock_analyze:
            mock_analyze.return_value = {
                "requires_tools": True,
                "needs_clarification": False,
                "tools_needed": ["file_tool"],
                "complexity": "medium"
            }
            
            response = await orchestrator.process_request("Show me files")
            
            # Should contain tool execution result
            assert "Mock tool executed" in response or "completed" in response.lower()
    
    @pytest.mark.asyncio
    async def test_clarification_request(self, orchestrator, mock_provider):
        """Test processing a request that needs clarification"""
        mock_provider.responses = ["Could you please clarify what you mean?"]
        
        with patch.object(orchestrator, '_analyze_request') as mock_analyze:
            mock_analyze.return_value = {
                "requires_tools": False,
                "needs_clarification": True,
                "clarification_questions": ["What specific files?"],
                "complexity": "medium"
            }
            
            response = await orchestrator.process_request("Show me files")
            
            assert "clarify" in response.lower() or "question" in response.lower()
    
    def test_get_context_summary(self, orchestrator):
        """Test getting context summary"""
        orchestrator.context.project_path = "/test/path"
        orchestrator.context.conversation_history.append(
            ChatMessage(role="user", content="Test message")
        )
        
        summary = orchestrator.get_context_summary()
        
        assert summary["project_path"] == "/test/path"
        assert summary["conversation_length"] == 1
        assert summary["active_tasks"] == 0
        assert isinstance(summary["available_tools"], list)
        assert len(summary["available_tools"]) == 2
    
    @pytest.mark.asyncio
    async def test_set_project_path(self, orchestrator):
        """Test setting project path"""
        test_path = str(Path(__file__).parent)  # Use test directory
        
        with patch.object(orchestrator.session_manager, 'start_session'), \
             patch('core.orchestrator.ContextManager') as mock_context_manager:
            
            mock_context_manager.return_value.build_context = AsyncMock(return_value=None)
            
            await orchestrator.set_project_path(test_path)
            
            assert orchestrator.context.project_path == test_path
            assert orchestrator.context_manager is not None
    
    def test_clear_conversation_history(self, orchestrator):
        """Test clearing conversation history"""
        orchestrator.context.conversation_history.append(
            ChatMessage(role="user", content="Test")
        )
        
        assert len(orchestrator.context.conversation_history) == 1
        
        orchestrator.clear_conversation_history()
        
        assert len(orchestrator.context.conversation_history) == 0
    
    @pytest.mark.asyncio
    async def test_user_feedback_processing(self, orchestrator):
        """Test processing user feedback"""
        # Add some conversation history
        orchestrator.context.conversation_history.extend([
            ChatMessage(role="user", content="Test question"),
            ChatMessage(role="assistant", content="Test response")
        ])
        
        feedback_response = await orchestrator.process_user_feedback("That was helpful")
        
        assert "thank you" in feedback_response.lower()
        assert "recorded" in feedback_response.lower()
    
    @pytest.mark.asyncio
    async def test_user_feedback_no_history(self, orchestrator):
        """Test feedback processing with no conversation history"""
        feedback_response = await orchestrator.process_user_feedback("Good job")
        
        assert "no recent interaction" in feedback_response.lower()
    
    def test_learning_integration(self, orchestrator):
        """Test learning system integration"""
        # Test getting learning summary
        summary = orchestrator.get_learning_summary()
        assert isinstance(summary, dict)
        
        # Test getting user preferences
        preferences = orchestrator.get_user_preferences()
        assert isinstance(preferences, dict)
        
        # Test getting performance metrics
        metrics = orchestrator.get_performance_metrics()
        assert isinstance(metrics, dict)


@pytest.mark.asyncio
async def test_error_handling(orchestrator, mock_provider):
    """Test error handling in request processing"""
    # Make the provider raise an exception
    mock_provider.chat_completion = AsyncMock(side_effect=Exception("Test error"))
    
    with patch.object(orchestrator, '_analyze_request') as mock_analyze:
        mock_analyze.return_value = {
            "requires_tools": False,
            "needs_clarification": False,
            "complexity": "low"
        }
        
        # Should handle the exception gracefully
        with pytest.raises(Exception):
            await orchestrator.process_request("Test")


if __name__ == "__main__":
    pytest.main([__file__])
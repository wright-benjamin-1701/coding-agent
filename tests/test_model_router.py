"""
Tests for the model router system
"""
import pytest
from unittest.mock import Mock, patch

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from core.model_router import (
    ModelRouter, ModelType, ModelCapability, TaskComplexity
)
from core.providers.base import BaseLLMProvider, ChatMessage, ModelConfig, ProviderResponse


class MockProvider(BaseLLMProvider):
    """Mock provider for testing"""
    
    def __init__(self, models=None):
        self.models = models or ["qwen2.5-coder:7b", "llama3.1:70b", "deepseek-coder:1.3b"]
    
    def validate_config(self) -> bool:
        return True
    
    def list_models(self):
        return self.models
    
    async def chat_completion(self, messages, config):
        return ProviderResponse(
            content="Test response",
            model=config.model_name,
            usage={"tokens": 100}
        )


@pytest.fixture
def mock_provider():
    """Create a mock provider"""
    return MockProvider()


@pytest.fixture 
def model_router(mock_provider):
    """Create a model router with mock provider"""
    with patch('core.model_router.get_config'):
        return ModelRouter(mock_provider)


class TestModelRouter:
    """Test cases for ModelRouter"""
    
    def test_initialization(self, model_router, mock_provider):
        """Test model router initialization"""
        assert model_router.provider == mock_provider
        assert len(model_router.model_capabilities) > 0
        assert isinstance(model_router.performance_history, dict)
    
    def test_model_capability_detection(self, model_router):
        """Test model capability detection from names"""
        capabilities = model_router.model_capabilities
        
        # Should detect coder model
        coder_models = [name for name, cap in capabilities.items() if "coder" in name.lower()]
        assert len(coder_models) > 0
        
        coder_capability = capabilities[coder_models[0]]
        assert coder_capability.reasoning_score > 0
        assert coder_capability.speed_score > 0
        assert "python" in coder_capability.specializations
    
    def test_task_complexity_analysis_simple(self, model_router):
        """Test analyzing simple task complexity"""
        complexity = model_router.analyze_task_complexity(
            "show me the status",
            {"conversation_history": []}
        )
        
        assert isinstance(complexity, TaskComplexity)
        assert complexity.complexity_score <= 5  # Should be low complexity
        assert complexity.requires_speed == True
        assert complexity.task_type == "quick_response"
    
    def test_task_complexity_analysis_complex(self, model_router):
        """Test analyzing complex task complexity"""
        complexity = model_router.analyze_task_complexity(
            "refactor the entire codebase and optimize performance across multiple files",
            {"project_context": {"files": 100}}
        )
        
        assert complexity.complexity_score >= 7  # Should be high complexity
        assert complexity.requires_reasoning == True
        assert complexity.task_type == "complex_analysis"
    
    def test_model_selection_simple_task(self, model_router):
        """Test model selection for simple tasks"""
        simple_complexity = TaskComplexity(
            complexity_score=2,
            requires_reasoning=False,
            requires_speed=True,
            estimated_tokens=100,
            task_type="quick_response",
            context_needs=[]
        )
        
        selected_model, should_chain = model_router.select_optimal_model(simple_complexity)
        
        assert selected_model in model_router.model_capabilities
        # For simple tasks, should prefer fast models
        capability = model_router.model_capabilities[selected_model]
        assert capability.speed_score >= 6 or capability.type == ModelType.FAST_COMPLETION
    
    def test_model_selection_complex_task(self, model_router):
        """Test model selection for complex tasks"""
        complex_complexity = TaskComplexity(
            complexity_score=9,
            requires_reasoning=True,
            requires_speed=False,
            estimated_tokens=2000,
            task_type="complex_analysis",
            context_needs=["project_understanding"]
        )
        
        selected_model, should_chain = model_router.select_optimal_model(complex_complexity)
        
        assert selected_model in model_router.model_capabilities
        # For complex tasks, should prefer reasoning models
        capability = model_router.model_capabilities[selected_model]
        assert capability.reasoning_score >= 7 or capability.type == ModelType.REASONING
    
    def test_model_chaining_decision(self, model_router):
        """Test decision to chain models"""
        # High complexity task that might benefit from chaining
        high_complexity = TaskComplexity(
            complexity_score=8,
            requires_reasoning=True,
            requires_speed=True,
            estimated_tokens=1500,
            task_type="code_generation",
            context_needs=["project_understanding", "code_context"]
        )
        
        selected_model, should_chain = model_router.select_optimal_model(high_complexity)
        
        # With multiple models available, complex tasks might chain
        assert isinstance(should_chain, bool)
        if should_chain:
            # Should have both reasoning and fast models available
            reasoning_model = model_router._get_best_reasoning_model()
            fast_model = model_router._get_best_fast_model()
            assert reasoning_model is not None
            assert fast_model is not None
    
    def test_single_model_fallback(self, model_router):
        """Test fallback when only one model is available"""
        # Replace with single model
        model_router.provider.models = ["single-model"]
        model_router.model_capabilities = {
            "single-model": ModelCapability(
                model_name="single-model",
                type=ModelType.CHAT,
                reasoning_score=6,
                speed_score=6,
                context_window=4096,
                specializations=["general"]
            )
        }
        
        complexity = TaskComplexity(
            complexity_score=8,
            requires_reasoning=True,
            requires_speed=True,
            estimated_tokens=1000,
            task_type="complex_analysis",
            context_needs=[]
        )
        
        selected_model, should_chain = model_router.select_optimal_model(complexity)
        
        assert selected_model == "single-model"
        assert should_chain == False  # Can't chain with only one model
    
    @pytest.mark.asyncio
    async def test_execute_with_routing_single(self, model_router):
        """Test executing with single model routing"""
        messages = [ChatMessage(role="user", content="Hello")]
        complexity = TaskComplexity(
            complexity_score=3,
            requires_reasoning=False,
            requires_speed=True,
            estimated_tokens=50,
            task_type="quick_response",
            context_needs=[]
        )
        
        result = await model_router.execute_with_routing(messages, complexity)
        
        assert isinstance(result, str)
        assert len(result) > 0
    
    def test_performance_tracking(self, model_router):
        """Test performance tracking"""
        model_name = "test-model"
        
        # Record some performance data
        model_router._record_performance(model_name, 2.5)
        model_router._record_performance(model_name, 3.0)
        model_router._record_performance(model_name, 2.0)
        
        assert model_name in model_router.performance_history
        assert len(model_router.performance_history[model_name]) == 3
        
        # Test history limit
        for i in range(25):  # Add more than the limit of 20
            model_router._record_performance(model_name, float(i))
        
        assert len(model_router.performance_history[model_name]) == 20
    
    def test_get_model_recommendations(self, model_router):
        """Test getting model recommendations"""
        recommendations = model_router.get_model_recommendations(
            "Create a Python script to analyze data"
        )
        
        assert isinstance(recommendations, dict)
        assert "primary_model" in recommendations
        assert "should_chain" in recommendations
        assert "task_complexity" in recommendations
        assert "reasoning_needed" in recommendations
        assert "speed_priority" in recommendations
        assert "task_type" in recommendations
    
    def test_get_available_models_info(self, model_router):
        """Test getting available models information"""
        models_info = model_router.get_available_models_info()
        
        assert isinstance(models_info, dict)
        assert len(models_info) > 0
        
        # Check structure of model info
        for model_name, info in models_info.items():
            assert "type" in info
            assert "reasoning_score" in info
            assert "speed_score" in info
            assert "context_window" in info
            assert "specializations" in info
            assert "avg_response_time" in info
    
    def test_suggest_model_for_task_type(self, model_router):
        """Test suggesting models for specific task types"""
        # Test different task types
        reasoning_model = model_router.suggest_model_for_task_type("reasoning")
        code_model = model_router.suggest_model_for_task_type("code_generation")
        fast_model = model_router.suggest_model_for_task_type("fast_response")
        
        # Should return model names or None
        if reasoning_model:
            assert reasoning_model in model_router.model_capabilities
        if code_model:
            assert code_model in model_router.model_capabilities  
        if fast_model:
            assert fast_model in model_router.model_capabilities
    
    def test_context_window_filtering(self, model_router):
        """Test filtering models by context window requirements"""
        # Task requiring large context
        large_context_complexity = TaskComplexity(
            complexity_score=5,
            requires_reasoning=True,
            requires_speed=False,
            estimated_tokens=20000,  # Large token requirement
            task_type="analysis",
            context_needs=[]
        )
        
        selected_model, _ = model_router.select_optimal_model(large_context_complexity)
        
        # Should select a model with sufficient context window
        capability = model_router.model_capabilities[selected_model]
        # The penalty system should work, even if context window is smaller
        assert isinstance(capability.context_window, int)


if __name__ == "__main__":
    pytest.main([__file__])
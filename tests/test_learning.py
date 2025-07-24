"""
Tests for the learning system
"""
import pytest
import tempfile
import shutil
from pathlib import Path
from unittest.mock import patch

import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from core.learning import (
    LearningSystem, LearningEvent, Pattern, FeedbackType,
    get_learning_system
)


@pytest.fixture
def temp_learning_dir():
    """Create a temporary directory for learning data"""
    temp_dir = tempfile.mkdtemp()
    yield temp_dir
    shutil.rmtree(temp_dir)


@pytest.fixture
def learning_system(temp_learning_dir):
    """Create a learning system with temporary directory"""
    with patch('core.learning.get_config') as mock_config:
        mock_config.return_value = None
        
        system = LearningSystem()
        system.learning_dir = Path(temp_learning_dir)
        return system


class TestLearningSystem:
    """Test cases for LearningSystem"""
    
    def test_initialization(self, learning_system):
        """Test learning system initialization"""
        assert learning_system.learning_dir.exists()
        assert len(learning_system.recent_events) == 0
        assert len(learning_system.patterns) == 0
        assert len(learning_system.user_preferences) == 0
    
    def test_record_success_interaction(self, learning_system):
        """Test recording a successful interaction"""
        event_id = learning_system.record_interaction(
            user_input="Create a Python file",
            agent_response="I'll create a Python file for you.",
            context={"task_type": "file_creation", "tool": "file_tool"},
            success_metrics={"completion": 1.0, "user_satisfaction": 0.9}
        )
        
        assert event_id.startswith("event_")
        assert len(learning_system.recent_events) == 1
        
        event = learning_system.recent_events[0]
        assert event.event_type == FeedbackType.SUCCESS
        assert event.user_input == "Create a Python file"
        assert event.success_metrics["completion"] == 1.0
    
    def test_record_correction_interaction(self, learning_system):
        """Test recording a user correction"""
        event_id = learning_system.record_interaction(
            user_input="Show git status",
            agent_response="Here's the git log",
            context={"task_type": "git_operation"},
            user_feedback="No, I asked for git status, not git log"
        )
        
        assert len(learning_system.recent_events) == 1
        
        event = learning_system.recent_events[0]
        assert event.event_type == FeedbackType.USER_CORRECTION
        assert "git status" in event.user_feedback
    
    def test_classify_interaction_success(self, learning_system):
        """Test classifying successful interactions"""
        feedback_type = learning_system._classify_interaction(
            "Great! That's exactly what I needed",
            {"success": 0.9}
        )
        assert feedback_type == FeedbackType.SUCCESS
    
    def test_classify_interaction_correction(self, learning_system):
        """Test classifying correction interactions"""
        feedback_type = learning_system._classify_interaction(
            "Actually, that's wrong. It should be different",
            None
        )
        assert feedback_type == FeedbackType.USER_CORRECTION
    
    def test_classify_interaction_preference(self, learning_system):
        """Test classifying preference interactions"""
        feedback_type = learning_system._classify_interaction(
            "I prefer the other approach instead",
            None
        )
        assert feedback_type == FeedbackType.PREFERENCE
    
    def test_user_preference_learning(self, learning_system):
        """Test learning user preferences"""
        learning_system.record_interaction(
            user_input="Use git to commit changes",
            agent_response="I'll use the git tool",
            context={"task_type": "git_operation", "tool": "git_tool"},
            user_feedback="I prefer detailed explanations of what you're doing"
        )
        
        # Should learn response style preference
        assert "response_style" in learning_system.user_preferences
        assert learning_system.user_preferences["response_style"] == "detailed"
    
    def test_successful_pattern_extraction(self, learning_system):
        """Test extracting successful patterns"""
        learning_system.record_interaction(
            user_input="Create a new Python module",
            agent_response="I'll create a new Python module with proper structure",
            context={"task_type": "file_creation", "tools_used": ["file_tool"]},
            success_metrics={"completion": 1.0}
        )
        
        # Should create a successful pattern  
        assert len(learning_system.patterns) > 0
        
        pattern = list(learning_system.patterns.values())[0]
        assert pattern.pattern_type == "successful_approach"
        assert pattern.success_rate == 1.0
        assert pattern.usage_count == 1
    
    def test_get_suggestions(self, learning_system):
        """Test getting suggestions based on context"""
        # Add a successful pattern
        learning_system.record_interaction(
            user_input="Create Python file",
            agent_response="Creating Python file with imports",
            context={"task_type": "file_creation", "complexity": "low"},
            success_metrics={"completion": 1.0}
        )
        
        # Get suggestions for similar context
        suggestions = learning_system.get_suggestions({
            "task_type": "file_creation",
            "complexity": "low"
        })
        
        assert len(suggestions) > 0
        assert suggestions[0]["type"] == "successful_approach"
        assert suggestions[0]["confidence"] > 0
    
    def test_context_similarity_calculation(self, learning_system):
        """Test context similarity calculation"""
        ctx1 = {"task_type": "file_creation", "complexity": "low", "tool": "file_tool"}
        ctx2 = {"task_type": "file_creation", "complexity": "low", "tool": "git_tool"}
        ctx3 = {"task_type": "git_operation", "complexity": "high", "tool": "git_tool"}
        
        similarity_1_2 = learning_system._calculate_context_similarity(ctx1, ctx2)
        similarity_1_3 = learning_system._calculate_context_similarity(ctx1, ctx3)
        
        # ctx1 and ctx2 should be more similar than ctx1 and ctx3
        assert similarity_1_2 > similarity_1_3
        assert similarity_1_2 > 0.5  # Should be quite similar
        assert similarity_1_3 < 0.5  # Should be less similar
    
    def test_adapt_behavior(self, learning_system):
        """Test behavior adaptation based on learning"""
        # Set some preferences
        learning_system.user_preferences = {
            "preferred_model_file_operations": "fast-model",
            "preferred_tool_file_operations": "file_tool",
            "response_style": "concise"
        }
        
        adaptations = learning_system.adapt_behavior({
            "task_type": "file_operations"
        })
        
        assert "preferred_model" in adaptations
        assert adaptations["preferred_model"] == "fast-model"
        assert "preferred_tool" in adaptations  
        assert adaptations["preferred_tool"] == "file_tool"
        assert "response_style" in adaptations
        assert adaptations["response_style"] == "concise"
    
    def test_performance_metrics(self, learning_system):
        """Test performance metrics tracking"""
        # Record some interactions with metrics
        for i in range(5):
            learning_system.record_interaction(
                user_input=f"Task {i}",
                agent_response=f"Response {i}",
                context={"task_type": "test"},
                success_metrics={"completion": 0.8 + i * 0.05}  # Improving trend
            )
        
        metrics = learning_system.get_performance_metrics()
        
        assert "completion" in metrics
        assert metrics["completion"]["count"] == 5
        assert 0.8 <= metrics["completion"]["average"] <= 1.0
        assert metrics["completion"]["trend"] in ["improving", "stable"]
    
    def test_trend_calculation(self, learning_system):
        """Test trend calculation"""
        # Improving trend
        improving_values = [0.5, 0.6, 0.7, 0.8, 0.9, 0.7, 0.8, 0.9, 0.95, 1.0]
        trend = learning_system._calculate_trend(improving_values)
        assert trend == "improving"
        
        # Declining trend  
        declining_values = [1.0, 0.9, 0.8, 0.7, 0.6, 0.8, 0.7, 0.6, 0.5, 0.4]
        trend = learning_system._calculate_trend(declining_values)
        assert trend == "declining"
        
        # Stable trend
        stable_values = [0.8, 0.75, 0.85, 0.8, 0.82, 0.78, 0.81, 0.79, 0.83, 0.8]
        trend = learning_system._calculate_trend(stable_values)
        assert trend == "stable"
    
    def test_data_persistence(self, learning_system):
        """Test saving and loading learning data"""
        # Add some learning data
        learning_system.record_interaction(
            user_input="Test interaction",
            agent_response="Test response", 
            context={"task_type": "test"},
            success_metrics={"completion": 1.0}
        )
        
        learning_system.user_preferences["test_pref"] = "test_value"
        
        # Save data
        learning_system._save_learning_data()
        
        # Create new system and load data
        new_system = LearningSystem()
        new_system.learning_dir = learning_system.learning_dir
        new_system._load_learning_data()
        
        # Check data was loaded
        assert len(new_system.patterns) > 0
        assert "test_pref" in new_system.user_preferences
        assert new_system.user_preferences["test_pref"] == "test_value"
        assert len(new_system.recent_events) > 0
    
    def test_learning_summary(self, learning_system):
        """Test getting learning summary"""
        # Add some data
        learning_system.record_interaction(
            user_input="Test", 
            agent_response="Response",
            context={"task_type": "test"},
            success_metrics={"completion": 1.0}
        )
        
        summary = learning_system.get_learning_summary()
        
        assert "patterns_learned" in summary
        assert "user_preferences" in summary
        assert "recent_interactions" in summary
        assert "learning_data_path" in summary
        assert "top_patterns" in summary
        
        assert summary["patterns_learned"] > 0
        assert summary["recent_interactions"] > 0
        assert isinstance(summary["top_patterns"], list)


def test_global_learning_system():
    """Test the global learning system getter"""
    system1 = get_learning_system()
    system2 = get_learning_system()
    
    # Should return the same instance
    assert system1 is system2


if __name__ == "__main__":
    pytest.main([__file__])
"""
Learning and adaptation system for improving agent performance
"""
import json
import time
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, asdict
from collections import defaultdict, deque
from enum import Enum

from .config import ConfigManager, get_config


class FeedbackType(Enum):
    SUCCESS = "success"
    FAILURE = "failure" 
    USER_CORRECTION = "user_correction"
    PERFORMANCE = "performance"
    PREFERENCE = "preference"


@dataclass
class LearningEvent:
    """Represents a learning event from user interaction"""
    id: str
    timestamp: float
    event_type: FeedbackType
    context: Dict[str, Any]
    user_input: str
    agent_response: str
    user_feedback: Optional[str] = None
    success_metrics: Optional[Dict[str, float]] = None
    metadata: Dict[str, Any] = None

    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


@dataclass
class Pattern:
    """Represents a learned pattern"""
    pattern_id: str
    pattern_type: str  # "successful_approach", "common_error", "user_preference"
    context_features: Dict[str, Any]
    response_template: Optional[str] = None
    confidence_score: float = 0.5
    usage_count: int = 0
    success_rate: float = 0.0
    created_at: float = 0.0
    last_used: float = 0.0


class LearningSystem:
    """Learns from user interactions and adapts behavior"""
    
    def __init__(self, config: Optional[ConfigManager] = None):
        self.config = config or get_config()
        self.learning_dir = Path("learning_data")
        self.learning_dir.mkdir(exist_ok=True)
        
        # In-memory storage for active learning
        self.recent_events: deque = deque(maxlen=1000)
        self.patterns: Dict[str, Pattern] = {}
        self.user_preferences: Dict[str, Any] = {}
        self.success_metrics: Dict[str, List[float]] = defaultdict(list)
        
        # Load existing learning data
        self._load_learning_data()
    
    def record_interaction(
        self,
        user_input: str,
        agent_response: str,
        context: Dict[str, Any],
        user_feedback: Optional[str] = None,
        success_metrics: Optional[Dict[str, float]] = None
    ) -> str:
        """Record a user interaction for learning"""
        
        event_id = f"event_{int(time.time())}_{len(self.recent_events)}"
        
        # Determine event type based on feedback and metrics
        event_type = self._classify_interaction(user_feedback, success_metrics)
        
        event = LearningEvent(
            id=event_id,
            timestamp=time.time(),
            event_type=event_type,
            context=context,
            user_input=user_input,
            agent_response=agent_response,
            user_feedback=user_feedback,
            success_metrics=success_metrics
        )
        
        self.recent_events.append(event)
        
        # Trigger learning from this event
        self._learn_from_event(event)
        
        # Periodically save learning data
        if len(self.recent_events) % 10 == 0:
            self._save_learning_data()
        
        return event_id
    
    def _classify_interaction(
        self,
        user_feedback: Optional[str],
        success_metrics: Optional[Dict[str, float]]
    ) -> FeedbackType:
        """Classify the type of interaction for learning"""
        
        if user_feedback:
            feedback_lower = user_feedback.lower()
            
            # Look for explicit corrections
            correction_indicators = ["actually", "no", "wrong", "incorrect", "should be", "meant"]
            if any(indicator in feedback_lower for indicator in correction_indicators):
                return FeedbackType.USER_CORRECTION
            
            # Look for positive feedback
            positive_indicators = ["good", "great", "perfect", "correct", "thanks", "exactly"]
            if any(indicator in feedback_lower for indicator in positive_indicators):
                return FeedbackType.SUCCESS
            
            # Look for preferences
            preference_indicators = ["prefer", "like", "better", "instead", "rather"]
            if any(indicator in feedback_lower for indicator in preference_indicators):
                return FeedbackType.PREFERENCE
        
        if success_metrics:
            # Use metrics to determine success/failure
            avg_success = sum(success_metrics.values()) / len(success_metrics)
            if avg_success > 0.7:
                return FeedbackType.SUCCESS
            elif avg_success < 0.3:
                return FeedbackType.FAILURE
            else:
                return FeedbackType.PERFORMANCE
        
        return FeedbackType.PERFORMANCE
    
    def _learn_from_event(self, event: LearningEvent) -> None:
        """Extract patterns and update learning from an event"""
        
        # Update success metrics
        if event.success_metrics:
            for metric, value in event.success_metrics.items():
                self.success_metrics[metric].append(value)
                # Keep only recent metrics
                if len(self.success_metrics[metric]) > 100:
                    self.success_metrics[metric] = self.success_metrics[metric][-100:]
        
        # Learn user preferences
        if event.event_type == FeedbackType.PREFERENCE:
            self._update_user_preferences(event)
        
        # Learn successful patterns
        if event.event_type == FeedbackType.SUCCESS:
            self._extract_successful_pattern(event)
        
        # Learn from corrections
        if event.event_type == FeedbackType.USER_CORRECTION:
            self._learn_from_correction(event)
    
    def _update_user_preferences(self, event: LearningEvent) -> None:
        """Update user preferences based on feedback"""
        
        context = event.context
        feedback = event.user_feedback or ""
        
        # Extract preferences from context and feedback
        preferences = {}
        
        # Tool preferences
        if "tool" in context:
            tool_name = context["tool"]
            if "prefer" in feedback.lower():
                preferences[f"preferred_tool_{context.get('task_type', 'general')}"] = tool_name
        
        # Response style preferences
        if any(word in feedback.lower() for word in ["brief", "short", "concise"]):
            preferences["response_style"] = "concise"
        elif any(word in feedback.lower() for word in ["detailed", "verbose", "explain"]):
            preferences["response_style"] = "detailed"
        
        # Model preferences
        if "model" in context:
            model_name = context["model"]
            task_type = context.get("task_type", "general")
            if "better" in feedback.lower() or "prefer" in feedback.lower():
                preferences[f"preferred_model_{task_type}"] = model_name
        
        # Update preferences
        self.user_preferences.update(preferences)
    
    def _extract_successful_pattern(self, event: LearningEvent) -> None:
        """Extract successful patterns from positive interactions"""
        
        pattern_id = f"success_{hash(event.user_input + event.agent_response) % 10000}"
        
        # Extract context features
        context_features = {
            "task_type": event.context.get("task_type", "unknown"),
            "tools_used": event.context.get("tools_used", []),
            "complexity": event.context.get("complexity", "medium"),
            "user_input_length": len(event.user_input),
            "response_length": len(event.agent_response)
        }
        
        # Create or update pattern
        if pattern_id in self.patterns:
            pattern = self.patterns[pattern_id]
            pattern.usage_count += 1
            pattern.success_rate = (pattern.success_rate + 1.0) / 2  # Running average
            pattern.last_used = time.time()
            pattern.confidence_score = min(1.0, pattern.confidence_score + 0.1)
        else:
            pattern = Pattern(
                pattern_id=pattern_id,
                pattern_type="successful_approach",
                context_features=context_features,
                response_template=self._generalize_response(event.agent_response),
                confidence_score=0.6,
                usage_count=1,
                success_rate=1.0,
                created_at=time.time(),
                last_used=time.time()
            )
            self.patterns[pattern_id] = pattern
    
    def _learn_from_correction(self, event: LearningEvent) -> None:
        """Learn from user corrections"""
        
        correction = event.user_feedback or ""
        
        # Extract the corrected information
        correction_patterns = self._extract_correction_patterns(event.user_input, correction)
        
        for pattern_id, pattern_data in correction_patterns.items():
            pattern = Pattern(
                pattern_id=pattern_id,
                pattern_type="common_error",
                context_features=pattern_data["context"],
                response_template=pattern_data["correction"],
                confidence_score=0.8,
                usage_count=1,
                success_rate=1.0,
                created_at=time.time(),
                last_used=time.time()
            )
            self.patterns[pattern_id] = pattern
    
    def _extract_correction_patterns(self, user_input: str, correction: str) -> Dict[str, Dict[str, Any]]:
        """Extract patterns from user corrections"""
        
        patterns = {}
        
        # Simple pattern extraction based on common correction phrases
        if "should be" in correction.lower():
            parts = correction.lower().split("should be")
            if len(parts) == 2:
                wrong_part = parts[0].strip()
                correct_part = parts[1].strip()
                
                pattern_id = f"correction_{hash(wrong_part + correct_part) % 10000}"
                patterns[pattern_id] = {
                    "context": {"incorrect": wrong_part, "correct": correct_part},
                    "correction": f"Use '{correct_part}' instead of '{wrong_part}'"
                }
        
        return patterns
    
    def _generalize_response(self, response: str) -> str:
        """Create a generalized template from a successful response"""
        
        # Simple template creation - replace specific values with placeholders
        template = response
        
        # Replace file paths
        import re
        template = re.sub(r'/[^\s]+\.(py|js|txt|md)', '[FILE_PATH]', template)
        
        # Replace numbers
        template = re.sub(r'\b\d+\b', '[NUMBER]', template)
        
        # Replace specific identifiers
        template = re.sub(r'\b[a-zA-Z_][a-zA-Z0-9_]*\.(py|js)', '[FILE_NAME]', template)
        
        return template
    
    def get_suggestions(self, context: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Get suggestions based on learned patterns"""
        
        suggestions = []
        
        # Get relevant patterns
        relevant_patterns = self._find_relevant_patterns(context)
        
        for pattern in relevant_patterns[:5]:  # Top 5 suggestions
            suggestion = {
                "type": pattern.pattern_type,
                "confidence": pattern.confidence_score,
                "suggestion": pattern.response_template,
                "context": pattern.context_features,
                "usage_count": pattern.usage_count,
                "success_rate": pattern.success_rate
            }
            suggestions.append(suggestion)
        
        return suggestions
    
    def _find_relevant_patterns(self, context: Dict[str, Any]) -> List[Pattern]:
        """Find patterns relevant to the current context"""
        
        relevant_patterns = []
        
        for pattern in self.patterns.values():
            similarity = self._calculate_context_similarity(context, pattern.context_features)
            
            if similarity > 0.3:  # Threshold for relevance
                # Adjust confidence based on similarity and recency
                adjusted_confidence = pattern.confidence_score * similarity
                
                # Boost recent patterns
                time_factor = max(0.1, 1.0 - (time.time() - pattern.last_used) / (30 * 24 * 3600))  # 30 days
                adjusted_confidence *= (1 + time_factor * 0.5)
                
                pattern.confidence_score = adjusted_confidence
                relevant_patterns.append(pattern)
        
        # Sort by confidence
        relevant_patterns.sort(key=lambda p: p.confidence_score, reverse=True)
        return relevant_patterns
    
    def _calculate_context_similarity(self, ctx1: Dict[str, Any], ctx2: Dict[str, Any]) -> float:
        """Calculate similarity between two contexts"""
        
        if not ctx1 or not ctx2:
            return 0.0
        
        common_keys = set(ctx1.keys()) & set(ctx2.keys())
        if not common_keys:
            return 0.0
        
        matches = 0
        total = len(common_keys)
        
        for key in common_keys:
            if ctx1[key] == ctx2[key]:
                matches += 1
            elif isinstance(ctx1[key], (int, float)) and isinstance(ctx2[key], (int, float)):
                # Numeric similarity
                diff = abs(ctx1[key] - ctx2[key])
                max_val = max(abs(ctx1[key]), abs(ctx2[key]), 1)
                similarity = 1 - (diff / max_val)
                matches += similarity
        
        return matches / total
    
    def get_user_preferences(self) -> Dict[str, Any]:
        """Get current user preferences"""
        return self.user_preferences.copy()
    
    def get_performance_metrics(self) -> Dict[str, Dict[str, float]]:
        """Get performance metrics summary"""
        
        metrics_summary = {}
        
        for metric_name, values in self.success_metrics.items():
            if values:
                metrics_summary[metric_name] = {
                    "average": sum(values) / len(values),
                    "recent_average": sum(values[-10:]) / len(values[-10:]) if len(values) >= 10 else sum(values) / len(values),
                    "trend": self._calculate_trend(values),
                    "count": len(values)
                }
        
        return metrics_summary
    
    def _calculate_trend(self, values: List[float]) -> str:
        """Calculate trend direction for metrics"""
        
        if len(values) < 5:
            return "insufficient_data"
        
        recent = sum(values[-5:]) / 5
        older = sum(values[-10:-5]) / 5 if len(values) >= 10 else sum(values[:-5]) / len(values[:-5])
        
        if recent > older * 1.1:
            return "improving"
        elif recent < older * 0.9:
            return "declining"
        else:
            return "stable"
    
    def adapt_behavior(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Adapt behavior based on learned patterns and preferences"""
        
        adaptations = {}
        
        # Apply user preferences
        task_type = context.get("task_type", "general")
        
        # Model preferences
        preferred_model_key = f"preferred_model_{task_type}"
        if preferred_model_key in self.user_preferences:
            adaptations["preferred_model"] = self.user_preferences[preferred_model_key]
        
        # Tool preferences
        preferred_tool_key = f"preferred_tool_{task_type}"
        if preferred_tool_key in self.user_preferences:
            adaptations["preferred_tool"] = self.user_preferences[preferred_tool_key]
        
        # Response style
        if "response_style" in self.user_preferences:
            adaptations["response_style"] = self.user_preferences["response_style"]
        
        # Get pattern-based suggestions
        suggestions = self.get_suggestions(context)
        if suggestions:
            adaptations["pattern_suggestions"] = suggestions[:3]  # Top 3
        
        return adaptations
    
    def _save_learning_data(self) -> None:
        """Save learning data to disk"""
        
        try:
            # Save patterns
            patterns_file = self.learning_dir / "patterns.json"
            patterns_data = {pid: asdict(pattern) for pid, pattern in self.patterns.items()}
            with open(patterns_file, 'w') as f:
                json.dump(patterns_data, f, indent=2, default=str)
            
            # Save preferences
            preferences_file = self.learning_dir / "preferences.json"
            with open(preferences_file, 'w') as f:
                json.dump(self.user_preferences, f, indent=2)
            
            # Save recent events (last 100)
            events_file = self.learning_dir / "recent_events.json"
            recent_events_data = [asdict(event) for event in list(self.recent_events)[-100:]]
            with open(events_file, 'w') as f:
                json.dump(recent_events_data, f, indent=2, default=str)
                
        except Exception as e:
            print(f"Warning: Could not save learning data: {e}")
    
    def _load_learning_data(self) -> None:
        """Load existing learning data from disk"""
        
        try:
            # Load patterns
            patterns_file = self.learning_dir / "patterns.json"
            if patterns_file.exists():
                with open(patterns_file, 'r') as f:
                    patterns_data = json.load(f)
                
                for pid, data in patterns_data.items():
                    self.patterns[pid] = Pattern(**data)
            
            # Load preferences
            preferences_file = self.learning_dir / "preferences.json"
            if preferences_file.exists():
                with open(preferences_file, 'r') as f:
                    self.user_preferences = json.load(f)
            
            # Load recent events
            events_file = self.learning_dir / "recent_events.json"
            if events_file.exists():
                with open(events_file, 'r') as f:
                    events_data = json.load(f)
                
                for event_data in events_data:
                    event = LearningEvent(**event_data)
                    self.recent_events.append(event)
                    
        except Exception as e:
            print(f"Warning: Could not load learning data: {e}")
    
    def get_learning_summary(self) -> Dict[str, Any]:
        """Get summary of current learning state"""
        
        return {
            "patterns_learned": len(self.patterns),
            "user_preferences": len(self.user_preferences),
            "recent_interactions": len(self.recent_events),
            "performance_metrics": list(self.success_metrics.keys()),
            "learning_data_path": str(self.learning_dir),
            "top_patterns": [
                {
                    "id": p.pattern_id,
                    "type": p.pattern_type,
                    "confidence": p.confidence_score,
                    "usage": p.usage_count,
                    "success_rate": p.success_rate
                }
                for p in sorted(self.patterns.values(), key=lambda x: x.confidence_score, reverse=True)[:5]
            ]
        }


# Global learning system instance
_learning_system: Optional[LearningSystem] = None


def get_learning_system() -> LearningSystem:
    """Get global learning system instance"""
    global _learning_system
    if _learning_system is None:
        _learning_system = LearningSystem()
    return _learning_system
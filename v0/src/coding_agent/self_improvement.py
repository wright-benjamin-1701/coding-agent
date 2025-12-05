"""Self-improvement loop system for continuous learning and adaptation."""

import json
import time
import hashlib
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Tuple
from collections import defaultdict, Counter
from dataclasses import dataclass, asdict
from .types import ToolResult
from .providers.base import ModelProvider


@dataclass
class InteractionRecord:
    """Record of an interaction for learning purposes."""
    timestamp: datetime
    user_prompt: str
    agent_response: str
    tools_used: List[str]
    success: bool
    execution_time: float
    user_feedback: Optional[str] = None
    improvement_score: Optional[float] = None
    context_hash: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        data = asdict(self)
        data['timestamp'] = self.timestamp.isoformat()
        return data
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'InteractionRecord':
        """Create from dictionary."""
        data['timestamp'] = datetime.fromisoformat(data['timestamp'])
        return cls(**data)


@dataclass
class LearningInsight:
    """A learning insight derived from interaction analysis."""
    insight_type: str  # pattern, failure, optimization, user_preference
    description: str
    confidence: float
    evidence: List[str]
    suggested_action: str
    created_at: datetime
    applied: bool = False
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        data = asdict(self)
        data['created_at'] = self.created_at.isoformat()
        return data
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'LearningInsight':
        """Create from dictionary."""
        data['created_at'] = datetime.fromisoformat(data['created_at'])
        return cls(**data)


class InteractionAnalyzer:
    """Analyze interaction patterns for learning opportunities."""
    
    def __init__(self):
        self.pattern_thresholds = {
            'min_interactions_for_pattern': 5,
            'pattern_confidence_threshold': 0.7,
            'failure_pattern_threshold': 0.3
        }
    
    def analyze_interactions(self, interactions: List[InteractionRecord]) -> List[LearningInsight]:
        """Analyze interactions to extract learning insights."""
        insights = []
        
        if len(interactions) < self.pattern_thresholds['min_interactions_for_pattern']:
            return insights
        
        # Analyze different aspects
        insights.extend(self._analyze_failure_patterns(interactions))
        insights.extend(self._analyze_tool_usage_patterns(interactions))
        insights.extend(self._analyze_user_preferences(interactions))
        insights.extend(self._analyze_performance_patterns(interactions))
        insights.extend(self._analyze_success_patterns(interactions))
        
        return insights
    
    def _analyze_failure_patterns(self, interactions: List[InteractionRecord]) -> List[LearningInsight]:
        """Identify patterns in failed interactions."""
        insights = []
        failed_interactions = [i for i in interactions if not i.success]
        
        if len(failed_interactions) < 3:
            return insights
        
        # Group failures by common characteristics
        failure_groups = defaultdict(list)
        
        for interaction in failed_interactions:
            # Group by tools used
            tools_key = tuple(sorted(interaction.tools_used))
            failure_groups[f"tools_{tools_key}"].append(interaction)
            
            # Group by prompt patterns
            prompt_words = set(interaction.user_prompt.lower().split())
            for word in prompt_words:
                if len(word) > 3:  # Skip short words
                    failure_groups[f"keyword_{word}"].append(interaction)
        
        # Identify significant failure patterns
        total_interactions = len(interactions)
        for group_key, group_failures in failure_groups.items():
            if len(group_failures) >= 2:
                failure_rate = len(group_failures) / total_interactions
                if failure_rate > self.pattern_thresholds['failure_pattern_threshold']:
                    
                    evidence = [f"Failed {len(group_failures)} times out of {total_interactions} total interactions"]
                    evidence.extend([f"Example: {f.user_prompt[:100]}..." for f in group_failures[:3]])
                    
                    if group_key.startswith("tools_"):
                        tools = group_key[6:]
                        description = f"High failure rate when using tools: {tools}"
                        action = f"Review tool usage patterns and error handling for: {tools}"
                    elif group_key.startswith("keyword_"):
                        keyword = group_key[8:]
                        description = f"High failure rate with '{keyword}' requests"
                        action = f"Improve handling of '{keyword}' related requests"
                    else:
                        continue
                    
                    insights.append(LearningInsight(
                        insight_type="failure",
                        description=description,
                        confidence=min(0.9, failure_rate * 2),
                        evidence=evidence,
                        suggested_action=action,
                        created_at=datetime.now()
                    ))
        
        return insights
    
    def _analyze_tool_usage_patterns(self, interactions: List[InteractionRecord]) -> List[LearningInsight]:
        """Analyze tool usage patterns for optimization."""
        insights = []
        
        # Count tool usage frequency
        tool_usage = Counter()
        tool_combinations = Counter()
        tool_success_rates = defaultdict(lambda: {'success': 0, 'total': 0})
        
        for interaction in interactions:
            for tool in interaction.tools_used:
                tool_usage[tool] += 1
                tool_success_rates[tool]['total'] += 1
                if interaction.success:
                    tool_success_rates[tool]['success'] += 1
            
            if len(interaction.tools_used) > 1:
                combo = tuple(sorted(interaction.tools_used))
                tool_combinations[combo] += 1
        
        # Identify underused but successful tools
        for tool, count in tool_usage.most_common():
            if count < len(interactions) * 0.1:  # Used in less than 10% of interactions
                success_rate = tool_success_rates[tool]['success'] / tool_success_rates[tool]['total']
                if success_rate > 0.8:  # But highly successful when used
                    insights.append(LearningInsight(
                        insight_type="optimization",
                        description=f"Tool '{tool}' is underused but highly successful",
                        confidence=success_rate,
                        evidence=[
                            f"Used in only {count}/{len(interactions)} interactions ({count/len(interactions)*100:.1f}%)",
                            f"Success rate: {success_rate*100:.1f}%"
                        ],
                        suggested_action=f"Consider using '{tool}' more frequently for relevant tasks",
                        created_at=datetime.now()
                    ))
        
        # Identify effective tool combinations
        if tool_combinations:
            total_interactions = len(interactions)
            for combo, count in tool_combinations.most_common(5):
                if count >= 3:  # At least 3 uses
                    combo_interactions = [i for i in interactions if set(i.tools_used) == set(combo)]
                    success_rate = sum(1 for i in combo_interactions if i.success) / len(combo_interactions)
                    
                    if success_rate > 0.8:
                        insights.append(LearningInsight(
                            insight_type="pattern",
                            description=f"Tool combination {combo} is highly effective",
                            confidence=success_rate,
                            evidence=[
                                f"Used {count} times with {success_rate*100:.1f}% success rate",
                                f"Tools: {', '.join(combo)}"
                            ],
                            suggested_action=f"Promote using tools {combo} together for relevant tasks",
                            created_at=datetime.now()
                        ))
        
        return insights
    
    def _analyze_user_preferences(self, interactions: List[InteractionRecord]) -> List[LearningInsight]:
        """Analyze user preferences and feedback patterns."""
        insights = []
        
        # Analyze feedback patterns
        feedback_interactions = [i for i in interactions if i.user_feedback]
        if len(feedback_interactions) < 3:
            return insights
        
        # Categorize feedback
        positive_feedback = [i for i in feedback_interactions if self._is_positive_feedback(i.user_feedback)]
        negative_feedback = [i for i in feedback_interactions if self._is_negative_feedback(i.user_feedback)]
        
        # Find patterns in positive feedback
        if positive_feedback:
            common_tools = Counter()
            for interaction in positive_feedback:
                for tool in interaction.tools_used:
                    common_tools[tool] += 1
            
            if common_tools:
                top_tool = common_tools.most_common(1)[0]
                insights.append(LearningInsight(
                    insight_type="user_preference",
                    description=f"Users appreciate when '{top_tool[0]}' tool is used",
                    confidence=top_tool[1] / len(positive_feedback),
                    evidence=[
                        f"Tool '{top_tool[0]}' appeared in {top_tool[1]}/{len(positive_feedback)} positive feedback interactions",
                        f"Examples: {', '.join([i.user_feedback[:50] + '...' for i in positive_feedback[:3]])}"
                    ],
                    suggested_action=f"Prioritize using '{top_tool[0]}' when applicable",
                    created_at=datetime.now()
                ))
        
        # Find patterns in negative feedback
        if negative_feedback:
            common_issues = Counter()
            for interaction in negative_feedback:
                # Simple keyword analysis
                feedback_lower = interaction.user_feedback.lower()
                if 'slow' in feedback_lower or 'time' in feedback_lower:
                    common_issues['performance'] += 1
                if 'wrong' in feedback_lower or 'incorrect' in feedback_lower:
                    common_issues['accuracy'] += 1
                if 'confusing' in feedback_lower or 'unclear' in feedback_lower:
                    common_issues['clarity'] += 1
            
            if common_issues:
                top_issue = common_issues.most_common(1)[0]
                insights.append(LearningInsight(
                    insight_type="user_preference",
                    description=f"Users frequently complain about {top_issue[0]} issues",
                    confidence=top_issue[1] / len(negative_feedback),
                    evidence=[
                        f"{top_issue[0]} mentioned in {top_issue[1]}/{len(negative_feedback)} negative feedback interactions"
                    ],
                    suggested_action=f"Focus on improving {top_issue[0]} in responses",
                    created_at=datetime.now()
                ))
        
        return insights
    
    def _analyze_performance_patterns(self, interactions: List[InteractionRecord]) -> List[LearningInsight]:
        """Analyze performance patterns for optimization."""
        insights = []
        
        # Analyze execution times
        execution_times = [i.execution_time for i in interactions if i.execution_time > 0]
        if len(execution_times) < 5:
            return insights
        
        avg_time = sum(execution_times) / len(execution_times)
        slow_interactions = [i for i in interactions if i.execution_time > avg_time * 2]
        
        if slow_interactions:
            # Find patterns in slow interactions
            slow_tools = Counter()
            for interaction in slow_interactions:
                for tool in interaction.tools_used:
                    slow_tools[tool] += 1
            
            if slow_tools:
                slowest_tool = slow_tools.most_common(1)[0]
                tool_times = [i.execution_time for i in interactions if slowest_tool[0] in i.tools_used]
                avg_tool_time = sum(tool_times) / len(tool_times)
                
                insights.append(LearningInsight(
                    insight_type="optimization",
                    description=f"Tool '{slowest_tool[0]}' causes performance issues",
                    confidence=0.8,
                    evidence=[
                        f"Appears in {slowest_tool[1]}/{len(slow_interactions)} slow interactions",
                        f"Average execution time with this tool: {avg_tool_time:.2f}s"
                    ],
                    suggested_action=f"Optimize '{slowest_tool[0]}' tool or use alternatives",
                    created_at=datetime.now()
                ))
        
        return insights
    
    def _analyze_success_patterns(self, interactions: List[InteractionRecord]) -> List[LearningInsight]:
        """Analyze successful interaction patterns."""
        insights = []
        
        successful_interactions = [i for i in interactions if i.success]
        if len(successful_interactions) < 5:
            return insights
        
        # Find patterns in successful interactions
        success_tools = Counter()
        success_contexts = Counter()
        
        for interaction in successful_interactions:
            for tool in interaction.tools_used:
                success_tools[tool] += 1
            
            # Simple context analysis based on prompt keywords
            prompt_words = [word.lower() for word in interaction.user_prompt.split() if len(word) > 4]
            for word in prompt_words[:5]:  # Top 5 keywords
                success_contexts[word] += 1
        
        # Identify highly successful patterns
        total_successful = len(successful_interactions)
        for tool, count in success_tools.most_common(3):
            if count > total_successful * 0.3:  # Used in more than 30% of successes
                insights.append(LearningInsight(
                    insight_type="pattern",
                    description=f"Tool '{tool}' is key to successful interactions",
                    confidence=count / total_successful,
                    evidence=[
                        f"Used in {count}/{total_successful} successful interactions ({count/total_successful*100:.1f}%)"
                    ],
                    suggested_action=f"Continue leveraging '{tool}' tool for similar tasks",
                    created_at=datetime.now()
                ))
        
        return insights
    
    def _is_positive_feedback(self, feedback: str) -> bool:
        """Determine if feedback is positive."""
        positive_words = ['good', 'great', 'excellent', 'perfect', 'helpful', 'thanks', 'amazing']
        return any(word in feedback.lower() for word in positive_words)
    
    def _is_negative_feedback(self, feedback: str) -> bool:
        """Determine if feedback is negative."""
        negative_words = ['bad', 'wrong', 'terrible', 'awful', 'useless', 'slow', 'confusing']
        return any(word in feedback.lower() for word in negative_words)


class SelfImprovementLoop:
    """Main self-improvement system that learns from interactions."""
    
    def __init__(self, model_provider: Optional[ModelProvider] = None, data_dir: str = ".agent_learning"):
        self.model_provider = model_provider
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(exist_ok=True)
        
        self.interactions_file = self.data_dir / "interactions.jsonl"
        self.insights_file = self.data_dir / "insights.json"
        self.metrics_file = self.data_dir / "metrics.json"
        
        self.analyzer = InteractionAnalyzer()
        self.interactions = []
        self.insights = []
        self.metrics = {}
        
        self._load_data()
    
    def _load_data(self):
        """Load existing data from disk."""
        # Load interactions
        if self.interactions_file.exists():
            with open(self.interactions_file, 'r', encoding='utf-8') as f:
                for line in f:
                    try:
                        data = json.loads(line.strip())
                        self.interactions.append(InteractionRecord.from_dict(data))
                    except Exception:
                        continue
        
        # Load insights
        if self.insights_file.exists():
            try:
                with open(self.insights_file, 'r', encoding='utf-8') as f:
                    insights_data = json.load(f)
                    self.insights = [LearningInsight.from_dict(data) for data in insights_data]
            except Exception:
                pass
        
        # Load metrics
        if self.metrics_file.exists():
            try:
                with open(self.metrics_file, 'r', encoding='utf-8') as f:
                    self.metrics = json.load(f)
            except Exception:
                self.metrics = {}
    
    def _save_data(self):
        """Save data to disk."""
        # Save interactions (append mode)
        with open(self.interactions_file, 'w', encoding='utf-8') as f:
            for interaction in self.interactions:
                f.write(json.dumps(interaction.to_dict()) + '\n')
        
        # Save insights
        with open(self.insights_file, 'w', encoding='utf-8') as f:
            json.dump([insight.to_dict() for insight in self.insights], f, indent=2)
        
        # Save metrics
        with open(self.metrics_file, 'w', encoding='utf-8') as f:
            json.dump(self.metrics, f, indent=2)
    
    def record_interaction(self, user_prompt: str, agent_response: str, tools_used: List[str], 
                          success: bool, execution_time: float, context_data: Dict[str, Any] = None) -> str:
        """Record an interaction for learning purposes."""
        # Create context hash for deduplication
        context_str = json.dumps(context_data or {}, sort_keys=True)
        context_hash = hashlib.md5((user_prompt + context_str).encode()).hexdigest()
        
        interaction = InteractionRecord(
            timestamp=datetime.now(),
            user_prompt=user_prompt,
            agent_response=agent_response,
            tools_used=tools_used,
            success=success,
            execution_time=execution_time,
            context_hash=context_hash
        )
        
        self.interactions.append(interaction)
        
        # Keep only recent interactions (last 1000)
        if len(self.interactions) > 1000:
            self.interactions = self.interactions[-1000:]
        
        self._save_data()
        return context_hash
    
    def add_user_feedback(self, interaction_hash: str, feedback: str, score: float = None):
        """Add user feedback to a recorded interaction."""
        for interaction in self.interactions:
            if interaction.context_hash == interaction_hash:
                interaction.user_feedback = feedback
                interaction.improvement_score = score
                break
        
        self._save_data()
    
    def analyze_and_learn(self) -> List[LearningInsight]:
        """Analyze interactions and generate learning insights."""
        # Only analyze recent interactions (last 30 days)
        cutoff_date = datetime.now() - timedelta(days=30)
        recent_interactions = [i for i in self.interactions if i.timestamp > cutoff_date]
        
        if len(recent_interactions) < 5:
            return []
        
        # Generate new insights
        new_insights = self.analyzer.analyze_interactions(recent_interactions)
        
        # Filter out duplicate insights
        existing_descriptions = {insight.description for insight in self.insights}
        unique_insights = [insight for insight in new_insights if insight.description not in existing_descriptions]
        
        self.insights.extend(unique_insights)
        
        # Keep only recent insights (last 50)
        self.insights.sort(key=lambda x: x.created_at, reverse=True)
        self.insights = self.insights[:50]
        
        self._update_metrics()
        self._save_data()
        
        return unique_insights
    
    def get_active_insights(self, insight_type: str = None) -> List[LearningInsight]:
        """Get active (not yet applied) insights."""
        insights = [insight for insight in self.insights if not insight.applied]
        
        if insight_type:
            insights = [insight for insight in insights if insight.insight_type == insight_type]
        
        return sorted(insights, key=lambda x: x.confidence, reverse=True)
    
    def apply_insight(self, insight: LearningInsight) -> bool:
        """Mark an insight as applied."""
        for stored_insight in self.insights:
            if (stored_insight.description == insight.description and 
                stored_insight.created_at == insight.created_at):
                stored_insight.applied = True
                self._save_data()
                return True
        return False
    
    def get_improvement_recommendations(self) -> Dict[str, Any]:
        """Get actionable improvement recommendations."""
        recommendations = {
            'high_priority': [],
            'medium_priority': [],
            'low_priority': [],
            'metrics': self.get_current_metrics()
        }
        
        active_insights = self.get_active_insights()
        
        for insight in active_insights:
            priority = 'low_priority'
            if insight.confidence > 0.8 and insight.insight_type in ['failure', 'user_preference']:
                priority = 'high_priority'
            elif insight.confidence > 0.6:
                priority = 'medium_priority'
            
            recommendations[priority].append({
                'type': insight.insight_type,
                'description': insight.description,
                'action': insight.suggested_action,
                'confidence': insight.confidence,
                'evidence': insight.evidence
            })
        
        return recommendations
    
    def get_current_metrics(self) -> Dict[str, Any]:
        """Get current performance metrics."""
        if not self.interactions:
            return {}
        
        recent_interactions = self.interactions[-100:]  # Last 100 interactions
        
        success_rate = sum(1 for i in recent_interactions if i.success) / len(recent_interactions)
        avg_execution_time = sum(i.execution_time for i in recent_interactions) / len(recent_interactions)
        
        tool_usage = Counter()
        for interaction in recent_interactions:
            for tool in interaction.tools_used:
                tool_usage[tool] += 1
        
        feedback_interactions = [i for i in recent_interactions if i.user_feedback]
        positive_feedback_rate = 0
        if feedback_interactions:
            positive_feedback_rate = sum(1 for i in feedback_interactions 
                                       if self.analyzer._is_positive_feedback(i.user_feedback)) / len(feedback_interactions)
        
        return {
            'success_rate': success_rate,
            'avg_execution_time': avg_execution_time,
            'total_interactions': len(self.interactions),
            'recent_interactions': len(recent_interactions),
            'positive_feedback_rate': positive_feedback_rate,
            'most_used_tools': dict(tool_usage.most_common(5)),
            'insights_generated': len(self.insights),
            'unapplied_insights': len(self.get_active_insights())
        }
    
    def _update_metrics(self):
        """Update internal metrics."""
        self.metrics = self.get_current_metrics()
        self.metrics['last_analysis'] = datetime.now().isoformat()
    
    def generate_self_improvement_report(self) -> str:
        """Generate a comprehensive self-improvement report."""
        recommendations = self.get_improvement_recommendations()
        metrics = recommendations['metrics']
        
        report_parts = [
            "📊 Self-Improvement Analysis Report\n",
            f"**Current Performance Metrics:**",
            f"   • Success Rate: {metrics.get('success_rate', 0)*100:.1f}%",
            f"   • Average Execution Time: {metrics.get('avg_execution_time', 0):.2f}s",
            f"   • Total Interactions: {metrics.get('total_interactions', 0)}",
            f"   • Positive Feedback Rate: {metrics.get('positive_feedback_rate', 0)*100:.1f}%",
            f"   • Insights Generated: {metrics.get('insights_generated', 0)}",
            ""
        ]
        
        if recommendations['high_priority']:
            report_parts.append("🔴 **High Priority Improvements:**")
            for rec in recommendations['high_priority']:
                report_parts.append(f"   • {rec['description']}")
                report_parts.append(f"     Action: {rec['action']}")
                report_parts.append(f"     Confidence: {rec['confidence']*100:.1f}%")
                report_parts.append("")
        
        if recommendations['medium_priority']:
            report_parts.append("🟡 **Medium Priority Improvements:**")
            for rec in recommendations['medium_priority']:
                report_parts.append(f"   • {rec['description']}")
                report_parts.append(f"     Action: {rec['action']}")
                report_parts.append("")
        
        if recommendations['low_priority']:
            report_parts.append("🟢 **Low Priority Optimizations:**")
            for rec in recommendations['low_priority'][:3]:  # Show top 3
                report_parts.append(f"   • {rec['description']}")
                report_parts.append(f"     Action: {rec['action']}")
            report_parts.append("")
        
        # Tool usage insights
        if metrics.get('most_used_tools'):
            report_parts.append("🔧 **Tool Usage Analysis:**")
            for tool, count in metrics['most_used_tools'].items():
                percentage = count / metrics.get('recent_interactions', 1) * 100
                report_parts.append(f"   • {tool}: {count} uses ({percentage:.1f}%)")
            report_parts.append("")
        
        report_parts.append("💡 **Next Steps:**")
        report_parts.append("   1. Address high-priority improvements first")
        report_parts.append("   2. Monitor success rate and user feedback")
        report_parts.append("   3. Continue collecting interaction data")
        report_parts.append("   4. Review and apply generated insights")
        
        return "\n".join(report_parts)
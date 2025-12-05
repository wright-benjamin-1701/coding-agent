"""Knowledge transfer tool that leverages RAG context to apply past solutions."""

import json
from typing import Dict, Any, List, Optional, Tuple
from .base import Tool
from ..types import ToolResult
from ..database.rag_db import RAGDatabase


class KnowledgeTransferTool(Tool):
    """Tool that finds similar past sessions and extracts applicable solutions."""
    
    def __init__(self, rag_db: Optional[RAGDatabase] = None):
        self.rag_db = rag_db or RAGDatabase()
    
    @property
    def name(self) -> str:
        return "transfer_knowledge"
    
    @property
    def description(self) -> str:
        return "Find similar past sessions and extract applicable techniques, solutions, and lessons learned"
    
    @property
    def parameters_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "current_task": {
                    "type": "string",
                    "description": "Description of the current task or problem"
                },
                "task_type": {
                    "type": "string",
                    "enum": ["debugging", "feature_development", "refactoring", "testing", "optimization", "general"],
                    "description": "Type of task to focus the search",
                    "default": "general"
                },
                "max_suggestions": {
                    "type": "integer",
                    "description": "Maximum number of suggestions to return",
                    "default": 3,
                    "minimum": 1,
                    "maximum": 10
                },
                "include_execution_details": {
                    "type": "boolean",
                    "description": "Include detailed execution logs in recommendations",
                    "default": False
                }
            },
            "required": ["current_task"]
        }
    
    @property
    def is_destructive(self) -> bool:
        return False
    
    def execute(self, **parameters) -> ToolResult:
        """Find and extract knowledge from similar past sessions."""
        current_task = parameters.get("current_task")
        task_type = parameters.get("task_type", "general")
        max_suggestions = parameters.get("max_suggestions", 3)
        include_execution = parameters.get("include_execution_details", False)
        
        if not current_task:
            return ToolResult(
                success=False,
                output=None,
                error="current_task parameter is required"
            )
        
        try:
            # Search for similar sessions
            similar_sessions = self.rag_db.search_similar_prompts(
                current_task, 
                limit=max_suggestions * 2  # Get more to filter better
            )
            
            if not similar_sessions:
                return ToolResult(
                    success=True,
                    output="No similar past sessions found. This appears to be a novel task.",
                    action_description="Searched knowledge base for similar sessions"
                )
            
            # Analyze and extract knowledge
            knowledge_items = self._extract_knowledge(
                similar_sessions, 
                current_task, 
                task_type,
                include_execution
            )
            
            # Filter and rank suggestions
            top_suggestions = self._rank_suggestions(knowledge_items, max_suggestions)
            
            if not top_suggestions:
                return ToolResult(
                    success=True,
                    output="Found similar sessions but no applicable knowledge could be extracted.",
                    action_description="Analyzed similar sessions"
                )
            
            # Format output
            output = self._format_knowledge_transfer(top_suggestions, current_task)
            
            return ToolResult(
                success=True,
                output=output,
                action_description=f"Extracted {len(top_suggestions)} knowledge items from {len(similar_sessions)} similar sessions"
            )
            
        except Exception as e:
            return ToolResult(
                success=False,
                output=None,
                error=f"Knowledge transfer failed: {str(e)}"
            )
    
    def _extract_knowledge(self, sessions: List[Dict[str, Any]], current_task: str, 
                          task_type: str, include_execution: bool) -> List[Dict[str, Any]]:
        """Extract actionable knowledge from similar sessions."""
        knowledge_items = []
        
        for session in sessions:
            user_prompt = session.get('user_prompt', '')
            summary = session.get('summary', '')
            timestamp = session.get('timestamp', '')
            
            # Calculate relevance score
            relevance_score = self._calculate_relevance(user_prompt, current_task, task_type)
            
            if relevance_score < 0.1:  # Skip very low relevance
                continue
            
            # Extract key insights
            insights = self._extract_insights_from_summary(summary, task_type)
            
            # Get execution details if requested
            execution_details = None
            if include_execution:
                execution_details = self._get_execution_details(session)
            
            knowledge_item = {
                'relevance_score': relevance_score,
                'original_prompt': user_prompt,
                'summary': summary,
                'timestamp': timestamp,
                'insights': insights,
                'execution_details': execution_details,
                'task_similarity': self._assess_task_similarity(user_prompt, current_task)
            }
            
            knowledge_items.append(knowledge_item)
        
        return knowledge_items
    
    def _calculate_relevance(self, past_prompt: str, current_task: str, task_type: str) -> float:
        """Calculate relevance score between past prompt and current task."""
        past_words = set(past_prompt.lower().split())
        current_words = set(current_task.lower().split())
        
        # Basic word overlap
        overlap = len(past_words & current_words)
        union = len(past_words | current_words)
        jaccard_score = overlap / union if union > 0 else 0
        
        # Task type bonus
        task_type_bonus = 0.2 if task_type.lower() in past_prompt.lower() else 0
        
        # Technical term bonus (weight technical terms higher)
        technical_terms = {'class', 'function', 'method', 'variable', 'import', 'error', 'bug', 
                          'test', 'debug', 'refactor', 'optimize', 'api', 'database', 'file'}
        
        past_tech = past_words & technical_terms
        current_tech = current_words & technical_terms
        tech_overlap = len(past_tech & current_tech)
        tech_bonus = tech_overlap * 0.1
        
        return min(1.0, jaccard_score + task_type_bonus + tech_bonus)
    
    def _extract_insights_from_summary(self, summary: str, task_type: str) -> List[str]:
        """Extract actionable insights from session summary."""
        insights = []
        
        # Look for solution patterns
        solution_indicators = [
            'fixed by', 'solved by', 'resolved by', 'implemented by', 'added',
            'created', 'modified', 'updated', 'refactored', 'optimized'
        ]
        
        # Look for tool usage patterns
        tool_patterns = [
            'used search_files to', 'generated code with', 'wrote file',
            'ran tests', 'debugged by', 'analyzed with'
        ]
        
        # Look for lessons learned
        lesson_indicators = [
            'learned that', 'discovered', 'found that', 'important to',
            'should', 'must', 'avoid', 'remember to'
        ]
        
        sentences = summary.split('.')
        
        for sentence in sentences:
            sentence = sentence.strip().lower()
            
            # Extract solutions
            for indicator in solution_indicators:
                if indicator in sentence:
                    insights.append(f"Solution: {sentence.capitalize()}")
                    break
            
            # Extract tool usage
            for pattern in tool_patterns:
                if pattern in sentence:
                    insights.append(f"Technique: {sentence.capitalize()}")
                    break
            
            # Extract lessons
            for indicator in lesson_indicators:
                if indicator in sentence:
                    insights.append(f"Lesson: {sentence.capitalize()}")
                    break
        
        # Remove duplicates and filter short insights
        insights = list(set(insights))
        insights = [i for i in insights if len(i) > 20]
        
        return insights[:5]  # Limit to top 5 insights
    
    def _assess_task_similarity(self, past_prompt: str, current_task: str) -> str:
        """Assess similarity level between tasks."""
        relevance = self._calculate_relevance(past_prompt, current_task, "general")
        
        if relevance >= 0.7:
            return "Very similar"
        elif relevance >= 0.4:
            return "Moderately similar"
        elif relevance >= 0.2:
            return "Somewhat similar"
        else:
            return "Low similarity"
    
    def _get_execution_details(self, session: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Extract relevant execution details from session."""
        # This would be enhanced with actual execution log parsing
        # For now, return basic info
        return {
            'timestamp': session.get('timestamp'),
            'prompt': session.get('user_prompt', '')[:100] + '...',
            'summary': session.get('summary', '')[:200] + '...'
        }
    
    def _rank_suggestions(self, knowledge_items: List[Dict[str, Any]], max_suggestions: int) -> List[Dict[str, Any]]:
        """Rank and filter knowledge items by relevance and quality."""
        # Sort by relevance score descending
        ranked_items = sorted(knowledge_items, key=lambda x: x['relevance_score'], reverse=True)
        
        # Filter out low-quality items
        quality_threshold = 0.15
        filtered_items = [item for item in ranked_items if item['relevance_score'] >= quality_threshold]
        
        return filtered_items[:max_suggestions]
    
    def _format_knowledge_transfer(self, suggestions: List[Dict[str, Any]], current_task: str) -> str:
        """Format knowledge transfer suggestions for output."""
        output = f"📚 **Knowledge Transfer for: {current_task}**\n\n"
        output += f"Found {len(suggestions)} relevant suggestions from past sessions:\n\n"
        
        for i, suggestion in enumerate(suggestions, 1):
            output += f"## 🔍 Suggestion #{i} ({suggestion['task_similarity']})\n"
            output += f"**Relevance Score**: {suggestion['relevance_score']:.2f}\n"
            output += f"**Original Task**: {suggestion['original_prompt'][:100]}...\n\n"
            
            if suggestion['insights']:
                output += "**Key Insights**:\n"
                for insight in suggestion['insights']:
                    output += f"• {insight}\n"
                output += "\n"
            
            output += f"**Session Summary**: {suggestion['summary'][:200]}...\n"
            output += f"**Date**: {suggestion['timestamp']}\n"
            output += "---\n\n"
        
        output += "💡 **Recommendation**: Review these past approaches and adapt the successful techniques to your current task.\n"
        
        return output
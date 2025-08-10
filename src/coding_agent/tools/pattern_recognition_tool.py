"""Pattern recognition tool that identifies recurring patterns from session history."""

import json
import sqlite3
from collections import defaultdict, Counter
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Tuple
from .base import Tool
from ..types import ToolResult
from ..database.rag_db import RAGDatabase


class PatternRecognitionTool(Tool):
    """Tool that analyzes session history to identify patterns and suggest improvements."""
    
    def __init__(self, rag_db: Optional[RAGDatabase] = None):
        self.rag_db = rag_db or RAGDatabase()
    
    @property
    def name(self) -> str:
        return "analyze_patterns"
    
    @property
    def description(self) -> str:
        return "Analyze session history to identify recurring patterns, common issues, and successful solutions"
    
    @property
    def parameters_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "analysis_type": {
                    "type": "string",
                    "enum": ["all", "issues", "solutions", "files", "trends", "performance"],
                    "description": "Type of pattern analysis to perform",
                    "default": "all"
                },
                "time_window_days": {
                    "type": "integer",
                    "description": "Number of days to analyze (0 = all time)",
                    "default": 30,
                    "minimum": 0,
                    "maximum": 365
                },
                "min_frequency": {
                    "type": "integer", 
                    "description": "Minimum frequency for a pattern to be considered significant",
                    "default": 2,
                    "minimum": 1
                },
                "include_recommendations": {
                    "type": "boolean",
                    "description": "Include improvement recommendations based on patterns",
                    "default": True
                }
            },
            "required": []
        }
    
    @property
    def is_destructive(self) -> bool:
        return False
    
    def execute(self, **parameters) -> ToolResult:
        """Analyze patterns in session history."""
        analysis_type = parameters.get("analysis_type", "all")
        time_window = parameters.get("time_window_days", 30)
        min_frequency = parameters.get("min_frequency", 2)
        include_recommendations = parameters.get("include_recommendations", True)
        
        try:
            # Get session data
            sessions = self._get_sessions_data(time_window)
            
            if not sessions:
                return ToolResult(
                    success=True,
                    output="No session data found for pattern analysis.",
                    action_description="Analyzed session patterns"
                )
            
            # Perform different types of analysis
            analysis_results = {}
            
            if analysis_type in ["all", "issues"]:
                analysis_results["issues"] = self._analyze_recurring_issues(sessions, min_frequency)
            
            if analysis_type in ["all", "solutions"]:
                analysis_results["solutions"] = self._analyze_successful_solutions(sessions, min_frequency)
            
            if analysis_type in ["all", "files"]:
                analysis_results["files"] = self._analyze_file_patterns(sessions, min_frequency)
            
            if analysis_type in ["all", "trends"]:
                analysis_results["trends"] = self._analyze_trends(sessions)
            
            if analysis_type in ["all", "performance"]:
                analysis_results["performance"] = self._analyze_performance_patterns(sessions)
            
            # Generate recommendations if requested
            recommendations = []
            if include_recommendations:
                recommendations = self._generate_recommendations(analysis_results, sessions)
            
            # Format output
            output = self._format_analysis_results(
                analysis_results, 
                recommendations, 
                len(sessions), 
                time_window
            )
            
            return ToolResult(
                success=True,
                output=output,
                action_description=f"Analyzed patterns from {len(sessions)} sessions"
            )
            
        except Exception as e:
            return ToolResult(
                success=False,
                output=None,
                error=f"Pattern analysis failed: {str(e)}"
            )
    
    def _get_sessions_data(self, time_window_days: int) -> List[Dict[str, Any]]:
        """Get session data from the database."""
        with sqlite3.connect(self.rag_db.db_path) as conn:
            if time_window_days > 0:
                cutoff_date = (datetime.now() - timedelta(days=time_window_days)).isoformat()
                cursor = conn.execute("""
                    SELECT timestamp, user_prompt, summary, modified_files, execution_log
                    FROM sessions 
                    WHERE timestamp >= ?
                    ORDER BY timestamp DESC
                """, (cutoff_date,))
            else:
                cursor = conn.execute("""
                    SELECT timestamp, user_prompt, summary, modified_files, execution_log
                    FROM sessions 
                    ORDER BY timestamp DESC
                """)
            
            sessions = []
            for row in cursor.fetchall():
                try:
                    modified_files = json.loads(row[3]) if row[3] else []
                    execution_log = json.loads(row[4]) if row[4] else {}
                except json.JSONDecodeError:
                    modified_files = []
                    execution_log = {}
                
                sessions.append({
                    'timestamp': row[0],
                    'user_prompt': row[1],
                    'summary': row[2],
                    'modified_files': modified_files,
                    'execution_log': execution_log
                })
            
            return sessions
    
    def _analyze_recurring_issues(self, sessions: List[Dict[str, Any]], min_frequency: int) -> Dict[str, Any]:
        """Analyze recurring issues and problems."""
        issue_keywords = [
            'error', 'bug', 'failed', 'exception', 'problem', 'issue', 'broken',
            'not working', 'fix', 'debug', 'crash', 'fail'
        ]
        
        issue_patterns = defaultdict(list)
        error_types = Counter()
        
        for session in sessions:
            prompt = session['user_prompt'].lower()
            summary = session['summary'].lower()
            text_to_analyze = f"{prompt} {summary}"
            
            # Check for issue keywords
            found_issues = [kw for kw in issue_keywords if kw in text_to_analyze]
            
            if found_issues:
                issue_signature = self._extract_issue_signature(text_to_analyze)
                issue_patterns[issue_signature].append({
                    'timestamp': session['timestamp'],
                    'prompt': session['user_prompt'][:100] + '...',
                    'keywords': found_issues
                })
                
                # Count error types
                for keyword in found_issues:
                    error_types[keyword] += 1
        
        # Filter by minimum frequency
        frequent_issues = {
            sig: occurrences for sig, occurrences in issue_patterns.items()
            if len(occurrences) >= min_frequency
        }
        
        return {
            'frequent_issues': frequent_issues,
            'error_types': dict(error_types.most_common(10)),
            'total_issue_sessions': len([s for s in sessions if any(kw in s['user_prompt'].lower() + s['summary'].lower() for kw in issue_keywords)])
        }
    
    def _analyze_successful_solutions(self, sessions: List[Dict[str, Any]], min_frequency: int) -> Dict[str, Any]:
        """Analyze patterns in successful solutions."""
        success_keywords = [
            'fixed', 'solved', 'resolved', 'implemented', 'completed', 'working',
            'successful', 'added', 'created', 'improved', 'optimized'
        ]
        
        solution_patterns = defaultdict(list)
        tool_usage = Counter()
        
        for session in sessions:
            summary = session['summary'].lower()
            
            if any(kw in summary for kw in success_keywords):
                # Extract solution techniques
                solution_type = self._extract_solution_type(summary)
                solution_patterns[solution_type].append({
                    'timestamp': session['timestamp'],
                    'summary': session['summary'][:150] + '...',
                    'files_modified': len(session['modified_files'])
                })
                
                # Track tool usage patterns
                for tool_mention in ['search', 'write', 'read', 'test', 'debug']:
                    if tool_mention in summary:
                        tool_usage[tool_mention] += 1
        
        # Filter by frequency
        frequent_solutions = {
            sol: occurrences for sol, occurrences in solution_patterns.items()
            if len(occurrences) >= min_frequency
        }
        
        return {
            'frequent_solutions': frequent_solutions,
            'popular_tools': dict(tool_usage.most_common(10)),
            'success_rate': len([s for s in sessions if any(kw in s['summary'].lower() for kw in success_keywords)]) / len(sessions) if sessions else 0
        }
    
    def _analyze_file_patterns(self, sessions: List[Dict[str, Any]], min_frequency: int) -> Dict[str, Any]:
        """Analyze file modification patterns."""
        file_frequency = Counter()
        file_pairs = Counter()  # Files modified together
        extension_patterns = Counter()
        
        for session in sessions:
            files = session['modified_files']
            
            # Count individual file frequency
            for file_path in files:
                file_frequency[file_path] += 1
                
                # Track extensions
                if '.' in file_path:
                    ext = file_path.split('.')[-1].lower()
                    extension_patterns[ext] += 1
            
            # Count file pairs (files modified together)
            if len(files) > 1:
                for i, file1 in enumerate(files):
                    for file2 in files[i+1:]:
                        pair = tuple(sorted([file1, file2]))
                        file_pairs[pair] += 1
        
        # Filter by frequency
        frequent_files = {f: count for f, count in file_frequency.items() if count >= min_frequency}
        frequent_pairs = {pair: count for pair, count in file_pairs.items() if count >= min_frequency}
        
        return {
            'frequent_files': dict(file_frequency.most_common(15)),
            'frequent_pairs': dict(list(frequent_pairs.items())[:10]),
            'extension_patterns': dict(extension_patterns.most_common(10)),
            'avg_files_per_session': sum(len(s['modified_files']) for s in sessions) / len(sessions) if sessions else 0
        }
    
    def _analyze_trends(self, sessions: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Analyze trends over time."""
        if len(sessions) < 5:
            return {'message': 'Not enough data for trend analysis'}
        
        # Group sessions by week
        weekly_stats = defaultdict(lambda: {'sessions': 0, 'files_modified': 0, 'issues': 0, 'successes': 0})
        
        for session in sessions:
            try:
                date = datetime.fromisoformat(session['timestamp'])
                week_key = date.strftime('%Y-W%U')
                
                weekly_stats[week_key]['sessions'] += 1
                weekly_stats[week_key]['files_modified'] += len(session['modified_files'])
                
                summary_lower = session['summary'].lower()
                if any(word in summary_lower for word in ['error', 'bug', 'failed', 'problem']):
                    weekly_stats[week_key]['issues'] += 1
                if any(word in summary_lower for word in ['fixed', 'solved', 'completed', 'successful']):
                    weekly_stats[week_key]['successes'] += 1
                    
            except ValueError:
                continue  # Skip invalid timestamps
        
        # Calculate trends (last 4 weeks vs previous 4 weeks if enough data)
        weeks = sorted(weekly_stats.keys())
        if len(weeks) >= 8:
            recent_weeks = weeks[-4:]
            previous_weeks = weeks[-8:-4]
            
            recent_avg_sessions = sum(weekly_stats[w]['sessions'] for w in recent_weeks) / 4
            previous_avg_sessions = sum(weekly_stats[w]['sessions'] for w in previous_weeks) / 4
            
            trend = {
                'session_trend': 'increasing' if recent_avg_sessions > previous_avg_sessions else 'decreasing',
                'recent_avg_sessions': recent_avg_sessions,
                'previous_avg_sessions': previous_avg_sessions
            }
        else:
            trend = {'message': 'Not enough data for trend comparison'}
        
        return {
            'weekly_stats': dict(weekly_stats),
            'trend': trend,
            'total_weeks': len(weeks)
        }
    
    def _analyze_performance_patterns(self, sessions: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Analyze performance patterns."""
        session_lengths = []
        complexity_scores = []
        
        for session in sessions:
            # Estimate session complexity based on files modified and prompt length
            complexity = len(session['modified_files']) + len(session['user_prompt'].split()) / 10
            complexity_scores.append(complexity)
            
            # This would be enhanced with actual timing data from execution logs
            # For now, estimate based on summary length (longer summaries = more work done)
            estimated_duration = len(session['summary'].split()) / 5  # rough estimate
            session_lengths.append(estimated_duration)
        
        if not session_lengths:
            return {'message': 'No performance data available'}
        
        avg_duration = sum(session_lengths) / len(session_lengths)
        avg_complexity = sum(complexity_scores) / len(complexity_scores)
        
        # Find sessions that took unusually long
        long_sessions = [
            (i, sessions[i]['user_prompt'][:100] + '...')
            for i, duration in enumerate(session_lengths)
            if duration > avg_duration * 1.5
        ]
        
        return {
            'avg_estimated_duration': round(avg_duration, 2),
            'avg_complexity': round(avg_complexity, 2),
            'long_sessions': long_sessions[:5],  # Top 5 longest
            'performance_trend': 'stable'  # Would need time-series analysis for real trends
        }
    
    def _extract_issue_signature(self, text: str) -> str:
        """Extract a signature for grouping similar issues."""
        # Simple signature based on key technical terms
        tech_terms = []
        common_terms = ['file', 'function', 'class', 'method', 'variable', 'import', 'syntax', 
                       'runtime', 'type', 'attribute', 'module', 'package', 'library']
        
        words = text.split()
        for word in words:
            clean_word = word.strip('.,()[]{}:"\'')
            if clean_word in common_terms:
                tech_terms.append(clean_word)
        
        if tech_terms:
            return f"{tech_terms[0]}_issue"
        else:
            return "general_issue"
    
    def _extract_solution_type(self, summary: str) -> str:
        """Extract solution type from summary."""
        if 'added' in summary or 'created' in summary:
            return 'code_addition'
        elif 'fixed' in summary or 'resolved' in summary:
            return 'bug_fix'
        elif 'refactor' in summary or 'improved' in summary:
            return 'refactoring'
        elif 'test' in summary:
            return 'testing'
        elif 'optimize' in summary:
            return 'optimization'
        else:
            return 'general_solution'
    
    def _generate_recommendations(self, analysis: Dict[str, Any], sessions: List[Dict[str, Any]]) -> List[str]:
        """Generate improvement recommendations based on patterns."""
        recommendations = []
        
        # Issue-based recommendations
        if 'issues' in analysis:
            issues = analysis['issues']
            if issues.get('frequent_issues'):
                recommendations.append(
                    f"🔍 **Recurring Issues Detected**: You have {len(issues['frequent_issues'])} types of issues that appear repeatedly. "
                    f"Consider creating templates or automation for these common problems."
                )
            
            if issues.get('error_types'):
                top_error = max(issues['error_types'].items(), key=lambda x: x[1])
                recommendations.append(
                    f"⚠️ **Most Common Issue**: '{top_error[0]}' appears in {top_error[1]} sessions. "
                    f"Consider adding better error handling or documentation for this."
                )
        
        # Solution-based recommendations  
        if 'solutions' in analysis:
            solutions = analysis['solutions']
            if solutions.get('success_rate', 0) < 0.7:
                recommendations.append(
                    f"📈 **Success Rate**: Your success rate is {solutions['success_rate']:.1%}. "
                    f"Consider using the knowledge transfer tool more often to apply proven solutions."
                )
            
            if solutions.get('popular_tools'):
                top_tool = max(solutions['popular_tools'].items(), key=lambda x: x[1])
                recommendations.append(
                    f"🛠️ **Tool Usage**: '{top_tool[0]}' is your most used tool. "
                    f"Consider learning advanced features of this tool for better efficiency."
                )
        
        # File-based recommendations
        if 'files' in analysis:
            files = analysis['files']
            if files.get('avg_files_per_session', 0) > 5:
                recommendations.append(
                    f"📁 **File Scope**: You modify an average of {files['avg_files_per_session']:.1f} files per session. "
                    f"Consider breaking down complex tasks into smaller, focused sessions."
                )
            
            if files.get('frequent_pairs'):
                recommendations.append(
                    f"🔗 **File Dependencies**: Some files are frequently modified together. "
                    f"Consider refactoring to reduce coupling or create shared utilities."
                )
        
        return recommendations[:5]  # Limit to top 5 recommendations
    
    def _format_analysis_results(self, analysis: Dict[str, Any], recommendations: List[str], 
                                session_count: int, time_window: int) -> str:
        """Format analysis results for output."""
        output = f"🔍 **Pattern Analysis Report**\n\n"
        output += f"**Analysis Period**: {time_window if time_window > 0 else 'All time'} days\n"
        output += f"**Sessions Analyzed**: {session_count}\n\n"
        
        # Issues section
        if 'issues' in analysis:
            issues = analysis['issues']
            output += "## 🚨 Recurring Issues\n"
            
            if issues['frequent_issues']:
                output += f"Found **{len(issues['frequent_issues'])}** types of recurring issues:\n"
                for issue_type, occurrences in list(issues['frequent_issues'].items())[:3]:
                    output += f"• **{issue_type.replace('_', ' ').title()}**: {len(occurrences)} times\n"
            
            if issues['error_types']:
                top_errors = list(issues['error_types'].items())[:3]
                output += f"\n**Most Common Error Types**:\n"
                for error, count in top_errors:
                    output += f"• {error}: {count} sessions\n"
            
            output += "\n"
        
        # Solutions section
        if 'solutions' in analysis:
            solutions = analysis['solutions']
            output += "## ✅ Successful Solution Patterns\n"
            
            if solutions['frequent_solutions']:
                output += f"**Common Solution Types**:\n"
                for sol_type, occurrences in list(solutions['frequent_solutions'].items())[:3]:
                    output += f"• **{sol_type.replace('_', ' ').title()}**: {len(occurrences)} times\n"
            
            if solutions['popular_tools']:
                output += f"\n**Most Used Tools**: {', '.join(list(solutions['popular_tools'].keys())[:5])}\n"
            
            output += f"**Overall Success Rate**: {solutions['success_rate']:.1%}\n\n"
        
        # File patterns section
        if 'files' in analysis:
            files = analysis['files']
            output += "## 📁 File Modification Patterns\n"
            
            if files['frequent_files']:
                output += "**Most Modified Files**:\n"
                for file_path, count in list(files['frequent_files'].items())[:5]:
                    output += f"• {file_path}: {count} times\n"
            
            output += f"\n**Average Files Modified Per Session**: {files['avg_files_per_session']:.1f}\n"
            
            if files['extension_patterns']:
                top_exts = list(files['extension_patterns'].items())[:3]
                output += f"**Most Common File Types**: {', '.join([f'.{ext} ({count})' for ext, count in top_exts])}\n\n"
        
        # Trends section
        if 'trends' in analysis:
            trends = analysis['trends']
            if 'trend' in trends and 'message' not in trends['trend']:
                output += "## 📈 Activity Trends\n"
                trend = trends['trend']
                output += f"**Session Activity**: {trend['session_trend'].title()}\n"
                output += f"**Recent Average**: {trend['recent_avg_sessions']:.1f} sessions/week\n\n"
        
        # Recommendations section
        if recommendations:
            output += "## 💡 Recommendations\n\n"
            for i, rec in enumerate(recommendations, 1):
                output += f"{i}. {rec}\n\n"
        
        return output
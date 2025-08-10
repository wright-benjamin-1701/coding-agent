"""Code review assistant with automated pre-review and checklist generation."""

import ast
import re
import os
import json
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple, Set
from collections import defaultdict, Counter
from .base import Tool
from ..types import ToolResult
from ..providers.base import ModelProvider


class CodeReviewAnalyzer(ast.NodeVisitor):
    """Analyze code changes for review insights."""
    
    def __init__(self, file_path: str):
        self.file_path = file_path
        self.issues = []
        self.metrics = {
            'complexity': 0,
            'new_functions': 0,
            'modified_functions': 0,
            'test_coverage_needed': [],
            'security_concerns': [],
            'performance_implications': []
        }
    
    def analyze_changes(self, old_content: str, new_content: str) -> Dict[str, Any]:
        """Analyze changes between old and new content."""
        try:
            old_tree = ast.parse(old_content) if old_content else None
            new_tree = ast.parse(new_content)
            
            # Analyze new content
            self.visit(new_tree)
            
            # Compare with old if available
            if old_tree:
                self._compare_versions(old_tree, new_tree, old_content, new_content)
            else:
                # All content is new
                self._analyze_new_file(new_tree, new_content)
                
        except SyntaxError as e:
            self.issues.append({
                'type': 'syntax_error',
                'severity': 'critical',
                'line': e.lineno or 0,
                'message': f'Syntax error: {e.msg}',
                'suggestion': 'Fix syntax before review'
            })
        
        return {
            'issues': self.issues,
            'metrics': self.metrics,
            'review_focus_areas': self._identify_focus_areas()
        }
    
    def visit_FunctionDef(self, node):
        """Analyze function definitions."""
        self.metrics['new_functions'] += 1
        
        # Check complexity
        complexity = self._calculate_complexity(node)
        self.metrics['complexity'] += complexity
        
        if complexity > 10:
            self.issues.append({
                'type': 'high_complexity',
                'severity': 'medium',
                'line': node.lineno,
                'message': f'Function "{node.name}" has high complexity ({complexity})',
                'suggestion': 'Consider breaking into smaller functions'
            })
        
        # Check for missing tests indicator
        if not node.name.startswith('test_') and not node.name.startswith('_'):
            self.metrics['test_coverage_needed'].append(node.name)
        
        # Security patterns
        self._check_security_patterns(node)
        
        # Performance patterns
        self._check_performance_patterns(node)
        
        self.generic_visit(node)
    
    def _calculate_complexity(self, node) -> int:
        """Calculate cyclomatic complexity."""
        complexity = 1
        for child in ast.walk(node):
            if isinstance(child, (ast.If, ast.While, ast.For, ast.ExceptHandler)):
                complexity += 1
            elif isinstance(child, ast.BoolOp):
                complexity += len(child.values) - 1
        return complexity
    
    def _check_security_patterns(self, node):
        """Check for security concerns."""
        source = ast.unparse(node) if hasattr(ast, 'unparse') else ""
        
        # SQL injection patterns
        if re.search(r'execute\s*\(\s*["\'].*%.*["\']', source):
            self.issues.append({
                'type': 'security_sql_injection',
                'severity': 'high',
                'line': node.lineno,
                'message': 'Potential SQL injection vulnerability',
                'suggestion': 'Use parameterized queries'
            })
            self.metrics['security_concerns'].append('sql_injection')
        
        # Command injection patterns
        if re.search(r'(subprocess|os\.system|os\.popen).*\+', source):
            self.issues.append({
                'type': 'security_command_injection',
                'severity': 'high',
                'line': node.lineno,
                'message': 'Potential command injection vulnerability',
                'suggestion': 'Validate inputs and use subprocess with shell=False'
            })
            self.metrics['security_concerns'].append('command_injection')
    
    def _check_performance_patterns(self, node):
        """Check for performance implications."""
        source = ast.unparse(node) if hasattr(ast, 'unparse') else ""
        
        # Nested loops
        nested_loops = 0
        for child in ast.walk(node):
            if isinstance(child, (ast.For, ast.While)):
                for grandchild in ast.walk(child):
                    if isinstance(grandchild, (ast.For, ast.While)) and grandchild != child:
                        nested_loops += 1
                        break
        
        if nested_loops > 1:
            self.issues.append({
                'type': 'performance_nested_loops',
                'severity': 'medium',
                'line': node.lineno,
                'message': f'Function "{node.name}" has nested loops',
                'suggestion': 'Consider algorithmic optimization'
            })
            self.metrics['performance_implications'].append('nested_loops')
    
    def _compare_versions(self, old_tree, new_tree, old_content: str, new_content: str):
        """Compare old and new versions to identify changes."""
        # Extract function names from both versions
        old_functions = {node.name for node in ast.walk(old_tree) if isinstance(node, ast.FunctionDef)}
        new_functions = {node.name for node in ast.walk(new_tree) if isinstance(node, ast.FunctionDef)}
        
        # Identify changes
        added_functions = new_functions - old_functions
        removed_functions = old_functions - new_functions
        
        self.metrics['new_functions'] = len(added_functions)
        self.metrics['modified_functions'] = len(new_functions & old_functions)
        
        if added_functions:
            self.issues.append({
                'type': 'new_functions_added',
                'severity': 'info',
                'line': 0,
                'message': f'New functions added: {", ".join(added_functions)}',
                'suggestion': 'Ensure new functions have tests and documentation'
            })
        
        if removed_functions:
            self.issues.append({
                'type': 'functions_removed',
                'severity': 'medium',
                'line': 0,
                'message': f'Functions removed: {", ".join(removed_functions)}',
                'suggestion': 'Check for breaking changes and update documentation'
            })
    
    def _analyze_new_file(self, tree, content: str):
        """Analyze a completely new file."""
        self.issues.append({
            'type': 'new_file',
            'severity': 'info',
            'line': 0,
            'message': 'New file added to codebase',
            'suggestion': 'Review file structure, naming, and integration'
        })
    
    def _identify_focus_areas(self) -> List[str]:
        """Identify areas that need focused review attention."""
        focus_areas = []
        
        if self.metrics['security_concerns']:
            focus_areas.append('security')
        if self.metrics['performance_implications']:
            focus_areas.append('performance')
        if self.metrics['complexity'] > 20:
            focus_areas.append('complexity')
        if self.metrics['test_coverage_needed']:
            focus_areas.append('testing')
        if self.metrics['new_functions'] > 5:
            focus_areas.append('architecture')
        
        return focus_areas


class CodeReviewAssistant(Tool):
    """Automated code review assistant for pre-review analysis and checklist generation."""
    
    def __init__(self, model_provider: Optional[ModelProvider] = None):
        self.model_provider = model_provider
    
    @property
    def name(self) -> str:
        return "code_review_assistant"
    
    @property
    def description(self) -> str:
        return "Perform automated pre-review analysis of code changes with AI-powered insights and checklist generation"
    
    @property
    def parameters_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["review_changes", "review_file", "generate_checklist", "compare_versions"],
                    "description": "Type of review action to perform"
                },
                "target": {
                    "type": "string",
                    "description": "File path, commit hash, or branch to review"
                },
                "comparison_base": {
                    "type": "string",
                    "description": "Base commit/branch for comparison (default: HEAD~1)"
                },
                "file_path": {
                    "type": "string",
                    "description": "Specific file path to review"
                },
                "focus_areas": {
                    "type": "array",
                    "items": {
                        "type": "string",
                        "enum": ["security", "performance", "testing", "documentation", "architecture", "style"]
                    },
                    "description": "Specific areas to focus review on"
                },
                "severity_threshold": {
                    "type": "string",
                    "enum": ["all", "critical", "high", "medium", "low"],
                    "default": "medium",
                    "description": "Minimum severity level to report"
                },
                "include_ai_analysis": {
                    "type": "boolean",
                    "default": True,
                    "description": "Include AI-powered analysis and suggestions"
                },
                "generate_report": {
                    "type": "boolean",
                    "default": False,
                    "description": "Generate detailed review report"
                }
            },
            "required": ["action"]
        }
    
    @property
    def is_destructive(self) -> bool:
        return False
    
    def _get_git_changes(self, target: str = None, base: str = "HEAD~1") -> List[Dict[str, str]]:
        """Get git changes for review."""
        try:
            # Get list of changed files
            cmd = ["git", "diff", "--name-status", base, target or "HEAD"]
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            if result.returncode != 0:
                return []
            
            changes = []
            for line in result.stdout.strip().split('\n'):
                if not line:
                    continue
                
                parts = line.split('\t')
                if len(parts) >= 2:
                    status = parts[0]
                    file_path = parts[1]
                    
                    # Get file content changes
                    old_content = ""
                    new_content = ""
                    
                    if status != 'A':  # Not a new file
                        try:
                            old_result = subprocess.run(
                                ["git", "show", f"{base}:{file_path}"],
                                capture_output=True, text=True
                            )
                            if old_result.returncode == 0:
                                old_content = old_result.stdout
                        except:
                            pass
                    
                    if status != 'D':  # Not a deleted file
                        try:
                            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                                new_content = f.read()
                        except:
                            pass
                    
                    changes.append({
                        'status': status,
                        'file_path': file_path,
                        'old_content': old_content,
                        'new_content': new_content
                    })
            
            return changes
        
        except Exception:
            return []
    
    def _analyze_file_changes(self, file_path: str, old_content: str, new_content: str) -> Dict[str, Any]:
        """Analyze changes in a single file."""
        if not file_path.endswith('.py'):
            return {
                'issues': [],
                'metrics': {},
                'review_focus_areas': [],
                'message': 'Non-Python file - basic review only'
            }
        
        analyzer = CodeReviewAnalyzer(file_path)
        return analyzer.analyze_changes(old_content, new_content)
    
    def _generate_review_checklist(self, analysis_results: List[Dict[str, Any]], focus_areas: List[str] = None) -> List[Dict[str, Any]]:
        """Generate context-aware review checklist."""
        checklist = []
        
        # Always include basic checks
        checklist.extend([
            {
                'category': 'Code Quality',
                'item': 'Code follows project style guidelines',
                'priority': 'high'
            },
            {
                'category': 'Functionality',
                'item': 'Code does what it\'s supposed to do',
                'priority': 'high'
            },
            {
                'category': 'Testing',
                'item': 'Changes are covered by tests',
                'priority': 'high'
            }
        ])
        
        # Add focus-specific checks
        all_focus_areas = set()
        for result in analysis_results:
            all_focus_areas.update(result.get('review_focus_areas', []))
        
        if focus_areas:
            all_focus_areas.update(focus_areas)
        
        if 'security' in all_focus_areas:
            checklist.extend([
                {
                    'category': 'Security',
                    'item': 'No SQL injection vulnerabilities',
                    'priority': 'critical'
                },
                {
                    'category': 'Security',
                    'item': 'Input validation is proper',
                    'priority': 'high'
                },
                {
                    'category': 'Security',
                    'item': 'No hardcoded secrets or credentials',
                    'priority': 'critical'
                }
            ])
        
        if 'performance' in all_focus_areas:
            checklist.extend([
                {
                    'category': 'Performance',
                    'item': 'No obvious performance bottlenecks',
                    'priority': 'medium'
                },
                {
                    'category': 'Performance',
                    'item': 'Efficient algorithms and data structures used',
                    'priority': 'medium'
                }
            ])
        
        if 'testing' in all_focus_areas:
            checklist.extend([
                {
                    'category': 'Testing',
                    'item': 'Edge cases are tested',
                    'priority': 'medium'
                },
                {
                    'category': 'Testing',
                    'item': 'Error conditions are tested',
                    'priority': 'medium'
                }
            ])
        
        if 'documentation' in all_focus_areas:
            checklist.extend([
                {
                    'category': 'Documentation',
                    'item': 'Public functions have docstrings',
                    'priority': 'medium'
                },
                {
                    'category': 'Documentation',
                    'item': 'Complex logic is commented',
                    'priority': 'low'
                }
            ])
        
        if 'architecture' in all_focus_areas:
            checklist.extend([
                {
                    'category': 'Architecture',
                    'item': 'Changes fit well with existing architecture',
                    'priority': 'high'
                },
                {
                    'category': 'Architecture',
                    'item': 'No unnecessary dependencies introduced',
                    'priority': 'medium'
                }
            ])
        
        return checklist
    
    def _get_ai_insights(self, analysis_results: List[Dict[str, Any]], changes_summary: str) -> str:
        """Get AI-powered review insights."""
        if not self.model_provider:
            return "AI insights not available - no model provider configured"
        
        # Prepare summary of issues and changes
        all_issues = []
        for result in analysis_results:
            all_issues.extend(result.get('issues', []))
        
        high_priority_issues = [issue for issue in all_issues if issue.get('severity') in ['critical', 'high']]
        
        prompt = f"""
        Analyze this code review data and provide insights:

        Changes Summary:
        {changes_summary}

        High Priority Issues Found:
        {json.dumps(high_priority_issues, indent=2)}

        Please provide:
        1. Overall assessment of change risk level (low/medium/high)
        2. Key areas reviewers should focus on
        3. Potential impacts on system stability
        4. Recommendations for reviewer attention
        5. Any missed considerations

        Be concise and actionable.
        """
        
        try:
            response = self.model_provider.generate(prompt, max_tokens=800)
            return response.content if response else "AI analysis failed"
        except Exception as e:
            return f"AI analysis error: {str(e)}"
    
    def execute(self, **parameters) -> ToolResult:
        """Execute code review assistance."""
        try:
            action = parameters.get("action")
            target = parameters.get("target")
            comparison_base = parameters.get("comparison_base", "HEAD~1")
            file_path = parameters.get("file_path")
            focus_areas = parameters.get("focus_areas", [])
            severity_threshold = parameters.get("severity_threshold", "medium")
            include_ai_analysis = parameters.get("include_ai_analysis", True)
            generate_report = parameters.get("generate_report", False)
            
            analysis_results = []
            changes_summary = ""
            
            if action == "review_changes":
                # Review git changes
                changes = self._get_git_changes(target, comparison_base)
                if not changes:
                    return ToolResult(
                        success=True,
                        output="No changes found to review.",
                        action_description="Code review analysis"
                    )
                
                changes_summary = f"Reviewing {len(changes)} changed files"
                
                for change in changes:
                    result = self._analyze_file_changes(
                        change['file_path'],
                        change['old_content'],
                        change['new_content']
                    )
                    result['file_path'] = change['file_path']
                    result['change_status'] = change['status']
                    analysis_results.append(result)
            
            elif action == "review_file":
                if not file_path:
                    return ToolResult(
                        success=False,
                        error="file_path required for file review"
                    )
                
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        new_content = f.read()
                    
                    result = self._analyze_file_changes(file_path, "", new_content)
                    result['file_path'] = file_path
                    analysis_results.append(result)
                    changes_summary = f"Reviewing file: {file_path}"
                    
                except Exception as e:
                    return ToolResult(
                        success=False,
                        error=f"Could not read file {file_path}: {str(e)}"
                    )
            
            elif action == "generate_checklist":
                # Generate checklist without detailed analysis
                checklist = self._generate_review_checklist([], focus_areas)
                
                output_lines = ["📋 Code Review Checklist\n"]
                
                by_category = defaultdict(list)
                for item in checklist:
                    by_category[item['category']].append(item)
                
                for category, items in by_category.items():
                    output_lines.append(f"## {category}")
                    for item in items:
                        priority_emoji = {'critical': '🔴', 'high': '🟠', 'medium': '🟡', 'low': '🟢'}
                        emoji = priority_emoji.get(item['priority'], '⚪')
                        output_lines.append(f"   {emoji} {item['item']}")
                    output_lines.append("")
                
                return ToolResult(
                    success=True,
                    output="\n".join(output_lines),
                    action_description="Generated code review checklist"
                )
            
            # Filter issues by severity
            severity_levels = {'critical': 0, 'high': 1, 'medium': 2, 'low': 3, 'info': 4}
            threshold_level = severity_levels.get(severity_threshold, 2)
            
            all_issues = []
            for result in analysis_results:
                filtered_issues = [
                    issue for issue in result.get('issues', [])
                    if severity_levels.get(issue.get('severity', 'info'), 4) <= threshold_level
                ]
                result['issues'] = filtered_issues
                all_issues.extend(filtered_issues)
            
            # Generate output
            output_lines = ["🔍 Code Review Assistant Analysis\n"]
            
            # Summary
            total_files = len(analysis_results)
            total_issues = len(all_issues)
            critical_issues = len([i for i in all_issues if i.get('severity') == 'critical'])
            high_issues = len([i for i in all_issues if i.get('severity') == 'high'])
            
            output_lines.append(f"📊 **Summary:**")
            output_lines.append(f"   • Files analyzed: {total_files}")
            output_lines.append(f"   • Total issues: {total_issues}")
            if critical_issues:
                output_lines.append(f"   • 🔴 Critical issues: {critical_issues}")
            if high_issues:
                output_lines.append(f"   • 🟠 High priority issues: {high_issues}")
            
            # Issues by file
            if analysis_results:
                output_lines.append(f"\n📋 **Issues by File:**")
                
                for result in analysis_results:
                    if result.get('issues'):
                        file_path = result.get('file_path', 'unknown')
                        change_status = result.get('change_status', '')
                        status_text = f" ({change_status})" if change_status else ""
                        
                        output_lines.append(f"\n📁 **{file_path}{status_text}:**")
                        
                        for issue in result['issues'][:10]:  # Limit per file
                            severity_emoji = {'critical': '🔴', 'high': '🟠', 'medium': '🟡', 'low': '🟢', 'info': '🔵'}
                            emoji = severity_emoji.get(issue.get('severity', 'info'), '⚪')
                            
                            line_info = f"Line {issue['line']}: " if issue.get('line', 0) > 0 else ""
                            output_lines.append(f"   {emoji} {line_info}{issue['message']}")
                            if issue.get('suggestion'):
                                output_lines.append(f"      💡 {issue['suggestion']}")
            
            # Review checklist
            if analysis_results:
                checklist = self._generate_review_checklist(analysis_results, focus_areas)
                output_lines.append(f"\n📋 **Review Checklist:**")
                
                by_priority = defaultdict(list)
                for item in checklist:
                    by_priority[item['priority']].append(item)
                
                for priority in ['critical', 'high', 'medium', 'low']:
                    if priority in by_priority:
                        priority_emoji = {'critical': '🔴', 'high': '🟠', 'medium': '🟡', 'low': '🟢'}
                        emoji = priority_emoji[priority]
                        output_lines.append(f"\n**{priority.title()} Priority:**")
                        for item in by_priority[priority]:
                            output_lines.append(f"   {emoji} {item['item']} ({item['category']})")
            
            # AI insights
            if include_ai_analysis and self.model_provider and analysis_results:
                output_lines.append(f"\n🤖 **AI Review Insights:**")
                ai_insights = self._get_ai_insights(analysis_results, changes_summary)
                output_lines.append(ai_insights)
            
            # Recommendations
            output_lines.append(f"\n💡 **Next Steps:**")
            if critical_issues:
                output_lines.append("   1. 🔴 Address critical issues before merging")
            if high_issues:
                output_lines.append("   2. 🟠 Review high-priority issues carefully")
            output_lines.append("   3. ✅ Verify checklist items are satisfied")
            output_lines.append("   4. 🧪 Ensure adequate test coverage")
            
            return ToolResult(
                success=True,
                output="\n".join(output_lines),
                action_description=f"Code review analysis: {action}"
            )
        
        except Exception as e:
            return ToolResult(
                success=False,
                error=f"Code review analysis error: {str(e)}"
            )
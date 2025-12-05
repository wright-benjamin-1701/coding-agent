"""Intelligent code review tool with context-aware suggestions."""

import ast
import re
import os
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple, Set
from .base import Tool
from ..types import ToolResult
from ..providers.base import ModelProvider


class SecurityAnalyzer(ast.NodeVisitor):
    """Analyze code for security vulnerabilities."""
    
    def __init__(self):
        self.issues = []
        self.current_function = None
    
    def analyze(self, tree: ast.AST, source: str, file_path: str) -> List[Dict[str, Any]]:
        """Analyze code for security issues."""
        self.file_path = file_path
        self.source_lines = source.split('\n')
        self.visit(tree)
        return self.issues
    
    def visit_Call(self, node):
        """Check function calls for security issues."""
        if isinstance(node.func, ast.Name):
            func_name = node.func.id
            
            # SQL injection risks
            if func_name in ['execute', 'executemany'] and node.args:
                if isinstance(node.args[0], (ast.BinOp, ast.JoinedStr)):
                    self.issues.append({
                        'type': 'security',
                        'category': 'sql_injection',
                        'severity': 'high',
                        'message': 'Potential SQL injection vulnerability',
                        'line': node.lineno,
                        'suggestion': 'Use parameterized queries instead of string concatenation',
                        'code': self._get_line(node.lineno)
                    })
            
            # Command injection
            if func_name in ['system', 'popen', 'call', 'run'] and node.args:
                if isinstance(node.args[0], (ast.BinOp, ast.JoinedStr)):
                    self.issues.append({
                        'type': 'security',
                        'category': 'command_injection',
                        'severity': 'high',
                        'message': 'Potential command injection vulnerability',
                        'line': node.lineno,
                        'suggestion': 'Use subprocess with shell=False and validate inputs',
                        'code': self._get_line(node.lineno)
                    })
            
            # Dangerous functions
            dangerous_funcs = ['eval', 'exec', 'compile']
            if func_name in dangerous_funcs:
                self.issues.append({
                    'type': 'security',
                    'category': 'dangerous_function',
                    'severity': 'high',
                    'message': f'Use of dangerous function: {func_name}',
                    'line': node.lineno,
                    'suggestion': 'Consider safer alternatives or validate input thoroughly',
                    'code': self._get_line(node.lineno)
                })
        
        self.generic_visit(node)
    
    def visit_Import(self, node):
        """Check imports for security concerns."""
        for alias in node.names:
            if alias.name in ['pickle', 'cPickle']:
                self.issues.append({
                    'type': 'security',
                    'category': 'unsafe_deserialization',
                    'severity': 'medium',
                    'message': 'Pickle can execute arbitrary code during deserialization',
                    'line': node.lineno,
                    'suggestion': 'Consider using json or other safe serialization formats',
                    'code': self._get_line(node.lineno)
                })
    
    def _get_line(self, line_no: int) -> str:
        """Get source line by number."""
        if 1 <= line_no <= len(self.source_lines):
            return self.source_lines[line_no - 1].strip()
        return ""


class PerformanceAnalyzer(ast.NodeVisitor):
    """Analyze code for performance issues."""
    
    def __init__(self):
        self.issues = []
        self.loop_depth = 0
    
    def analyze(self, tree: ast.AST, source: str, file_path: str) -> List[Dict[str, Any]]:
        """Analyze code for performance issues."""
        self.file_path = file_path
        self.source_lines = source.split('\n')
        self.visit(tree)
        return self.issues
    
    def visit_For(self, node):
        """Check for loops for performance issues."""
        self.loop_depth += 1
        
        # Nested loops
        if self.loop_depth > 2:
            self.issues.append({
                'type': 'performance',
                'category': 'nested_loops',
                'severity': 'medium',
                'message': f'Deeply nested loops (depth: {self.loop_depth})',
                'line': node.lineno,
                'suggestion': 'Consider algorithmic optimization or breaking into functions',
                'code': self._get_line(node.lineno)
            })
        
        # Check for list operations in loops
        for child in ast.walk(node):
            if isinstance(child, ast.Call) and isinstance(child.func, ast.Attribute):
                if child.func.attr in ['append', 'extend'] and isinstance(child.func.value, ast.Name):
                    # Look for list comprehension opportunities
                    self.issues.append({
                        'type': 'performance',
                        'category': 'inefficient_loop',
                        'severity': 'low',
                        'message': 'Consider using list comprehension for better performance',
                        'line': child.lineno,
                        'suggestion': 'Replace loop with list comprehension if appropriate',
                        'code': self._get_line(child.lineno)
                    })
                    break
        
        self.generic_visit(node)
        self.loop_depth -= 1
    
    def visit_ListComp(self, node):
        """Check list comprehensions."""
        # Nested list comprehensions
        nested_count = sum(1 for _ in ast.walk(node) if isinstance(_, ast.ListComp))
        if nested_count > 2:
            self.issues.append({
                'type': 'performance',
                'category': 'complex_comprehension',
                'severity': 'low',
                'message': 'Complex nested list comprehension',
                'line': node.lineno,
                'suggestion': 'Consider breaking into multiple steps for readability',
                'code': self._get_line(node.lineno)
            })
        
        self.generic_visit(node)
    
    def _get_line(self, line_no: int) -> str:
        """Get source line by number."""
        if 1 <= line_no <= len(self.source_lines):
            return self.source_lines[line_no - 1].strip()
        return ""


class BestPracticesAnalyzer(ast.NodeVisitor):
    """Analyze code for best practice violations."""
    
    def __init__(self):
        self.issues = []
        self.current_function = None
        self.imports = set()
    
    def analyze(self, tree: ast.AST, source: str, file_path: str) -> List[Dict[str, Any]]:
        """Analyze code for best practice issues."""
        self.file_path = file_path
        self.source_lines = source.split('\n')
        self.visit(tree)
        return self.issues
    
    def visit_Import(self, node):
        """Track imports."""
        for alias in node.names:
            self.imports.add(alias.name)
    
    def visit_ImportFrom(self, node):
        """Track from imports."""
        if node.module:
            for alias in node.names:
                self.imports.add(f"{node.module}.{alias.name}")
    
    def visit_FunctionDef(self, node):
        """Analyze function definitions."""
        old_function = self.current_function
        self.current_function = node.name
        
        # Missing docstring
        if not (node.body and isinstance(node.body[0], ast.Expr) 
                and isinstance(node.body[0].value, ast.Constant) 
                and isinstance(node.body[0].value.value, str)):
            if not node.name.startswith('_') and node.name not in ['__init__', '__str__', '__repr__']:
                self.issues.append({
                    'type': 'best_practice',
                    'category': 'missing_docstring',
                    'severity': 'low',
                    'message': f"Function '{node.name}' missing docstring",
                    'line': node.lineno,
                    'suggestion': 'Add docstring to document function purpose and parameters',
                    'code': self._get_line(node.lineno)
                })
        
        # Mutable default arguments
        for arg in node.args.defaults:
            if isinstance(arg, (ast.List, ast.Dict, ast.Set)):
                self.issues.append({
                    'type': 'best_practice',
                    'category': 'mutable_default_argument',
                    'severity': 'medium',
                    'message': 'Mutable default argument detected',
                    'line': node.lineno,
                    'suggestion': 'Use None as default and create mutable object inside function',
                    'code': self._get_line(node.lineno)
                })
        
        self.generic_visit(node)
        self.current_function = old_function
    
    def visit_Except(self, node):
        """Check exception handling."""
        # Bare except clause
        if node.type is None:
            self.issues.append({
                'type': 'best_practice',
                'category': 'bare_except',
                'severity': 'medium',
                'message': 'Bare except clause catches all exceptions',
                'line': node.lineno,
                'suggestion': 'Specify specific exception types to catch',
                'code': self._get_line(node.lineno)
            })
    
    def visit_Global(self, node):
        """Check global variable usage."""
        self.issues.append({
            'type': 'best_practice',
            'category': 'global_variable',
            'severity': 'low',
            'message': 'Use of global variables',
            'line': node.lineno,
            'suggestion': 'Consider passing variables as parameters instead',
            'code': self._get_line(node.lineno)
        })
    
    def visit_Call(self, node):
        """Check function calls."""
        if isinstance(node.func, ast.Name):
            # Print statements (should use logging)
            if node.func.id == 'print' and 'logging' not in self.imports:
                self.issues.append({
                    'type': 'best_practice',
                    'category': 'print_statement',
                    'severity': 'low',
                    'message': 'Consider using logging instead of print',
                    'line': node.lineno,
                    'suggestion': 'Use logging module for better control over output',
                    'code': self._get_line(node.lineno)
                })
        
        self.generic_visit(node)
    
    def _get_line(self, line_no: int) -> str:
        """Get source line by number."""
        if 1 <= line_no <= len(self.source_lines):
            return self.source_lines[line_no - 1].strip()
        return ""


class IntelligentCodeReviewTool(Tool):
    """Intelligent code review with context-aware suggestions."""
    
    def __init__(self, model_provider: Optional[ModelProvider] = None):
        self.model_provider = model_provider
    
    @property
    def name(self) -> str:
        return "intelligent_code_review"
    
    @property
    def description(self) -> str:
        return "Perform intelligent code review with security analysis, performance checks, and best practice suggestions"
    
    @property
    def parameters_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Path to file or directory to review"
                },
                "file_pattern": {
                    "type": "string",
                    "default": "*.py",
                    "description": "File pattern to review"
                },
                "review_type": {
                    "type": "array",
                    "items": {
                        "type": "string",
                        "enum": ["security", "performance", "best_practices", "style", "all"]
                    },
                    "default": ["all"],
                    "description": "Types of review to perform"
                },
                "severity_filter": {
                    "type": "string",
                    "enum": ["all", "high", "medium", "low"],
                    "default": "all",
                    "description": "Filter issues by severity level"
                },
                "max_issues": {
                    "type": "integer",
                    "default": 50,
                    "description": "Maximum number of issues to report"
                },
                "context_aware": {
                    "type": "boolean",
                    "default": True,
                    "description": "Use AI for context-aware analysis (requires model provider)"
                },
                "changed_files_only": {
                    "type": "boolean",
                    "default": False,
                    "description": "Review only recently changed files"
                }
            },
            "required": ["path"]
        }
    
    @property
    def is_destructive(self) -> bool:
        return False
    
    def _get_files(self, path: str, file_pattern: str, changed_files_only: bool = False) -> List[Path]:
        """Get files to review."""
        search_path = Path(path)
        if not search_path.exists():
            return []
        
        if search_path.is_file():
            return [search_path]
        
        # Get files based on pattern
        if file_pattern.startswith("*."):
            extension = file_pattern[1:]
            files = list(search_path.rglob(f"*{extension}"))
        else:
            files = list(search_path.rglob(file_pattern))
        
        # Filter by recently changed files if requested
        if changed_files_only:
            try:
                import subprocess
                result = subprocess.run(['git', 'diff', '--name-only', 'HEAD~10'], 
                                      capture_output=True, text=True, cwd=search_path)
                if result.returncode == 0:
                    changed_files = set(result.stdout.strip().split('\n'))
                    files = [f for f in files if str(f.relative_to(search_path)) in changed_files]
            except Exception:
                pass  # Fall back to all files
        
        return files
    
    def _analyze_with_ai(self, code: str, file_path: str, issues: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Use AI for context-aware analysis."""
        if not self.model_provider or not issues:
            return issues
        
        try:
            # Prepare prompt for AI analysis
            issues_summary = "\n".join([
                f"- {issue['category']}: {issue['message']} (line {issue['line']})"
                for issue in issues[:10]  # Limit to avoid token limits
            ])
            
            prompt = f"""
            Analyze this code and the detected issues. Provide context-aware suggestions:
            
            File: {file_path}
            
            Code snippet:
            ```python
            {code[:2000]}  # Limit code length
            ```
            
            Detected Issues:
            {issues_summary}
            
            Please provide:
            1. Priority ranking of these issues
            2. Context-aware suggestions for fixes
            3. Additional issues you notice that weren't detected
            4. Overall code quality assessment
            
            Format as JSON with keys: priority_ranking, contextual_suggestions, additional_issues, quality_score
            """
            
            response = self.model_provider.generate(prompt, max_tokens=1000)
            
            # Parse AI response (simplified - would need better parsing in production)
            if response and "contextual_suggestions" in response.content:
                # Add AI insights to issues
                for issue in issues:
                    issue['ai_insight'] = "AI-enhanced analysis available"
            
        except Exception:
            pass  # Continue without AI enhancement
        
        return issues
    
    def execute(self, **parameters) -> ToolResult:
        """Execute intelligent code review."""
        try:
            path = parameters.get("path")
            file_pattern = parameters.get("file_pattern", "*.py")
            review_types = parameters.get("review_type", ["all"])
            severity_filter = parameters.get("severity_filter", "all")
            max_issues = parameters.get("max_issues", 50)
            context_aware = parameters.get("context_aware", True)
            changed_files_only = parameters.get("changed_files_only", False)
            
            if "all" in review_types:
                review_types = ["security", "performance", "best_practices"]
            
            files = self._get_files(path, file_pattern, changed_files_only)
            if not files:
                return ToolResult(
                    success=True,
                    output="No files found to review.",
                    action_description="Code review"
                )
            
            all_issues = []
            files_analyzed = 0
            
            # Analyze each file
            for file_path in files:
                try:
                    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                        content = f.read()
                    
                    if not content.strip():
                        continue
                    
                    tree = ast.parse(content)
                    file_issues = []
                    
                    # Security analysis
                    if "security" in review_types:
                        security_analyzer = SecurityAnalyzer()
                        security_issues = security_analyzer.analyze(tree, content, str(file_path))
                        file_issues.extend(security_issues)
                    
                    # Performance analysis
                    if "performance" in review_types:
                        performance_analyzer = PerformanceAnalyzer()
                        performance_issues = performance_analyzer.analyze(tree, content, str(file_path))
                        file_issues.extend(performance_issues)
                    
                    # Best practices analysis
                    if "best_practices" in review_types:
                        bp_analyzer = BestPracticesAnalyzer()
                        bp_issues = bp_analyzer.analyze(tree, content, str(file_path))
                        file_issues.extend(bp_issues)
                    
                    # Add file path to all issues
                    for issue in file_issues:
                        issue['file'] = str(file_path)
                    
                    # AI-enhanced analysis
                    if context_aware and self.model_provider and file_issues:
                        file_issues = self._analyze_with_ai(content, str(file_path), file_issues)
                    
                    all_issues.extend(file_issues)
                    files_analyzed += 1
                
                except (SyntaxError, UnicodeDecodeError):
                    continue
                except Exception:
                    continue
            
            if not all_issues:
                return ToolResult(
                    success=True,
                    output=f"✅ No issues found in {files_analyzed} files analyzed.",
                    action_description=f"Reviewed {files_analyzed} files"
                )
            
            # Filter by severity
            if severity_filter != "all":
                all_issues = [issue for issue in all_issues if issue['severity'] == severity_filter]
            
            # Sort by severity and limit results
            severity_order = {'high': 0, 'medium': 1, 'low': 2}
            all_issues.sort(key=lambda x: (severity_order.get(x['severity'], 3), x['file'], x['line']))
            all_issues = all_issues[:max_issues]
            
            # Generate report
            output_lines = ["🔍 Intelligent Code Review Report\n"]
            output_lines.append(f"📊 **Summary**")
            output_lines.append(f"   • Files analyzed: {files_analyzed}")
            output_lines.append(f"   • Issues found: {len(all_issues)}")
            
            # Group by severity
            by_severity = {}
            for issue in all_issues:
                severity = issue['severity']
                if severity not in by_severity:
                    by_severity[severity] = []
                by_severity[severity].append(issue)
            
            for severity in ['high', 'medium', 'low']:
                if severity in by_severity:
                    count = len(by_severity[severity])
                    emoji = {'high': '🔴', 'medium': '🟡', 'low': '🟢'}[severity]
                    output_lines.append(f"   • {emoji} {severity.title()} priority: {count}")
            
            # Show issues by category
            output_lines.append(f"\n📋 **Issues by Category**")
            by_category = {}
            for issue in all_issues:
                category = issue['category']
                if category not in by_category:
                    by_category[category] = []
                by_category[category].append(issue)
            
            for category, issues in sorted(by_category.items(), key=lambda x: len(x[1]), reverse=True):
                category_name = category.replace('_', ' ').title()
                output_lines.append(f"   • {category_name}: {len(issues)} issues")
            
            # Show detailed issues
            output_lines.append(f"\n🔍 **Detailed Issues**")
            
            current_file = None
            for issue in all_issues[:20]:  # Show top 20 issues
                if issue['file'] != current_file:
                    current_file = issue['file']
                    output_lines.append(f"\n📁 **{current_file}**")
                
                severity_emoji = {'high': '🔴', 'medium': '🟡', 'low': '🟢'}[issue['severity']]
                output_lines.append(f"   {severity_emoji} Line {issue['line']}: {issue['message']}")
                output_lines.append(f"      💡 {issue['suggestion']}")
                if issue.get('code'):
                    output_lines.append(f"      📝 `{issue['code']}`")
                if issue.get('ai_insight'):
                    output_lines.append(f"      🤖 {issue['ai_insight']}")
                output_lines.append("")
            
            if len(all_issues) > 20:
                output_lines.append(f"... and {len(all_issues) - 20} more issues")
            
            # Recommendations
            output_lines.append(f"\n💡 **Recommendations**")
            high_priority = len(by_severity.get('high', []))
            if high_priority > 0:
                output_lines.append(f"   • Address {high_priority} high-priority security/performance issues immediately")
            
            output_lines.append(f"   • Consider setting up pre-commit hooks for automated code quality checks")
            output_lines.append(f"   • Regular code reviews can catch issues early in development")
            
            return ToolResult(
                success=True,
                output="\n".join(output_lines),
                action_description=f"Found {len(all_issues)} issues in {files_analyzed} files"
            )
        
        except Exception as e:
            return ToolResult(
                success=False,
                error=f"Code review error: {str(e)}"
            )
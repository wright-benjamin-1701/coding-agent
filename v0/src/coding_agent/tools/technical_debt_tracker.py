"""Technical debt tracking and quantification tool."""

import ast
import re
import os
import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple, Set
from collections import defaultdict, Counter
from .base import Tool
from ..types import ToolResult


class TechnicalDebtAnalyzer(ast.NodeVisitor):
    """Analyze code for technical debt indicators."""
    
    def __init__(self):
        self.debt_items = []
        self.current_file = ""
        self.current_function = None
        self.current_class = None
    
    def analyze_file(self, file_path: str, content: str) -> List[Dict[str, Any]]:
        """Analyze a single file for technical debt."""
        self.current_file = file_path
        self.debt_items = []
        
        try:
            tree = ast.parse(content)
            self.visit(tree)
            
            # Add line-based analysis
            self._analyze_lines(content)
            
        except SyntaxError as e:
            self.debt_items.append({
                'type': 'syntax_error',
                'severity': 'critical',
                'description': f'Syntax error: {e.msg}',
                'file': file_path,
                'line': e.lineno or 0,
                'debt_score': 10,
                'effort_estimate': 'high'
            })
        
        return self.debt_items
    
    def visit_FunctionDef(self, node):
        """Analyze function definitions for debt."""
        old_function = self.current_function
        self.current_function = node.name
        
        # Long function debt
        if hasattr(node, 'end_lineno') and node.end_lineno:
            function_length = node.end_lineno - node.lineno
            if function_length > 50:
                self.debt_items.append({
                    'type': 'long_function',
                    'severity': 'medium',
                    'description': f'Function "{node.name}" is {function_length} lines long',
                    'file': self.current_file,
                    'line': node.lineno,
                    'debt_score': min(10, function_length // 10),
                    'effort_estimate': 'medium',
                    'suggestion': 'Break into smaller functions'
                })
        
        # Too many parameters debt
        param_count = len(node.args.args)
        if param_count > 7:
            self.debt_items.append({
                'type': 'too_many_parameters',
                'severity': 'medium',
                'description': f'Function "{node.name}" has {param_count} parameters',
                'file': self.current_file,
                'line': node.lineno,
                'debt_score': param_count - 5,
                'effort_estimate': 'medium',
                'suggestion': 'Use configuration objects or reduce parameters'
            })
        
        # Complex function (nested depth)
        max_depth = self._calculate_nesting_depth(node)
        if max_depth > 4:
            self.debt_items.append({
                'type': 'complex_nesting',
                'severity': 'medium',
                'description': f'Function "{node.name}" has nesting depth of {max_depth}',
                'file': self.current_file,
                'line': node.lineno,
                'debt_score': max_depth,
                'effort_estimate': 'high',
                'suggestion': 'Reduce nesting with early returns or extraction'
            })
        
        # Missing docstring
        if not self._has_docstring(node) and not node.name.startswith('_'):
            self.debt_items.append({
                'type': 'missing_docstring',
                'severity': 'low',
                'description': f'Function "{node.name}" lacks documentation',
                'file': self.current_file,
                'line': node.lineno,
                'debt_score': 1,
                'effort_estimate': 'low',
                'suggestion': 'Add docstring explaining purpose and parameters'
            })
        
        self.generic_visit(node)
        self.current_function = old_function
    
    def visit_ClassDef(self, node):
        """Analyze class definitions for debt."""
        old_class = self.current_class
        self.current_class = node.name
        
        # God class detection
        methods = [n for n in node.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]
        if len(methods) > 20:
            self.debt_items.append({
                'type': 'god_class',
                'severity': 'high',
                'description': f'Class "{node.name}" has {len(methods)} methods',
                'file': self.current_file,
                'line': node.lineno,
                'debt_score': len(methods) // 5,
                'effort_estimate': 'very_high',
                'suggestion': 'Break class into smaller, focused classes'
            })
        
        # Empty class
        if len(node.body) == 1 and isinstance(node.body[0], ast.Pass):
            self.debt_items.append({
                'type': 'empty_class',
                'severity': 'low',
                'description': f'Class "{node.name}" is empty',
                'file': self.current_file,
                'line': node.lineno,
                'debt_score': 1,
                'effort_estimate': 'low',
                'suggestion': 'Implement class or remove if unused'
            })
        
        self.generic_visit(node)
        self.current_class = old_class
    
    def visit_Try(self, node):
        """Analyze exception handling debt."""
        # Bare except clauses
        for handler in node.handlers:
            if handler.type is None:
                self.debt_items.append({
                    'type': 'bare_except',
                    'severity': 'medium',
                    'description': 'Bare except clause catches all exceptions',
                    'file': self.current_file,
                    'line': handler.lineno,
                    'debt_score': 3,
                    'effort_estimate': 'low',
                    'suggestion': 'Specify specific exception types'
                })
        
        self.generic_visit(node)
    
    def _analyze_lines(self, content: str):
        """Analyze content line by line for debt indicators."""
        lines = content.split('\n')
        
        for i, line in enumerate(lines, 1):
            line_stripped = line.strip().lower()
            
            # TODO/FIXME/HACK comments
            for keyword in ['todo', 'fixme', 'hack', 'bug', 'xxx']:
                if keyword in line_stripped and (line_stripped.startswith('#') or '//' in line):
                    priority = 'high' if keyword in ['fixme', 'bug'] else 'medium' if keyword == 'hack' else 'low'
                    severity = 'high' if keyword in ['bug', 'fixme'] else 'medium' if keyword == 'hack' else 'low'
                    
                    self.debt_items.append({
                        'type': f'{keyword}_comment',
                        'severity': severity,
                        'description': f'{keyword.upper()} comment: {line.strip()}',
                        'file': self.current_file,
                        'line': i,
                        'debt_score': 3 if priority == 'high' else 2 if priority == 'medium' else 1,
                        'effort_estimate': priority,
                        'suggestion': f'Address {keyword} item'
                    })
            
            # Magic numbers (excluding common ones)
            if re.search(r'\b(?!0|1|2|10|100|1000)\d{2,}\b', line) and not line_stripped.startswith('#'):
                self.debt_items.append({
                    'type': 'magic_number',
                    'severity': 'low',
                    'description': f'Magic number found: {line.strip()}',
                    'file': self.current_file,
                    'line': i,
                    'debt_score': 1,
                    'effort_estimate': 'low',
                    'suggestion': 'Replace with named constant'
                })
            
            # Long lines
            if len(line) > 120 and not line_stripped.startswith('#'):
                self.debt_items.append({
                    'type': 'long_line',
                    'severity': 'low',
                    'description': f'Line too long ({len(line)} chars)',
                    'file': self.current_file,
                    'line': i,
                    'debt_score': 1,
                    'effort_estimate': 'low',
                    'suggestion': 'Break line or simplify expression'
                })
    
    def _has_docstring(self, node) -> bool:
        """Check if node has docstring."""
        return (node.body and isinstance(node.body[0], ast.Expr) 
                and isinstance(node.body[0].value, ast.Constant)
                and isinstance(node.body[0].value.value, str))
    
    def _calculate_nesting_depth(self, node, depth=0) -> int:
        """Calculate maximum nesting depth in function."""
        max_depth = depth
        
        for child in ast.iter_child_nodes(node):
            if isinstance(child, (ast.If, ast.For, ast.While, ast.With, ast.Try)):
                child_depth = self._calculate_nesting_depth(child, depth + 1)
                max_depth = max(max_depth, child_depth)
        
        return max_depth


class TechnicalDebtTracker(Tool):
    """Track and quantify technical debt across the codebase."""
    
    def __init__(self):
        self.debt_history_file = ".technical_debt_history.json"
    
    @property
    def name(self) -> str:
        return "technical_debt_tracker"
    
    @property
    def description(self) -> str:
        return "Track, quantify, and prioritize technical debt across the codebase with historical trends"
    
    @property
    def parameters_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["analyze", "history", "prioritize", "summary", "export"],
                    "description": "Action to perform"
                },
                "path": {
                    "type": "string",
                    "default": ".",
                    "description": "Path to analyze"
                },
                "file_pattern": {
                    "type": "string",
                    "default": "*.py",
                    "description": "File pattern to analyze"
                },
                "severity_filter": {
                    "type": "string",
                    "enum": ["all", "critical", "high", "medium", "low"],
                    "default": "all",
                    "description": "Filter by severity level"
                },
                "debt_type": {
                    "type": "string",
                    "enum": ["all", "complexity", "documentation", "style", "architecture", "comments"],
                    "default": "all",
                    "description": "Filter by debt type"
                },
                "max_items": {
                    "type": "integer",
                    "default": 50,
                    "description": "Maximum items to report"
                },
                "save_history": {
                    "type": "boolean",
                    "default": True,
                    "description": "Save analysis to history"
                }
            },
            "required": ["action"]
        }
    
    @property
    def is_destructive(self) -> bool:
        return False
    
    def _get_files(self, path: str, file_pattern: str) -> List[Path]:
        """Get files to analyze."""
        search_path = Path(path)
        if not search_path.exists():
            return []
        
        if search_path.is_file():
            return [search_path]
        
        # Handle different file patterns
        if file_pattern.startswith("*."):
            extension = file_pattern[1:]
            return list(search_path.rglob(f"*{extension}"))
        
        return list(search_path.rglob(file_pattern))
    
    def _analyze_codebase(self, path: str, file_pattern: str) -> List[Dict[str, Any]]:
        """Analyze codebase for technical debt."""
        files = self._get_files(path, file_pattern)
        all_debt = []
        
        analyzer = TechnicalDebtAnalyzer()
        
        for file_path in files:
            # Skip common ignore patterns
            if any(ignore in str(file_path) for ignore in ['.git', '__pycache__', 'node_modules', '.env']):
                continue
            
            try:
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
                
                debt_items = analyzer.analyze_file(str(file_path), content)
                all_debt.extend(debt_items)
                
            except Exception as e:
                continue
        
        return all_debt
    
    def _calculate_debt_metrics(self, debt_items: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Calculate overall debt metrics."""
        if not debt_items:
            return {}
        
        total_score = sum(item['debt_score'] for item in debt_items)
        severity_counts = Counter(item['severity'] for item in debt_items)
        type_counts = Counter(item['type'] for item in debt_items)
        effort_counts = Counter(item['effort_estimate'] for item in debt_items)
        
        # Calculate debt density (debt per file)
        files = set(item['file'] for item in debt_items)
        debt_density = len(debt_items) / len(files) if files else 0
        
        return {
            'total_items': len(debt_items),
            'total_score': total_score,
            'average_score': total_score / len(debt_items),
            'debt_density': debt_density,
            'files_affected': len(files),
            'by_severity': dict(severity_counts),
            'by_type': dict(type_counts.most_common(10)),
            'by_effort': dict(effort_counts)
        }
    
    def _prioritize_debt(self, debt_items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Prioritize debt items by impact and effort."""
        severity_weights = {'critical': 10, 'high': 7, 'medium': 4, 'low': 1}
        effort_weights = {'low': 1, 'medium': 2, 'high': 3, 'very_high': 5}
        
        for item in debt_items:
            severity_weight = severity_weights.get(item['severity'], 1)
            effort_weight = effort_weights.get(item['effort_estimate'], 1)
            
            # Priority score = (severity * debt_score) / effort
            item['priority_score'] = (severity_weight * item['debt_score']) / effort_weight
        
        return sorted(debt_items, key=lambda x: x['priority_score'], reverse=True)
    
    def _save_to_history(self, analysis_data: Dict[str, Any]):
        """Save analysis to history file."""
        history_entry = {
            'timestamp': datetime.now().isoformat(),
            'metrics': analysis_data['metrics'],
            'top_items': analysis_data['debt_items'][:10]  # Save top 10 for trending
        }
        
        # Load existing history
        history = []
        if Path(self.debt_history_file).exists():
            try:
                with open(self.debt_history_file, 'r') as f:
                    history = json.load(f)
            except Exception:
                history = []
        
        history.append(history_entry)
        
        # Keep only last 30 entries
        history = history[-30:]
        
        with open(self.debt_history_file, 'w') as f:
            json.dump(history, f, indent=2)
    
    def _get_history_analysis(self) -> Dict[str, Any]:
        """Analyze debt history for trends."""
        if not Path(self.debt_history_file).exists():
            return {'message': 'No history data available'}
        
        try:
            with open(self.debt_history_file, 'r') as f:
                history = json.load(f)
        except Exception:
            return {'error': 'Could not load history'}
        
        if len(history) < 2:
            return {'message': 'Need at least 2 analyses for trend analysis'}
        
        # Compare latest vs previous
        latest = history[-1]
        previous = history[-2]
        
        latest_metrics = latest['metrics']
        previous_metrics = previous['metrics']
        
        trends = {}
        for metric in ['total_items', 'total_score', 'debt_density']:
            if metric in latest_metrics and metric in previous_metrics:
                current = latest_metrics[metric]
                prev = previous_metrics[metric]
                change = current - prev
                percent_change = (change / prev * 100) if prev != 0 else 0
                
                trends[metric] = {
                    'current': current,
                    'previous': prev,
                    'change': change,
                    'percent_change': percent_change,
                    'trend': 'improving' if change < 0 else 'worsening' if change > 0 else 'stable'
                }
        
        return {
            'total_analyses': len(history),
            'date_range': {
                'first': history[0]['timestamp'],
                'latest': history[-1]['timestamp']
            },
            'trends': trends
        }
    
    def execute(self, **parameters) -> ToolResult:
        """Execute technical debt tracking."""
        try:
            action = parameters.get("action")
            path = parameters.get("path", ".")
            file_pattern = parameters.get("file_pattern", "*.py")
            severity_filter = parameters.get("severity_filter", "all")
            debt_type = parameters.get("debt_type", "all")
            max_items = parameters.get("max_items", 50)
            save_history = parameters.get("save_history", True)
            
            if action == "history":
                history_data = self._get_history_analysis()
                return ToolResult(
                    success=True,
                    output=json.dumps(history_data, indent=2),
                    action_description="Retrieved technical debt history"
                )
            
            # Perform debt analysis
            debt_items = self._analyze_codebase(path, file_pattern)
            
            if not debt_items:
                return ToolResult(
                    success=True,
                    output="✅ No technical debt found! Codebase is clean.",
                    action_description="Technical debt analysis"
                )
            
            # Apply filters
            if severity_filter != "all":
                debt_items = [item for item in debt_items if item['severity'] == severity_filter]
            
            if debt_type != "all":
                type_mapping = {
                    'complexity': ['long_function', 'complex_nesting', 'god_class', 'too_many_parameters'],
                    'documentation': ['missing_docstring'],
                    'style': ['long_line', 'magic_number'],
                    'architecture': ['god_class', 'empty_class'],
                    'comments': ['todo_comment', 'fixme_comment', 'hack_comment', 'bug_comment']
                }
                if debt_type in type_mapping:
                    debt_items = [item for item in debt_items if item['type'] in type_mapping[debt_type]]
            
            # Calculate metrics
            metrics = self._calculate_debt_metrics(debt_items)
            
            # Prioritize if requested
            if action == "prioritize":
                debt_items = self._prioritize_debt(debt_items)
            
            # Limit results
            debt_items = debt_items[:max_items]
            
            # Save to history
            analysis_data = {
                'metrics': metrics,
                'debt_items': debt_items
            }
            
            if save_history and action in ["analyze", "prioritize"]:
                self._save_to_history(analysis_data)
            
            # Generate output based on action
            if action == "summary":
                output_lines = ["📊 Technical Debt Summary\n"]
                output_lines.append(f"**Overall Metrics:**")
                output_lines.append(f"   • Total Items: {metrics['total_items']}")
                output_lines.append(f"   • Total Debt Score: {metrics['total_score']}")
                output_lines.append(f"   • Average Score: {metrics['average_score']:.1f}")
                output_lines.append(f"   • Files Affected: {metrics['files_affected']}")
                output_lines.append(f"   • Debt Density: {metrics['debt_density']:.1f} items/file")
                
                output_lines.append(f"\n**By Severity:**")
                for severity, count in metrics['by_severity'].items():
                    output_lines.append(f"   • {severity.title()}: {count}")
                
                output_lines.append(f"\n**Top Debt Types:**")
                for debt_type, count in list(metrics['by_type'].items())[:5]:
                    output_lines.append(f"   • {debt_type.replace('_', ' ').title()}: {count}")
            
            elif action == "export":
                return ToolResult(
                    success=True,
                    output=json.dumps(analysis_data, indent=2),
                    action_description="Exported technical debt data"
                )
            
            else:  # analyze or prioritize
                output_lines = [f"🔍 Technical Debt Analysis ({action})\n"]
                
                # Summary
                output_lines.append(f"📊 **Summary:** {metrics['total_items']} items, Score: {metrics['total_score']}")
                
                # Top items
                output_lines.append(f"\n📋 **Top Issues:**")
                current_file = None
                for item in debt_items[:15]:
                    if item['file'] != current_file:
                        current_file = item['file']
                        output_lines.append(f"\n📁 **{current_file}:**")
                    
                    severity_emoji = {'critical': '🔴', 'high': '🟠', 'medium': '🟡', 'low': '🟢'}
                    emoji = severity_emoji.get(item['severity'], '⚪')
                    
                    output_lines.append(f"   {emoji} Line {item['line']}: {item['description']}")
                    output_lines.append(f"      💡 {item['suggestion']}")
                    if action == "prioritize":
                        output_lines.append(f"      🎯 Priority: {item['priority_score']:.1f}")
                    output_lines.append("")
                
                if len(debt_items) > 15:
                    output_lines.append(f"... and {len(debt_items) - 15} more items")
            
            return ToolResult(
                success=True,
                output="\n".join(output_lines),
                action_description=f"Technical debt {action}"
            )
        
        except Exception as e:
            return ToolResult(
                success=False,
                error=f"Technical debt analysis error: {str(e)}"
            )
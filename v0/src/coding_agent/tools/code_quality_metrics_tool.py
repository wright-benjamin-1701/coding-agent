"""Code quality metrics tool with complexity analysis and technical debt detection."""

import ast
import re
import os
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple, Set
from collections import defaultdict, Counter
from .base import Tool
from ..types import ToolResult


class ComplexityCalculator(ast.NodeVisitor):
    """Calculate various complexity metrics for Python code."""
    
    def __init__(self):
        self.cyclomatic_complexity = 1  # Base complexity
        self.cognitive_complexity = 0
        self.depth = 0
        self.max_depth = 0
        self.function_count = 0
        self.class_count = 0
        self.lines_of_code = 0
        self.comment_lines = 0
        self.blank_lines = 0
        
    def calculate_metrics(self, tree: ast.AST, source: str) -> Dict[str, Any]:
        """Calculate all metrics for the given AST and source."""
        self.source_lines = source.split('\n')
        self.lines_of_code = len([line for line in self.source_lines if line.strip()])
        self.comment_lines = len([line for line in self.source_lines if line.strip().startswith('#')])
        self.blank_lines = len([line for line in self.source_lines if not line.strip()])
        
        self.visit(tree)
        
        return {
            'cyclomatic_complexity': self.cyclomatic_complexity,
            'cognitive_complexity': self.cognitive_complexity,
            'max_nesting_depth': self.max_depth,
            'function_count': self.function_count,
            'class_count': self.class_count,
            'lines_of_code': self.lines_of_code,
            'comment_lines': self.comment_lines,
            'blank_lines': self.blank_lines,
            'total_lines': len(self.source_lines),
            'comment_ratio': self.comment_lines / max(1, self.lines_of_code),
        }
    
    def visit(self, node):
        """Override visit to track nesting depth."""
        if isinstance(node, (ast.If, ast.For, ast.While, ast.With, ast.Try, ast.FunctionDef, ast.ClassDef)):
            self.depth += 1
            self.max_depth = max(self.max_depth, self.depth)
        
        super().visit(node)
        
        if isinstance(node, (ast.If, ast.For, ast.While, ast.With, ast.Try, ast.FunctionDef, ast.ClassDef)):
            self.depth -= 1
    
    def visit_If(self, node):
        """Visit if statements."""
        self.cyclomatic_complexity += 1
        self.cognitive_complexity += 1 + self.depth  # Nesting increases cognitive load
        self.generic_visit(node)
    
    def visit_While(self, node):
        """Visit while loops."""
        self.cyclomatic_complexity += 1
        self.cognitive_complexity += 1 + self.depth
        self.generic_visit(node)
    
    def visit_For(self, node):
        """Visit for loops."""
        self.cyclomatic_complexity += 1
        self.cognitive_complexity += 1 + self.depth
        self.generic_visit(node)
    
    def visit_ExceptHandler(self, node):
        """Visit except handlers."""
        self.cyclomatic_complexity += 1
        self.cognitive_complexity += 1 + self.depth
        self.generic_visit(node)
    
    def visit_With(self, node):
        """Visit with statements."""
        self.cyclomatic_complexity += len(node.items)
        self.cognitive_complexity += 1 + self.depth
        self.generic_visit(node)
    
    def visit_FunctionDef(self, node):
        """Visit function definitions."""
        self.function_count += 1
        self.generic_visit(node)
    
    def visit_AsyncFunctionDef(self, node):
        """Visit async function definitions."""
        self.function_count += 1
        self.generic_visit(node)
    
    def visit_ClassDef(self, node):
        """Visit class definitions."""
        self.class_count += 1
        self.generic_visit(node)
    
    def visit_BoolOp(self, node):
        """Visit boolean operations (and/or)."""
        self.cyclomatic_complexity += len(node.values) - 1
        self.cognitive_complexity += len(node.values) - 1
        self.generic_visit(node)


class DuplicationDetector:
    """Detect code duplication."""
    
    def __init__(self, min_lines: int = 6):
        self.min_lines = min_lines
        self.line_hashes = defaultdict(list)
    
    def add_file(self, file_path: str, content: str):
        """Add file content for duplication analysis."""
        lines = [line.strip() for line in content.split('\n') if line.strip()]
        
        # Create sliding window of lines
        for i in range(len(lines) - self.min_lines + 1):
            window = '\n'.join(lines[i:i + self.min_lines])
            hash_val = hash(window)
            self.line_hashes[hash_val].append({
                'file': file_path,
                'start_line': i + 1,
                'content': window
            })
    
    def find_duplicates(self) -> List[Dict[str, Any]]:
        """Find duplicate code blocks."""
        duplicates = []
        
        for hash_val, locations in self.line_hashes.items():
            if len(locations) > 1:
                duplicates.append({
                    'locations': locations,
                    'duplicate_lines': self.min_lines,
                    'occurrences': len(locations)
                })
        
        return sorted(duplicates, key=lambda x: x['occurrences'], reverse=True)


class CodeSmellDetector(ast.NodeVisitor):
    """Detect common code smells."""
    
    def __init__(self):
        self.smells = []
        self.current_function = None
        self.current_class = None
    
    def detect_smells(self, tree: ast.AST, source: str, file_path: str) -> List[Dict[str, Any]]:
        """Detect code smells in the AST."""
        self.file_path = file_path
        self.source_lines = source.split('\n')
        self.visit(tree)
        return self.smells
    
    def visit_FunctionDef(self, node):
        """Visit function definitions to detect smells."""
        old_function = self.current_function
        self.current_function = node.name
        
        # Long function smell
        if hasattr(node, 'end_lineno') and node.end_lineno:
            function_length = node.end_lineno - node.lineno
            if function_length > 50:
                self.smells.append({
                    'type': 'long_function',
                    'severity': 'medium',
                    'message': f"Function '{node.name}' is {function_length} lines long",
                    'file': self.file_path,
                    'line': node.lineno,
                    'suggestion': "Consider breaking this function into smaller functions"
                })
        
        # Too many parameters
        param_count = len(node.args.args)
        if param_count > 7:
            self.smells.append({
                'type': 'too_many_parameters',
                'severity': 'medium',
                'message': f"Function '{node.name}' has {param_count} parameters",
                'file': self.file_path,
                'line': node.lineno,
                'suggestion': "Consider using a configuration object or breaking the function"
            })
        
        self.generic_visit(node)
        self.current_function = old_function
    
    def visit_ClassDef(self, node):
        """Visit class definitions to detect smells."""
        old_class = self.current_class
        self.current_class = node.name
        
        # Count methods and attributes
        methods = [n for n in node.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]
        
        # God class smell
        if len(methods) > 20:
            self.smells.append({
                'type': 'god_class',
                'severity': 'high',
                'message': f"Class '{node.name}' has {len(methods)} methods",
                'file': self.file_path,
                'line': node.lineno,
                'suggestion': "Consider breaking this class into smaller, more focused classes"
            })
        
        # Class with no methods (data class smell)
        if len(methods) == 0:
            self.smells.append({
                'type': 'data_class',
                'severity': 'low',
                'message': f"Class '{node.name}' has no methods",
                'file': self.file_path,
                'line': node.lineno,
                'suggestion': "Consider using a dataclass or namedtuple instead"
            })
        
        self.generic_visit(node)
        self.current_class = old_class
    
    def visit_If(self, node):
        """Visit if statements to detect complex conditions."""
        # Check for deeply nested conditions
        if self._count_nested_ifs(node) > 4:
            self.smells.append({
                'type': 'deeply_nested_conditionals',
                'severity': 'medium',
                'message': "Deeply nested if statements detected",
                'file': self.file_path,
                'line': node.lineno,
                'suggestion': "Consider using early returns or extracting methods"
            })
        
        self.generic_visit(node)
    
    def _count_nested_ifs(self, node, depth=0):
        """Count nested if statements recursively."""
        max_depth = depth
        for child in ast.iter_child_nodes(node):
            if isinstance(child, ast.If):
                child_depth = self._count_nested_ifs(child, depth + 1)
                max_depth = max(max_depth, child_depth)
        return max_depth


class CodeQualityMetricsTool(Tool):
    """Comprehensive code quality analysis tool."""
    
    @property
    def name(self) -> str:
        return "code_quality_metrics"
    
    @property
    def description(self) -> str:
        return "Analyze code quality with complexity metrics, duplication detection, and code smell identification"
    
    @property
    def parameters_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
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
                "metrics": {
                    "type": "array",
                    "items": {
                        "type": "string",
                        "enum": ["complexity", "duplication", "smells", "maintainability", "all"]
                    },
                    "default": ["all"],
                    "description": "Which metrics to calculate"
                },
                "min_duplication_lines": {
                    "type": "integer",
                    "default": 6,
                    "description": "Minimum lines for duplication detection"
                },
                "detailed": {
                    "type": "boolean",
                    "default": False,
                    "description": "Include detailed per-file breakdown"
                }
            }
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
    
    def _calculate_maintainability_index(self, metrics: Dict[str, Any]) -> float:
        """Calculate maintainability index (0-100, higher is better)."""
        # Simplified maintainability index calculation
        # Based on Halstead volume, cyclomatic complexity, and lines of code
        
        loc = max(1, metrics['lines_of_code'])
        cc = max(1, metrics['cyclomatic_complexity'])
        
        # Simple formula (actual MI is more complex)
        mi = max(0, (171 - 5.2 * (cc / 10) - 0.23 * (loc / 100) + 16.2 * (metrics['comment_ratio'] * 100)) * 100 / 171)
        return min(100, mi)
    
    def _get_quality_grade(self, score: float) -> str:
        """Get quality grade from score."""
        if score >= 85:
            return "A"
        elif score >= 70:
            return "B"
        elif score >= 55:
            return "C"
        elif score >= 40:
            return "D"
        else:
            return "F"
    
    def execute(self, **parameters) -> ToolResult:
        """Execute code quality analysis."""
        try:
            path = parameters.get("path", ".")
            file_pattern = parameters.get("file_pattern", "*.py")
            metrics_to_calculate = parameters.get("metrics", ["all"])
            min_duplication_lines = parameters.get("min_duplication_lines", 6)
            detailed = parameters.get("detailed", False)
            
            if "all" in metrics_to_calculate:
                metrics_to_calculate = ["complexity", "duplication", "smells", "maintainability"]
            
            files = self._get_files(path, file_pattern)
            if not files:
                return ToolResult(
                    success=True,
                    output="No files found to analyze.",
                    action_description="Code quality analysis"
                )
            
            # Initialize analyzers
            duplication_detector = DuplicationDetector(min_duplication_lines) if "duplication" in metrics_to_calculate else None
            
            # Aggregate metrics
            total_metrics = {
                'files_analyzed': 0,
                'total_lines': 0,
                'total_complexity': 0,
                'total_functions': 0,
                'total_classes': 0,
                'high_complexity_functions': 0,
                'smells': [],
                'file_details': []
            }
            
            output_lines = ["📊 Code Quality Analysis Report\n"]
            
            # Analyze each file
            for file_path in files:
                try:
                    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                        content = f.read()
                    
                    # Skip empty files
                    if not content.strip():
                        continue
                    
                    tree = ast.parse(content)
                    
                    # Calculate complexity metrics
                    if "complexity" in metrics_to_calculate or "maintainability" in metrics_to_calculate:
                        calculator = ComplexityCalculator()
                        file_metrics = calculator.calculate_metrics(tree, content)
                        
                        # Update totals
                        total_metrics['files_analyzed'] += 1
                        total_metrics['total_lines'] += file_metrics['total_lines']
                        total_metrics['total_complexity'] += file_metrics['cyclomatic_complexity']
                        total_metrics['total_functions'] += file_metrics['function_count']
                        total_metrics['total_classes'] += file_metrics['class_count']
                        
                        if file_metrics['cyclomatic_complexity'] > 20:
                            total_metrics['high_complexity_functions'] += 1
                        
                        if detailed:
                            maintainability = self._calculate_maintainability_index(file_metrics)
                            grade = self._get_quality_grade(maintainability)
                            
                            total_metrics['file_details'].append({
                                'file': str(file_path),
                                'metrics': file_metrics,
                                'maintainability': maintainability,
                                'grade': grade
                            })
                    
                    # Detect code smells
                    if "smells" in metrics_to_calculate:
                        smell_detector = CodeSmellDetector()
                        smells = smell_detector.detect_smells(tree, content, str(file_path))
                        total_metrics['smells'].extend(smells)
                    
                    # Add to duplication detector
                    if duplication_detector:
                        duplication_detector.add_file(str(file_path), content)
                
                except (SyntaxError, UnicodeDecodeError):
                    continue
                except Exception:
                    continue
            
            # Generate report
            if total_metrics['files_analyzed'] == 0:
                return ToolResult(
                    success=True,
                    output="No valid files found to analyze.",
                    action_description="Code quality analysis"
                )
            
            # Overall metrics
            avg_complexity = total_metrics['total_complexity'] / max(1, total_metrics['files_analyzed'])
            avg_maintainability = sum(f['maintainability'] for f in total_metrics['file_details']) / max(1, len(total_metrics['file_details'])) if total_metrics['file_details'] else 0
            
            output_lines.append(f"📋 **Summary**")
            output_lines.append(f"   • Files analyzed: {total_metrics['files_analyzed']}")
            output_lines.append(f"   • Total lines: {total_metrics['total_lines']:,}")
            output_lines.append(f"   • Functions: {total_metrics['total_functions']}")
            output_lines.append(f"   • Classes: {total_metrics['total_classes']}")
            
            if "complexity" in metrics_to_calculate:
                output_lines.append(f"\n🔄 **Complexity Analysis**")
                output_lines.append(f"   • Average cyclomatic complexity: {avg_complexity:.1f}")
                output_lines.append(f"   • High complexity files: {total_metrics['high_complexity_functions']}")
                complexity_grade = self._get_quality_grade(max(0, 100 - avg_complexity * 2))
                output_lines.append(f"   • Complexity grade: {complexity_grade}")
            
            if "maintainability" in metrics_to_calculate and total_metrics['file_details']:
                output_lines.append(f"\n🔧 **Maintainability**")
                output_lines.append(f"   • Average maintainability index: {avg_maintainability:.1f}")
                maintainability_grade = self._get_quality_grade(avg_maintainability)
                output_lines.append(f"   • Maintainability grade: {maintainability_grade}")
            
            # Code smells
            if "smells" in metrics_to_calculate and total_metrics['smells']:
                smell_counts = Counter(smell['type'] for smell in total_metrics['smells'])
                output_lines.append(f"\n🚨 **Code Smells ({len(total_metrics['smells'])} total)**")
                for smell_type, count in smell_counts.most_common():
                    output_lines.append(f"   • {smell_type.replace('_', ' ').title()}: {count}")
                
                # Show worst smells
                high_severity = [s for s in total_metrics['smells'] if s['severity'] == 'high']
                if high_severity:
                    output_lines.append(f"\n⚠️ **Critical Issues**")
                    for smell in high_severity[:5]:  # Show top 5
                        output_lines.append(f"   • {smell['message']}")
                        output_lines.append(f"     📁 {smell['file']}:{smell['line']}")
            
            # Duplication analysis
            if duplication_detector:
                duplicates = duplication_detector.find_duplicates()
                if duplicates:
                    total_duplicated_lines = sum(d['duplicate_lines'] * (d['occurrences'] - 1) for d in duplicates)
                    output_lines.append(f"\n📋 **Code Duplication**")
                    output_lines.append(f"   • Duplicate blocks: {len(duplicates)}")
                    output_lines.append(f"   • Duplicated lines: {total_duplicated_lines}")
                    
                    # Show worst duplications
                    for dup in duplicates[:3]:
                        output_lines.append(f"\n   🔄 {dup['duplicate_lines']} lines duplicated {dup['occurrences']} times:")
                        for loc in dup['locations'][:3]:  # Show first 3 locations
                            output_lines.append(f"      📁 {loc['file']}:{loc['start_line']}")
            
            # Detailed file breakdown
            if detailed and total_metrics['file_details']:
                output_lines.append(f"\n📄 **File Details**")
                sorted_files = sorted(total_metrics['file_details'], key=lambda x: x['maintainability'])
                
                for file_detail in sorted_files[:10]:  # Show worst 10 files
                    metrics = file_detail['metrics']
                    output_lines.append(f"\n   📁 {file_detail['file']}")
                    output_lines.append(f"      Grade: {file_detail['grade']} (MI: {file_detail['maintainability']:.1f})")
                    output_lines.append(f"      Complexity: {metrics['cyclomatic_complexity']}, LOC: {metrics['lines_of_code']}")
                    output_lines.append(f"      Functions: {metrics['function_count']}, Classes: {metrics['class_count']}")
            
            # Overall grade
            overall_score = (avg_maintainability + max(0, 100 - avg_complexity * 2)) / 2
            overall_grade = self._get_quality_grade(overall_score)
            output_lines.append(f"\n🎯 **Overall Quality Grade: {overall_grade}** (Score: {overall_score:.1f}/100)")
            
            return ToolResult(
                success=True,
                output="\n".join(output_lines),
                action_description=f"Analyzed {total_metrics['files_analyzed']} files"
            )
        
        except Exception as e:
            return ToolResult(
                success=False,
                error=f"Code quality analysis error: {str(e)}"
            )
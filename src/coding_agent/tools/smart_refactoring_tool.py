"""Smart refactoring tool with automated code improvement suggestions."""

import ast
import re
import os
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple, Set
from collections import defaultdict
from .base import Tool
from ..types import ToolResult


class RefactoringOpportunity:
    """Represents a refactoring opportunity."""
    
    def __init__(self, refactor_type: str, description: str, file_path: str, line_no: int, 
                 severity: str, before_code: str, after_code: str, reasoning: str):
        self.refactor_type = refactor_type
        self.description = description
        self.file_path = file_path
        self.line_no = line_no
        self.severity = severity  # high, medium, low
        self.before_code = before_code
        self.after_code = after_code
        self.reasoning = reasoning


class ExtractMethodAnalyzer(ast.NodeVisitor):
    """Analyze code for extract method opportunities."""
    
    def __init__(self):
        self.opportunities = []
        self.current_function = None
    
    def analyze(self, tree: ast.AST, source: str, file_path: str) -> List[RefactoringOpportunity]:
        """Find extract method opportunities."""
        self.file_path = file_path
        self.source_lines = source.split('\n')
        self.visit(tree)
        return self.opportunities
    
    def visit_FunctionDef(self, node):
        """Analyze function for extract method opportunities."""
        old_function = self.current_function
        self.current_function = node.name
        
        # Long function - suggest breaking it up
        if hasattr(node, 'end_lineno') and node.end_lineno:
            function_length = node.end_lineno - node.lineno
            if function_length > 30:
                # Find logical blocks that could be extracted
                blocks = self._find_extractable_blocks(node)
                for block in blocks:
                    self.opportunities.append(RefactoringOpportunity(
                        refactor_type="extract_method",
                        description=f"Extract method from long function '{node.name}' ({function_length} lines)",
                        file_path=self.file_path,
                        line_no=block['start_line'],
                        severity="medium",
                        before_code=self._get_code_block(block['start_line'], block['end_line']),
                        after_code=self._generate_extracted_method(block),
                        reasoning=f"Function is {function_length} lines long, extracting logical blocks improves readability"
                    ))
        
        # High complexity function
        complexity_calculator = ComplexityCounter()
        complexity_calculator.visit(node)
        if complexity_calculator.complexity > 10:
            self.opportunities.append(RefactoringOpportunity(
                refactor_type="extract_method",
                description=f"Extract methods from complex function '{node.name}' (complexity: {complexity_calculator.complexity})",
                file_path=self.file_path,
                line_no=node.lineno,
                severity="high",
                before_code=self._get_code_block(node.lineno, getattr(node, 'end_lineno', node.lineno + 10)),
                after_code="# Extract logical blocks into separate methods",
                reasoning=f"High cyclomatic complexity ({complexity_calculator.complexity}) makes function hard to understand"
            ))
        
        self.generic_visit(node)
        self.current_function = old_function
    
    def _find_extractable_blocks(self, node: ast.FunctionDef) -> List[Dict[str, Any]]:
        """Find blocks of code that could be extracted into methods."""
        blocks = []
        
        # Look for consecutive statements that form logical groups
        current_block = None
        for stmt in node.body:
            if isinstance(stmt, (ast.If, ast.For, ast.While, ast.Try)):
                if current_block and len(current_block['statements']) >= 3:
                    blocks.append(current_block)
                current_block = {
                    'start_line': stmt.lineno,
                    'end_line': getattr(stmt, 'end_lineno', stmt.lineno),
                    'statements': [stmt],
                    'type': type(stmt).__name__.lower()
                }
            elif current_block:
                current_block['statements'].append(stmt)
                current_block['end_line'] = getattr(stmt, 'end_lineno', stmt.lineno)
        
        if current_block and len(current_block['statements']) >= 3:
            blocks.append(current_block)
        
        return blocks
    
    def _get_code_block(self, start_line: int, end_line: int) -> str:
        """Get source code block."""
        if start_line <= 0 or end_line > len(self.source_lines):
            return ""
        return '\n'.join(self.source_lines[start_line-1:end_line])
    
    def _generate_extracted_method(self, block: Dict[str, Any]) -> str:
        """Generate code for extracted method."""
        method_name = f"_handle_{block['type']}_logic"
        return f"""def {method_name}(self):
    \"\"\"Handle {block['type']} logic.\"\"\"
    # Extract the following {len(block['statements'])} statements:
    # Lines {block['start_line']}-{block['end_line']}
    pass

# Then call: self.{method_name}()"""


class ComplexityCounter(ast.NodeVisitor):
    """Count cyclomatic complexity of a function."""
    
    def __init__(self):
        self.complexity = 1
    
    def visit_If(self, node):
        self.complexity += 1
        self.generic_visit(node)
    
    def visit_While(self, node):
        self.complexity += 1
        self.generic_visit(node)
    
    def visit_For(self, node):
        self.complexity += 1
        self.generic_visit(node)


class ExtractClassAnalyzer(ast.NodeVisitor):
    """Analyze code for extract class opportunities."""
    
    def __init__(self):
        self.opportunities = []
    
    def analyze(self, tree: ast.AST, source: str, file_path: str) -> List[RefactoringOpportunity]:
        """Find extract class opportunities."""
        self.file_path = file_path
        self.source_lines = source.split('\n')
        self.visit(tree)
        return self.opportunities
    
    def visit_ClassDef(self, node):
        """Analyze class for extract class opportunities."""
        methods = [n for n in node.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]
        
        # Large class with many methods
        if len(methods) > 15:
            # Analyze method groups by naming patterns
            method_groups = self._group_methods_by_prefix(methods)
            
            for prefix, group_methods in method_groups.items():
                if len(group_methods) >= 3:
                    self.opportunities.append(RefactoringOpportunity(
                        refactor_type="extract_class",
                        description=f"Extract '{prefix}' methods from class '{node.name}' into separate class",
                        file_path=self.file_path,
                        line_no=node.lineno,
                        severity="medium",
                        before_code=f"# Class {node.name} with {len(methods)} methods",
                        after_code=f"# Extract {len(group_methods)} '{prefix}' methods into {prefix.title()}Handler class",
                        reasoning=f"Class has {len(methods)} methods, extracting {prefix} methods would improve organization"
                    ))
        
        self.generic_visit(node)
    
    def _group_methods_by_prefix(self, methods: List[ast.FunctionDef]) -> Dict[str, List[ast.FunctionDef]]:
        """Group methods by common prefixes."""
        groups = defaultdict(list)
        
        for method in methods:
            if method.name.startswith('_'):
                continue  # Skip private methods
            
            # Find common prefixes
            parts = method.name.split('_')
            if len(parts) > 1:
                prefix = parts[0]
                groups[prefix].append(method)
            
            # Also check for common suffixes
            if method.name.endswith(('_handler', '_processor', '_validator', '_converter')):
                suffix = method.name.split('_')[-1]
                groups[suffix].append(method)
        
        return {k: v for k, v in groups.items() if len(v) >= 2}


class DuplicationRefactorAnalyzer:
    """Analyze code duplication for refactoring opportunities."""
    
    def __init__(self, min_lines: int = 4):
        self.min_lines = min_lines
        self.duplications = []
    
    def analyze(self, files_content: Dict[str, str]) -> List[RefactoringOpportunity]:
        """Find code duplication refactoring opportunities."""
        opportunities = []
        
        # Simple line-based duplication detection
        line_groups = defaultdict(list)
        
        for file_path, content in files_content.items():
            lines = [line.strip() for line in content.split('\n') if line.strip()]
            
            # Create sliding windows
            for i in range(len(lines) - self.min_lines + 1):
                window = tuple(lines[i:i + self.min_lines])
                if window and not any(line.startswith('#') or line.startswith('"""') for line in window):
                    line_groups[window].append({
                        'file': file_path,
                        'start_line': i + 1,
                        'lines': window
                    })
        
        # Find duplications
        for window, locations in line_groups.items():
            if len(locations) > 1:
                opportunities.append(RefactoringOpportunity(
                    refactor_type="extract_common_code",
                    description=f"Extract duplicated code block ({self.min_lines} lines) into shared function",
                    file_path=locations[0]['file'],
                    line_no=locations[0]['start_line'],
                    severity="medium",
                    before_code='\n'.join(window),
                    after_code=f"# Extract to shared function:\ndef _extracted_logic():\n    {'    '.join(window)}",
                    reasoning=f"Code block appears in {len(locations)} locations: {', '.join(loc['file'] for loc in locations)}"
                ))
        
        return opportunities


class DesignPatternAnalyzer(ast.NodeVisitor):
    """Analyze code for design pattern application opportunities."""
    
    def __init__(self):
        self.opportunities = []
        self.classes = []
    
    def analyze(self, tree: ast.AST, source: str, file_path: str) -> List[RefactoringOpportunity]:
        """Find design pattern opportunities."""
        self.file_path = file_path
        self.source_lines = source.split('\n')
        self.visit(tree)
        return self.opportunities
    
    def visit_ClassDef(self, node):
        """Analyze classes for design pattern opportunities."""
        self.classes.append(node)
        
        # Analyze for Strategy pattern opportunity
        methods = [n for n in node.body if isinstance(n, ast.FunctionDef)]
        
        # Look for long if-elif chains in methods (Strategy pattern candidate)
        for method in methods:
            if_chain_length = self._count_if_elif_chain(method)
            if if_chain_length > 3:
                self.opportunities.append(RefactoringOpportunity(
                    refactor_type="apply_strategy_pattern",
                    description=f"Replace long if-elif chain in {node.name}.{method.name} with Strategy pattern",
                    file_path=self.file_path,
                    line_no=method.lineno,
                    severity="medium",
                    before_code=f"# Long if-elif chain ({if_chain_length} conditions)",
                    after_code="# Create strategy classes for each condition",
                    reasoning="Long conditional chains are hard to maintain and extend"
                ))
        
        # Look for Factory pattern opportunities (multiple constructors)
        init_methods = [m for m in methods if m.name == '__init__']
        if init_methods and len(init_methods[0].args.args) > 5:
            self.opportunities.append(RefactoringOpportunity(
                refactor_type="apply_factory_pattern",
                description=f"Use Factory pattern for complex {node.name} construction",
                file_path=self.file_path,
                line_no=node.lineno,
                severity="low",
                before_code=f"# Complex constructor with {len(init_methods[0].args.args)} parameters",
                after_code=f"# Create {node.name}Factory with builder methods",
                reasoning="Complex constructors benefit from factory patterns for clarity"
            ))
        
        self.generic_visit(node)
    
    def _count_if_elif_chain(self, method: ast.FunctionDef) -> int:
        """Count the length of if-elif chains."""
        max_chain = 0
        
        for node in ast.walk(method):
            if isinstance(node, ast.If):
                chain_length = 1
                current = node
                
                while hasattr(current, 'orelse') and len(current.orelse) == 1 and isinstance(current.orelse[0], ast.If):
                    chain_length += 1
                    current = current.orelse[0]
                
                max_chain = max(max_chain, chain_length)
        
        return max_chain


class SmartRefactoringTool(Tool):
    """Smart refactoring tool with automated improvement suggestions."""
    
    @property
    def name(self) -> str:
        return "smart_refactoring"
    
    @property
    def description(self) -> str:
        return "Analyze code for refactoring opportunities including extract method, extract class, design patterns, and code duplication removal"
    
    @property
    def parameters_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Path to analyze for refactoring opportunities"
                },
                "file_pattern": {
                    "type": "string",
                    "default": "*.py",
                    "description": "File pattern to analyze"
                },
                "refactor_types": {
                    "type": "array",
                    "items": {
                        "type": "string",
                        "enum": ["extract_method", "extract_class", "design_patterns", "duplication", "all"]
                    },
                    "default": ["all"],
                    "description": "Types of refactoring to analyze"
                },
                "severity_filter": {
                    "type": "string",
                    "enum": ["all", "high", "medium", "low"],
                    "default": "all",
                    "description": "Filter suggestions by severity"
                },
                "max_suggestions": {
                    "type": "integer",
                    "default": 20,
                    "description": "Maximum number of suggestions to return"
                },
                "apply_refactoring": {
                    "type": "boolean",
                    "default": False,
                    "description": "Actually apply the refactoring (DESTRUCTIVE)"
                },
                "suggestion_id": {
                    "type": "string",
                    "description": "ID of specific suggestion to apply"
                }
            },
            "required": ["path"]
        }
    
    @property
    def is_destructive(self) -> bool:
        return True  # Can apply refactorings
    
    def _get_files(self, path: str, file_pattern: str) -> List[Path]:
        """Get files to analyze."""
        search_path = Path(path)
        if not search_path.exists():
            return []
        
        if search_path.is_file():
            return [search_path]
        
        if file_pattern.startswith("*."):
            extension = file_pattern[1:]
            return list(search_path.rglob(f"*{extension}"))
        
        return list(search_path.rglob(file_pattern))
    
    def execute(self, **parameters) -> ToolResult:
        """Execute smart refactoring analysis."""
        try:
            path = parameters.get("path")
            file_pattern = parameters.get("file_pattern", "*.py")
            refactor_types = parameters.get("refactor_types", ["all"])
            severity_filter = parameters.get("severity_filter", "all")
            max_suggestions = parameters.get("max_suggestions", 20)
            apply_refactoring = parameters.get("apply_refactoring", False)
            suggestion_id = parameters.get("suggestion_id")
            
            if "all" in refactor_types:
                refactor_types = ["extract_method", "extract_class", "design_patterns", "duplication"]
            
            files = self._get_files(path, file_pattern)
            if not files:
                return ToolResult(
                    success=True,
                    output="No files found to analyze.",
                    action_description="Refactoring analysis"
                )
            
            all_opportunities = []
            files_content = {}
            
            # Analyze each file
            for file_path in files:
                try:
                    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                        content = f.read()
                    
                    if not content.strip():
                        continue
                    
                    files_content[str(file_path)] = content
                    tree = ast.parse(content)
                    
                    # Extract method analysis
                    if "extract_method" in refactor_types:
                        extract_analyzer = ExtractMethodAnalyzer()
                        opportunities = extract_analyzer.analyze(tree, content, str(file_path))
                        all_opportunities.extend(opportunities)
                    
                    # Extract class analysis
                    if "extract_class" in refactor_types:
                        class_analyzer = ExtractClassAnalyzer()
                        opportunities = class_analyzer.analyze(tree, content, str(file_path))
                        all_opportunities.extend(opportunities)
                    
                    # Design pattern analysis
                    if "design_patterns" in refactor_types:
                        pattern_analyzer = DesignPatternAnalyzer()
                        opportunities = pattern_analyzer.analyze(tree, content, str(file_path))
                        all_opportunities.extend(opportunities)
                
                except (SyntaxError, UnicodeDecodeError):
                    continue
                except Exception:
                    continue
            
            # Duplication analysis (cross-file)
            if "duplication" in refactor_types and files_content:
                dup_analyzer = DuplicationRefactorAnalyzer()
                dup_opportunities = dup_analyzer.analyze(files_content)
                all_opportunities.extend(dup_opportunities)
            
            if not all_opportunities:
                return ToolResult(
                    success=True,
                    output="✅ No refactoring opportunities found. Code looks well-structured!",
                    action_description=f"Analyzed {len(files)} files"
                )
            
            # Filter by severity
            if severity_filter != "all":
                all_opportunities = [opp for opp in all_opportunities if opp.severity == severity_filter]
            
            # Sort by severity and limit
            severity_order = {'high': 0, 'medium': 1, 'low': 2}
            all_opportunities.sort(key=lambda x: (severity_order.get(x.severity, 3), x.file_path, x.line_no))
            all_opportunities = all_opportunities[:max_suggestions]
            
            # If applying specific refactoring
            if apply_refactoring and suggestion_id:
                # This would implement actual refactoring application
                return ToolResult(
                    success=True,
                    output=f"⚠️ Refactoring application not fully implemented yet. Would apply suggestion {suggestion_id}",
                    action_description="Apply refactoring"
                )
            
            # Generate report
            output_lines = ["🔧 Smart Refactoring Analysis Report\n"]
            
            # Summary
            output_lines.append("📊 **Summary**")
            output_lines.append(f"   • Files analyzed: {len(files)}")
            output_lines.append(f"   • Refactoring opportunities: {len(all_opportunities)}")
            
            # By severity
            by_severity = {}
            for opp in all_opportunities:
                if opp.severity not in by_severity:
                    by_severity[opp.severity] = []
                by_severity[opp.severity].append(opp)
            
            for severity in ['high', 'medium', 'low']:
                if severity in by_severity:
                    count = len(by_severity[severity])
                    emoji = {'high': '🔴', 'medium': '🟡', 'low': '🟢'}[severity]
                    output_lines.append(f"   • {emoji} {severity.title()} priority: {count}")
            
            # By type
            by_type = {}
            for opp in all_opportunities:
                if opp.refactor_type not in by_type:
                    by_type[opp.refactor_type] = []
                by_type[opp.refactor_type].append(opp)
            
            output_lines.append(f"\n📋 **By Refactoring Type**")
            for refactor_type, opportunities in sorted(by_type.items(), key=lambda x: len(x[1]), reverse=True):
                type_name = refactor_type.replace('_', ' ').title()
                output_lines.append(f"   • {type_name}: {len(opportunities)}")
            
            # Detailed suggestions
            output_lines.append(f"\n🔧 **Refactoring Suggestions**")
            
            current_file = None
            for i, opp in enumerate(all_opportunities[:15]):  # Show top 15
                if opp.file_path != current_file:
                    current_file = opp.file_path
                    output_lines.append(f"\n📁 **{current_file}**")
                
                severity_emoji = {'high': '🔴', 'medium': '🟡', 'low': '🟢'}[opp.severity]
                suggestion_id = f"REF{i+1:03d}"
                
                output_lines.append(f"   {severity_emoji} **{suggestion_id}**: {opp.description}")
                output_lines.append(f"      📍 Line {opp.line_no}")
                output_lines.append(f"      🔍 Type: {opp.refactor_type.replace('_', ' ').title()}")
                output_lines.append(f"      💭 Reasoning: {opp.reasoning}")
                
                if opp.before_code and len(opp.before_code) < 150:
                    output_lines.append(f"      📝 Current: `{opp.before_code.replace(chr(10), ' ')[:100]}...`")
                
                if opp.after_code and len(opp.after_code) < 150:
                    output_lines.append(f"      ✨ Suggested: `{opp.after_code.replace(chr(10), ' ')[:100]}...`")
                
                output_lines.append("")
            
            if len(all_opportunities) > 15:
                output_lines.append(f"... and {len(all_opportunities) - 15} more suggestions")
            
            # Next steps
            output_lines.append(f"\n💡 **Next Steps**")
            high_priority = len(by_severity.get('high', []))
            if high_priority > 0:
                output_lines.append(f"   • Focus on {high_priority} high-priority refactoring opportunities first")
            output_lines.append(f"   • Consider refactoring in small, incremental steps")
            output_lines.append(f"   • Test thoroughly after each refactoring")
            output_lines.append(f"   • Use version control to track changes")
            
            return ToolResult(
                success=True,
                output="\n".join(output_lines),
                action_description=f"Found {len(all_opportunities)} refactoring opportunities"
            )
        
        except Exception as e:
            return ToolResult(
                success=False,
                error=f"Smart refactoring error: {str(e)}"
            )
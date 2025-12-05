"""Documentation synchronization tool to keep docs, code, and comments in sync."""

import ast
import re
import os
import json
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple, Set
from collections import defaultdict
from .base import Tool
from ..types import ToolResult
from ..providers.base import ModelProvider


class DocumentationExtractor(ast.NodeVisitor):
    """Extract documentation from Python code."""
    
    def __init__(self):
        self.functions = []
        self.classes = []
        self.module_docstring = None
        self.current_class = None
    
    def extract_from_file(self, file_path: str, content: str) -> Dict[str, Any]:
        """Extract documentation elements from a Python file."""
        self.functions = []
        self.classes = []
        self.module_docstring = None
        self.current_class = None
        
        try:
            tree = ast.parse(content)
            
            # Get module docstring
            if (tree.body and isinstance(tree.body[0], ast.Expr) 
                and isinstance(tree.body[0].value, ast.Constant)
                and isinstance(tree.body[0].value.value, str)):
                self.module_docstring = tree.body[0].value.value
            
            self.visit(tree)
            
        except SyntaxError:
            pass  # Skip files with syntax errors
        
        return {
            'file_path': file_path,
            'module_docstring': self.module_docstring,
            'functions': self.functions,
            'classes': self.classes
        }
    
    def visit_FunctionDef(self, node):
        """Extract function documentation."""
        docstring = self._get_docstring(node)
        
        function_info = {
            'name': node.name,
            'line': node.lineno,
            'is_public': not node.name.startswith('_'),
            'is_method': self.current_class is not None,
            'class_name': self.current_class,
            'docstring': docstring,
            'has_docstring': docstring is not None,
            'parameters': [arg.arg for arg in node.args.args],
            'returns': node.returns is not None,
            'is_async': isinstance(node, ast.AsyncFunctionDef)
        }
        
        self.functions.append(function_info)
        self.generic_visit(node)
    
    def visit_AsyncFunctionDef(self, node):
        """Handle async functions."""
        self.visit_FunctionDef(node)
    
    def visit_ClassDef(self, node):
        """Extract class documentation."""
        old_class = self.current_class
        self.current_class = node.name
        
        docstring = self._get_docstring(node)
        
        class_info = {
            'name': node.name,
            'line': node.lineno,
            'is_public': not node.name.startswith('_'),
            'docstring': docstring,
            'has_docstring': docstring is not None,
            'base_classes': [self._get_name(base) for base in node.bases],
            'methods': []
        }
        
        self.classes.append(class_info)
        self.generic_visit(node)
        self.current_class = old_class
    
    def _get_docstring(self, node) -> Optional[str]:
        """Extract docstring from a node."""
        if (node.body and isinstance(node.body[0], ast.Expr) 
            and isinstance(node.body[0].value, ast.Constant)
            and isinstance(node.body[0].value.value, str)):
            return node.body[0].value.value
        return None
    
    def _get_name(self, node) -> str:
        """Get name from a node."""
        if isinstance(node, ast.Name):
            return node.id
        elif isinstance(node, ast.Attribute):
            return f"{self._get_name(node.value)}.{node.attr}"
        else:
            return str(node)


class DocumentationAnalyzer:
    """Analyze documentation completeness and consistency."""
    
    def __init__(self):
        self.issues = []
        self.metrics = defaultdict(int)
    
    def analyze_documentation(self, extracted_docs: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Analyze documentation across multiple files."""
        self.issues = []
        self.metrics = defaultdict(int)
        
        for file_doc in extracted_docs:
            self._analyze_file_documentation(file_doc)
        
        return {
            'issues': self.issues,
            'metrics': dict(self.metrics),
            'coverage_stats': self._calculate_coverage_stats(extracted_docs)
        }
    
    def _analyze_file_documentation(self, file_doc: Dict[str, Any]):
        """Analyze documentation for a single file."""
        file_path = file_doc['file_path']
        
        # Module docstring analysis
        if not file_doc['module_docstring'] and not file_path.endswith('__init__.py'):
            self.issues.append({
                'type': 'missing_module_docstring',
                'severity': 'medium',
                'file': file_path,
                'line': 1,
                'message': 'Module missing docstring',
                'suggestion': 'Add module-level docstring explaining purpose'
            })
        
        # Function documentation analysis
        for func in file_doc['functions']:
            self._analyze_function_docs(func, file_path)
        
        # Class documentation analysis
        for cls in file_doc['classes']:
            self._analyze_class_docs(cls, file_path)
        
        # Update metrics
        self.metrics['total_files'] += 1
        self.metrics['total_functions'] += len(file_doc['functions'])
        self.metrics['total_classes'] += len(file_doc['classes'])
        self.metrics['documented_functions'] += sum(1 for f in file_doc['functions'] if f['has_docstring'])
        self.metrics['documented_classes'] += sum(1 for c in file_doc['classes'] if c['has_docstring'])
    
    def _analyze_function_docs(self, func: Dict[str, Any], file_path: str):
        """Analyze documentation for a single function."""
        if func['is_public'] and not func['has_docstring']:
            self.issues.append({
                'type': 'missing_function_docstring',
                'severity': 'medium' if not func['is_method'] else 'low',
                'file': file_path,
                'line': func['line'],
                'message': f"{'Method' if func['is_method'] else 'Function'} '{func['name']}' missing docstring",
                'suggestion': 'Add docstring with description, parameters, and return value'
            })
        
        # Check docstring quality if present
        if func['has_docstring']:
            docstring = func['docstring']
            
            # Check for parameter documentation
            if func['parameters'] and len(func['parameters']) > 1:  # Skip 'self'
                if not any(param in docstring for param in func['parameters'][1:]):
                    self.issues.append({
                        'type': 'incomplete_parameter_docs',
                        'severity': 'low',
                        'file': file_path,
                        'line': func['line'],
                        'message': f"Function '{func['name']}' parameters not documented",
                        'suggestion': 'Document parameters in docstring'
                    })
            
            # Check for return documentation
            if func['returns'] and 'return' not in docstring.lower():
                self.issues.append({
                    'type': 'missing_return_docs',
                    'severity': 'low',
                    'file': file_path,
                    'line': func['line'],
                    'message': f"Function '{func['name']}' return value not documented",
                    'suggestion': 'Document return value in docstring'
                })
    
    def _analyze_class_docs(self, cls: Dict[str, Any], file_path: str):
        """Analyze documentation for a single class."""
        if cls['is_public'] and not cls['has_docstring']:
            self.issues.append({
                'type': 'missing_class_docstring',
                'severity': 'medium',
                'file': file_path,
                'line': cls['line'],
                'message': f"Class '{cls['name']}' missing docstring",
                'suggestion': 'Add class docstring explaining purpose and usage'
            })
    
    def _calculate_coverage_stats(self, extracted_docs: List[Dict[str, Any]]) -> Dict[str, float]:
        """Calculate documentation coverage statistics."""
        stats = {}
        
        if self.metrics['total_functions'] > 0:
            stats['function_coverage'] = (self.metrics['documented_functions'] / 
                                        self.metrics['total_functions']) * 100
        else:
            stats['function_coverage'] = 100.0
        
        if self.metrics['total_classes'] > 0:
            stats['class_coverage'] = (self.metrics['documented_classes'] / 
                                     self.metrics['total_classes']) * 100
        else:
            stats['class_coverage'] = 100.0
        
        # Overall coverage
        total_items = self.metrics['total_functions'] + self.metrics['total_classes']
        documented_items = self.metrics['documented_functions'] + self.metrics['documented_classes']
        
        if total_items > 0:
            stats['overall_coverage'] = (documented_items / total_items) * 100
        else:
            stats['overall_coverage'] = 100.0
        
        return stats


class DocumentationSyncTool(Tool):
    """Tool for synchronizing documentation across code, README, and API docs."""
    
    def __init__(self, model_provider: Optional[ModelProvider] = None):
        self.model_provider = model_provider
    
    @property
    def name(self) -> str:
        return "documentation_sync"
    
    @property
    def description(self) -> str:
        return "Synchronize documentation across codebase: analyze completeness, detect outdated docs, and generate missing documentation"
    
    @property
    def parameters_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["analyze", "generate_missing", "check_sync", "update_readme", "extract_api_docs"],
                    "description": "Documentation action to perform"
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
                "output_format": {
                    "type": "string",
                    "enum": ["markdown", "restructured_text", "json"],
                    "default": "markdown",
                    "description": "Output format for generated documentation"
                },
                "include_private": {
                    "type": "boolean",
                    "default": False,
                    "description": "Include private functions/classes in analysis"
                },
                "severity_threshold": {
                    "type": "string",
                    "enum": ["all", "high", "medium", "low"],
                    "default": "medium",
                    "description": "Minimum severity to report"
                },
                "generate_files": {
                    "type": "boolean",
                    "default": False,
                    "description": "Generate documentation files (DESTRUCTIVE)"
                },
                "update_existing": {
                    "type": "boolean",
                    "default": False,
                    "description": "Update existing documentation files"
                }
            },
            "required": ["action"]
        }
    
    @property
    def is_destructive(self) -> bool:
        return True  # Can generate/update files
    
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
    
    def _extract_documentation(self, files: List[Path], include_private: bool = False) -> List[Dict[str, Any]]:
        """Extract documentation from all files."""
        extracted_docs = []
        extractor = DocumentationExtractor()
        
        for file_path in files:
            # Skip non-Python files for now
            if not str(file_path).endswith('.py'):
                continue
            
            # Skip common ignore patterns
            if any(ignore in str(file_path) for ignore in ['.git', '__pycache__', 'node_modules']):
                continue
            
            try:
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
                
                docs = extractor.extract_from_file(str(file_path), content)
                
                # Filter private items if requested
                if not include_private:
                    docs['functions'] = [f for f in docs['functions'] if f['is_public']]
                    docs['classes'] = [c for c in docs['classes'] if c['is_public']]
                
                extracted_docs.append(docs)
                
            except Exception:
                continue
        
        return extracted_docs
    
    def _generate_markdown_docs(self, extracted_docs: List[Dict[str, Any]]) -> str:
        """Generate markdown documentation."""
        lines = ["# API Documentation\n"]
        lines.append(f"Generated on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        
        for file_doc in extracted_docs:
            if not file_doc['functions'] and not file_doc['classes']:
                continue
            
            file_path = file_doc['file_path']
            lines.append(f"## {file_path}\n")
            
            if file_doc['module_docstring']:
                lines.append(f"{file_doc['module_docstring']}\n")
            
            # Classes
            for cls in file_doc['classes']:
                lines.append(f"### class {cls['name']}")
                if cls['base_classes']:
                    lines.append(f"*Inherits from: {', '.join(cls['base_classes'])}*")
                lines.append("")
                
                if cls['docstring']:
                    lines.append(f"{cls['docstring']}\n")
                else:
                    lines.append("*No documentation available*\n")
            
            # Functions
            for func in file_doc['functions']:
                if func['is_method']:
                    continue  # Skip methods, they're handled with classes
                
                func_name = func['name']
                params = ', '.join(func['parameters']) if func['parameters'] else ''
                lines.append(f"### {func_name}({params})")
                
                if func['is_async']:
                    lines.append("*Async function*")
                
                lines.append("")
                
                if func['docstring']:
                    lines.append(f"{func['docstring']}\n")
                else:
                    lines.append("*No documentation available*\n")
        
        return "\n".join(lines)
    
    def _generate_missing_docstrings(self, extracted_docs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Generate suggestions for missing docstrings using AI."""
        suggestions = []
        
        if not self.model_provider:
            return suggestions
        
        for file_doc in extracted_docs:
            # Generate for functions without docstrings
            for func in file_doc['functions']:
                if not func['has_docstring'] and func['is_public']:
                    prompt = f"""
                    Generate a concise docstring for this Python function:
                    
                    Function name: {func['name']}
                    Parameters: {', '.join(func['parameters'])}
                    Is async: {func['is_async']}
                    Is method: {func['is_method']}
                    Class: {func['class_name'] or 'None'}
                    
                    Provide only the docstring text without quotes or formatting.
                    Be concise but informative about purpose and parameters.
                    """
                    
                    try:
                        response = self.model_provider.generate(prompt, max_tokens=200)
                        if response and response.content:
                            suggestions.append({
                                'type': 'function_docstring',
                                'file': file_doc['file_path'],
                                'line': func['line'],
                                'name': func['name'],
                                'suggestion': response.content.strip()
                            })
                    except Exception:
                        pass
            
            # Generate for classes without docstrings
            for cls in file_doc['classes']:
                if not cls['has_docstring'] and cls['is_public']:
                    prompt = f"""
                    Generate a concise docstring for this Python class:
                    
                    Class name: {cls['name']}
                    Base classes: {', '.join(cls['base_classes']) or 'None'}
                    
                    Provide only the docstring text without quotes or formatting.
                    Be concise but informative about the class purpose and usage.
                    """
                    
                    try:
                        response = self.model_provider.generate(prompt, max_tokens=150)
                        if response and response.content:
                            suggestions.append({
                                'type': 'class_docstring',
                                'file': file_doc['file_path'],
                                'line': cls['line'],
                                'name': cls['name'],
                                'suggestion': response.content.strip()
                            })
                    except Exception:
                        pass
        
        return suggestions
    
    def _check_readme_sync(self, path: str) -> Dict[str, Any]:
        """Check if README is in sync with codebase."""
        readme_files = []
        search_path = Path(path)
        
        # Find README files
        for pattern in ['README.md', 'README.rst', 'README.txt', 'readme.md']:
            readme_path = search_path / pattern
            if readme_path.exists():
                readme_files.append(readme_path)
        
        if not readme_files:
            return {
                'status': 'missing',
                'message': 'No README file found',
                'suggestions': ['Create a README.md file with project overview']
            }
        
        # Analyze README content
        sync_issues = []
        readme_path = readme_files[0]  # Use first found
        
        try:
            with open(readme_path, 'r', encoding='utf-8') as f:
                readme_content = f.read().lower()
            
            # Check for common sections
            expected_sections = ['installation', 'usage', 'api', 'documentation', 'examples']
            missing_sections = []
            
            for section in expected_sections:
                if section not in readme_content:
                    missing_sections.append(section)
            
            if missing_sections:
                sync_issues.append(f"Missing sections: {', '.join(missing_sections)}")
            
            # Check if main modules are mentioned
            python_files = list(search_path.rglob("*.py"))
            main_modules = [f.stem for f in python_files if not f.name.startswith('_') and f.parent == search_path]
            
            mentioned_modules = [mod for mod in main_modules if mod in readme_content]
            unmentioned = set(main_modules) - set(mentioned_modules)
            
            if unmentioned and len(main_modules) > 1:
                sync_issues.append(f"Main modules not mentioned: {', '.join(unmentioned)}")
            
        except Exception as e:
            sync_issues.append(f"Could not analyze README: {str(e)}")
        
        return {
            'status': 'needs_sync' if sync_issues else 'synchronized',
            'file': str(readme_path),
            'issues': sync_issues,
            'suggestions': [f"Update README to address: {issue}" for issue in sync_issues]
        }
    
    def execute(self, **parameters) -> ToolResult:
        """Execute documentation synchronization."""
        try:
            action = parameters.get("action")
            path = parameters.get("path", ".")
            file_pattern = parameters.get("file_pattern", "*.py")
            output_format = parameters.get("output_format", "markdown")
            include_private = parameters.get("include_private", False)
            severity_threshold = parameters.get("severity_threshold", "medium")
            generate_files = parameters.get("generate_files", False)
            update_existing = parameters.get("update_existing", False)
            
            if action == "check_sync":
                # Check README synchronization
                readme_sync = self._check_readme_sync(path)
                
                output_lines = ["📄 Documentation Synchronization Check\n"]
                output_lines.append(f"**README Status:** {readme_sync['status']}")
                
                if readme_sync.get('file'):
                    output_lines.append(f"**README File:** {readme_sync['file']}")
                
                if readme_sync.get('issues'):
                    output_lines.append(f"\n**Sync Issues:**")
                    for issue in readme_sync['issues']:
                        output_lines.append(f"   • {issue}")
                
                if readme_sync.get('suggestions'):
                    output_lines.append(f"\n**Suggestions:**")
                    for suggestion in readme_sync['suggestions']:
                        output_lines.append(f"   • {suggestion}")
                
                return ToolResult(
                    success=True,
                    output="\n".join(output_lines),
                    action_description="Documentation sync check"
                )
            
            # Get files and extract documentation
            files = self._get_files(path, file_pattern)
            if not files:
                return ToolResult(
                    success=True,
                    output="No files found to analyze.",
                    action_description="Documentation analysis"
                )
            
            extracted_docs = self._extract_documentation(files, include_private)
            
            if action == "analyze":
                # Analyze documentation completeness
                analyzer = DocumentationAnalyzer()
                analysis = analyzer.analyze_documentation(extracted_docs)
                
                # Filter by severity
                severity_levels = {'high': 0, 'medium': 1, 'low': 2}
                threshold_level = severity_levels.get(severity_threshold, 1)
                
                filtered_issues = [
                    issue for issue in analysis['issues']
                    if severity_levels.get(issue.get('severity', 'low'), 2) <= threshold_level
                ]
                
                output_lines = ["📚 Documentation Analysis Report\n"]
                
                # Coverage stats
                stats = analysis['coverage_stats']
                output_lines.append("📊 **Coverage Statistics:**")
                output_lines.append(f"   • Overall: {stats['overall_coverage']:.1f}%")
                output_lines.append(f"   • Functions: {stats['function_coverage']:.1f}%")
                output_lines.append(f"   • Classes: {stats['class_coverage']:.1f}%")
                
                # Metrics
                metrics = analysis['metrics']
                output_lines.append(f"\n📈 **Metrics:**")
                output_lines.append(f"   • Files analyzed: {metrics['total_files']}")
                output_lines.append(f"   • Functions: {metrics['documented_functions']}/{metrics['total_functions']}")
                output_lines.append(f"   • Classes: {metrics['documented_classes']}/{metrics['total_classes']}")
                
                # Issues
                if filtered_issues:
                    output_lines.append(f"\n⚠️ **Documentation Issues ({len(filtered_issues)}):**")
                    
                    current_file = None
                    for issue in filtered_issues[:20]:  # Limit output
                        if issue['file'] != current_file:
                            current_file = issue['file']
                            output_lines.append(f"\n📁 **{current_file}:**")
                        
                        severity_emoji = {'high': '🔴', 'medium': '🟡', 'low': '🟢'}
                        emoji = severity_emoji.get(issue.get('severity', 'low'), '⚪')
                        
                        line_info = f"Line {issue['line']}: " if issue.get('line', 0) > 0 else ""
                        output_lines.append(f"   {emoji} {line_info}{issue['message']}")
                        output_lines.append(f"      💡 {issue['suggestion']}")
                
                else:
                    output_lines.append(f"\n✅ **No documentation issues found!**")
            
            elif action == "generate_missing":
                # Generate missing docstrings
                suggestions = self._generate_missing_docstrings(extracted_docs)
                
                if not suggestions:
                    return ToolResult(
                        success=True,
                        output="✅ No missing docstrings found or AI generation not available.",
                        action_description="Generate missing documentation"
                    )
                
                output_lines = ["🤖 Generated Documentation Suggestions\n"]
                
                current_file = None
                for suggestion in suggestions[:15]:  # Limit output
                    if suggestion['file'] != current_file:
                        current_file = suggestion['file']
                        output_lines.append(f"\n📁 **{current_file}:**")
                    
                    output_lines.append(f"\n**{suggestion['type'].replace('_', ' ').title()}: {suggestion['name']}** (Line {suggestion['line']})")
                    output_lines.append(f'```python')
                    output_lines.append(f'"""{suggestion["suggestion"]}"""')
                    output_lines.append(f'```')
            
            elif action == "extract_api_docs":
                # Generate API documentation
                if output_format == "markdown":
                    api_docs = self._generate_markdown_docs(extracted_docs)
                else:
                    api_docs = json.dumps(extracted_docs, indent=2)
                
                if generate_files:
                    # Save to file
                    output_file = f"api_docs.{output_format}"
                    with open(output_file, 'w', encoding='utf-8') as f:
                        f.write(api_docs)
                    
                    return ToolResult(
                        success=True,
                        output=f"✅ API documentation saved to {output_file}",
                        action_description="Generated API documentation file"
                    )
                else:
                    return ToolResult(
                        success=True,
                        output=api_docs,
                        action_description="Generated API documentation"
                    )
            
            return ToolResult(
                success=True,
                output="\n".join(output_lines),
                action_description=f"Documentation {action}"
            )
        
        except Exception as e:
            return ToolResult(
                success=False,
                error=f"Documentation sync error: {str(e)}"
            )
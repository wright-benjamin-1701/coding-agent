"""Semantic code search tool with AST-based analysis."""

import ast
import os
import re
from pathlib import Path
from typing import Dict, Any, List, Optional, Set, Tuple
from .base import Tool
from ..types import ToolResult


class CodePattern:
    """Represents a code pattern for searching."""
    
    def __init__(self, pattern_type: str, name: str, params: List[str] = None, body_contains: List[str] = None):
        self.pattern_type = pattern_type  # function, class, method, variable, import
        self.name = name
        self.params = params or []
        self.body_contains = body_contains or []


class ASTSearcher(ast.NodeVisitor):
    """AST visitor for semantic code search."""
    
    def __init__(self, pattern: CodePattern, file_path: str):
        self.pattern = pattern
        self.file_path = file_path
        self.matches = []
        self.current_class = None
        self.source_lines = []
    
    def search(self, tree: ast.AST, source: str) -> List[Dict[str, Any]]:
        """Search for pattern in AST."""
        self.source_lines = source.split('\n')
        self.visit(tree)
        return self.matches
    
    def _get_source_snippet(self, node: ast.AST) -> str:
        """Extract source code snippet for a node."""
        if hasattr(node, 'lineno') and hasattr(node, 'end_lineno'):
            start_line = max(0, node.lineno - 1)
            end_line = min(len(self.source_lines), node.end_lineno or node.lineno)
            return '\n'.join(self.source_lines[start_line:end_line])
        return ""
    
    def _matches_pattern(self, name: str) -> bool:
        """Check if name matches pattern using wildcards and regex."""
        pattern_name = self.pattern.name
        
        # Exact match
        if pattern_name == name:
            return True
        
        # Wildcard matching
        if '*' in pattern_name:
            regex_pattern = pattern_name.replace('*', '.*')
            return bool(re.match(f'^{regex_pattern}$', name))
        
        # Partial match (contains)
        if pattern_name.lower() in name.lower():
            return True
        
        return False
    
    def visit_FunctionDef(self, node: ast.FunctionDef):
        """Visit function definitions."""
        if self.pattern.pattern_type in ['function', 'method']:
            if self._matches_pattern(node.name):
                # Check parameter matching if specified
                param_match = True
                if self.pattern.params:
                    node_params = [arg.arg for arg in node.args.args]
                    for required_param in self.pattern.params:
                        if not any(required_param.lower() in param.lower() for param in node_params):
                            param_match = False
                            break
                
                # Check body content if specified
                body_match = True
                if self.pattern.body_contains:
                    source_snippet = self._get_source_snippet(node)
                    for required_content in self.pattern.body_contains:
                        if required_content.lower() not in source_snippet.lower():
                            body_match = False
                            break
                
                if param_match and body_match:
                    self.matches.append({
                        'type': 'method' if self.current_class else 'function',
                        'name': node.name,
                        'class': self.current_class,
                        'line': node.lineno,
                        'file': self.file_path,
                        'params': [arg.arg for arg in node.args.args],
                        'source': self._get_source_snippet(node)
                    })
        
        self.generic_visit(node)
    
    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef):
        """Visit async function definitions."""
        self.visit_FunctionDef(node)
    
    def visit_ClassDef(self, node: ast.ClassDef):
        """Visit class definitions."""
        old_class = self.current_class
        self.current_class = node.name
        
        if self.pattern.pattern_type == 'class':
            if self._matches_pattern(node.name):
                # Check body content if specified
                body_match = True
                if self.pattern.body_contains:
                    source_snippet = self._get_source_snippet(node)
                    for required_content in self.pattern.body_contains:
                        if required_content.lower() not in source_snippet.lower():
                            body_match = False
                            break
                
                if body_match:
                    base_classes = [base.id if isinstance(base, ast.Name) else str(base) for base in node.bases]
                    self.matches.append({
                        'type': 'class',
                        'name': node.name,
                        'line': node.lineno,
                        'file': self.file_path,
                        'bases': base_classes,
                        'source': self._get_source_snippet(node)
                    })
        
        self.generic_visit(node)
        self.current_class = old_class
    
    def visit_Import(self, node: ast.Import):
        """Visit import statements."""
        if self.pattern.pattern_type == 'import':
            for alias in node.names:
                if self._matches_pattern(alias.name):
                    self.matches.append({
                        'type': 'import',
                        'name': alias.name,
                        'alias': alias.asname,
                        'line': node.lineno,
                        'file': self.file_path,
                        'source': self._get_source_snippet(node)
                    })
    
    def visit_ImportFrom(self, node: ast.ImportFrom):
        """Visit from-import statements."""
        if self.pattern.pattern_type == 'import':
            module = node.module or ""
            for alias in node.names:
                full_name = f"{module}.{alias.name}" if module else alias.name
                if self._matches_pattern(full_name) or self._matches_pattern(alias.name):
                    self.matches.append({
                        'type': 'from_import',
                        'name': alias.name,
                        'module': module,
                        'alias': alias.asname,
                        'line': node.lineno,
                        'file': self.file_path,
                        'source': self._get_source_snippet(node)
                    })
    
    def visit_Assign(self, node: ast.Assign):
        """Visit variable assignments."""
        if self.pattern.pattern_type == 'variable':
            for target in node.targets:
                if isinstance(target, ast.Name):
                    if self._matches_pattern(target.id):
                        self.matches.append({
                            'type': 'variable',
                            'name': target.id,
                            'class': self.current_class,
                            'line': node.lineno,
                            'file': self.file_path,
                            'source': self._get_source_snippet(node)
                        })


class SemanticSearchTool(Tool):
    """Semantic code search using AST analysis."""
    
    @property
    def name(self) -> str:
        return "semantic_search"
    
    @property
    def description(self) -> str:
        return "Advanced semantic code search using AST analysis. Find functions, classes, methods, variables, and imports by pattern matching with context awareness."
    
    @property
    def parameters_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "pattern_type": {
                    "type": "string",
                    "enum": ["function", "class", "method", "variable", "import", "usage"],
                    "description": "Type of code element to search for"
                },
                "name": {
                    "type": "string",
                    "description": "Name pattern to search for (supports wildcards with *)"
                },
                "path": {
                    "type": "string",
                    "default": ".",
                    "description": "Path to search in"
                },
                "file_pattern": {
                    "type": "string",
                    "default": "*.py",
                    "description": "File pattern to include (e.g., '*.py', '*.js')"
                },
                "params": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Required parameter names (for functions/methods)"
                },
                "body_contains": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Text that must appear in the body/implementation"
                },
                "class_name": {
                    "type": "string",
                    "description": "Class name to search within (for methods)"
                },
                "similar_to": {
                    "type": "string",
                    "description": "Find code similar to this reference (file:line or code snippet)"
                }
            },
            "required": ["pattern_type", "name"]
        }
    
    @property
    def is_destructive(self) -> bool:
        return False
    
    def _get_files_to_search(self, path: str, file_pattern: str) -> List[Path]:
        """Get list of files to search."""
        search_path = Path(path)
        if not search_path.exists():
            return []
        
        # Convert glob pattern to file extensions
        if file_pattern.startswith("*."):
            extension = file_pattern[1:]  # Remove *
            if search_path.is_file():
                return [search_path] if search_path.suffix == extension else []
            else:
                return list(search_path.rglob(f"*{extension}"))
        
        return [search_path] if search_path.is_file() else list(search_path.rglob(file_pattern))
    
    def _search_usage(self, name: str, files: List[Path]) -> List[Dict[str, Any]]:
        """Search for usage of a name in files."""
        results = []
        
        for file_path in files:
            try:
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
                    lines = content.split('\n')
                
                # Simple text-based usage search
                for line_num, line in enumerate(lines, 1):
                    if name in line:
                        # Try to determine context
                        context = "usage"
                        if f"def {name}" in line or f"class {name}" in line:
                            context = "definition"
                        elif f"import {name}" in line or f"from .* import.*{name}" in line:
                            context = "import"
                        elif f"{name}(" in line:
                            context = "call"
                        elif f"{name} =" in line or f"= {name}" in line:
                            context = "assignment"
                        
                        results.append({
                            'type': 'usage',
                            'name': name,
                            'context': context,
                            'line': line_num,
                            'file': str(file_path),
                            'source': line.strip()
                        })
            except Exception:
                continue
        
        return results
    
    def _find_similar_code(self, reference: str, files: List[Path]) -> List[Dict[str, Any]]:
        """Find code similar to reference."""
        # This is a simplified similarity search
        # In a production system, you might use more sophisticated techniques
        results = []
        
        # Extract keywords from reference
        if ":" in reference:  # file:line format
            try:
                file_path, line_num = reference.split(":", 1)
                with open(file_path, 'r', encoding='utf-8') as f:
                    lines = f.readlines()
                    if int(line_num) <= len(lines):
                        reference = lines[int(line_num) - 1].strip()
            except Exception:
                pass
        
        # Extract meaningful tokens
        reference_tokens = set(re.findall(r'\b\w+\b', reference.lower()))
        
        for file_path in files:
            try:
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
                    lines = content.split('\n')
                
                for line_num, line in enumerate(lines, 1):
                    line_tokens = set(re.findall(r'\b\w+\b', line.lower()))
                    # Simple similarity score based on common tokens
                    if reference_tokens and line_tokens:
                        similarity = len(reference_tokens & line_tokens) / len(reference_tokens | line_tokens)
                        if similarity > 0.3:  # Threshold for similarity
                            results.append({
                                'type': 'similar',
                                'similarity': similarity,
                                'line': line_num,
                                'file': str(file_path),
                                'source': line.strip()
                            })
            except Exception:
                continue
        
        # Sort by similarity score
        results.sort(key=lambda x: x['similarity'], reverse=True)
        return results[:20]  # Limit results
    
    def execute(self, **parameters) -> ToolResult:
        """Execute semantic search."""
        try:
            pattern_type = parameters.get("pattern_type")
            name = parameters.get("name", "")
            path = parameters.get("path", ".")
            file_pattern = parameters.get("file_pattern", "*.py")
            params = parameters.get("params", [])
            body_contains = parameters.get("body_contains", [])
            class_name = parameters.get("class_name")
            similar_to = parameters.get("similar_to")
            
            files = self._get_files_to_search(path, file_pattern)
            
            if not files:
                return ToolResult(
                    success=True,
                    output="No files found matching the search criteria.",
                    action_description=f"Searched for {pattern_type} '{name}'"
                )
            
            # Handle special cases
            if pattern_type == "usage":
                results = self._search_usage(name, files)
            elif similar_to:
                results = self._find_similar_code(similar_to, files)
            else:
                # AST-based search
                pattern = CodePattern(pattern_type, name, params, body_contains)
                results = []
                
                for file_path in files:
                    try:
                        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                            content = f.read()
                        
                        tree = ast.parse(content)
                        searcher = ASTSearcher(pattern, str(file_path))
                        file_results = searcher.search(tree, content)
                        
                        # Filter by class if specified
                        if class_name:
                            file_results = [r for r in file_results if r.get('class') == class_name]
                        
                        results.extend(file_results)
                    
                    except (SyntaxError, UnicodeDecodeError):
                        continue
                    except Exception as e:
                        continue
            
            if not results:
                return ToolResult(
                    success=True,
                    output=f"No matches found for {pattern_type} '{name}'",
                    action_description=f"Searched for {pattern_type} '{name}'"
                )
            
            # Format results
            output_lines = [f"Found {len(results)} matches for {pattern_type} '{name}':\n"]
            
            for result in results:
                result_type = result['type']
                file_path = result['file']
                line_num = result['line']
                
                if result_type in ['function', 'method']:
                    class_info = f" in {result['class']}" if result.get('class') else ""
                    params_info = f"({', '.join(result['params'])})" if result.get('params') else "()"
                    output_lines.append(f"🔧 {result['name']}{params_info}{class_info}")
                elif result_type == 'class':
                    bases_info = f" extends {', '.join(result['bases'])}" if result.get('bases') else ""
                    output_lines.append(f"📦 {result['name']}{bases_info}")
                elif result_type == 'variable':
                    class_info = f" in {result['class']}" if result.get('class') else ""
                    output_lines.append(f"🔢 {result['name']}{class_info}")
                elif result_type in ['import', 'from_import']:
                    module_info = f" from {result.get('module', '')}" if result.get('module') else ""
                    output_lines.append(f"📥 {result['name']}{module_info}")
                elif result_type == 'usage':
                    output_lines.append(f"🔍 {result['context']}: {result['name']}")
                elif result_type == 'similar':
                    similarity = result.get('similarity', 0)
                    output_lines.append(f"🔗 Similar ({similarity:.2f}): {result['source'][:50]}...")
                
                output_lines.append(f"   📁 {file_path}:{line_num}")
                
                if result.get('source') and len(result['source']) < 200:
                    output_lines.append(f"   💾 {result['source'][:100]}...")
                
                output_lines.append("")
            
            return ToolResult(
                success=True,
                output="\n".join(output_lines),
                action_description=f"Found {len(results)} matches for {pattern_type} '{name}'"
            )
        
        except Exception as e:
            return ToolResult(
                success=False,
                error=f"Semantic search error: {str(e)}"
            )
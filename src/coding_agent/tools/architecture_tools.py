"""Architecture analysis tools for code structure and dependency visualization."""

import os
import re
import ast
import json
from typing import Dict, Any, List, Set, Optional, Tuple
from pathlib import Path
from collections import defaultdict, Counter
from .base import Tool
from ..types import ToolResult


class ArchitectureAnalysisTool(Tool):
    """Tool for analyzing code architecture, dependencies, and structural patterns."""
    
    @property
    def name(self) -> str:
        return "analyze_architecture"
    
    @property
    def description(self) -> str:
        return "Analyze code architecture, dependencies, imports, class hierarchies, and structural patterns"
    
    @property
    def parameters_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "target": {
                    "type": "string",
                    "description": "Directory path to analyze"
                },
                "analysis_type": {
                    "type": "string",
                    "enum": ["dependencies", "structure", "complexity", "patterns", "all"],
                    "description": "Type of architecture analysis to perform"
                },
                "output_format": {
                    "type": "string",
                    "enum": ["text", "json", "graph"],
                    "description": "Format for analysis output"
                },
                "language": {
                    "type": "string",
                    "enum": ["python", "javascript", "typescript", "java", "auto"],
                    "description": "Programming language to analyze (auto-detect if not specified)"
                },
                "depth": {
                    "type": "integer",
                    "description": "Maximum depth for dependency analysis (1-5)",
                    "minimum": 1,
                    "maximum": 5
                }
            },
            "required": ["target"]
        }
    
    @property
    def is_destructive(self) -> bool:
        return False  # Read-only analysis
    
    def execute(self, **parameters) -> ToolResult:
        """Execute architecture analysis."""
        target = parameters.get("target", ".")
        analysis_type = parameters.get("analysis_type", "all")
        output_format = parameters.get("output_format", "text")
        language = parameters.get("language", "auto")
        depth = parameters.get("depth", 3)
        
        if not os.path.exists(target):
            return ToolResult(
                success=False,
                output=None,
                error=f"Target directory not found: {target}"
            )
        
        if not os.path.isdir(target):
            return ToolResult(
                success=False,
                output=None,
                error=f"Target must be a directory: {target}"
            )
        
        try:
            # Auto-detect language if needed
            if language == "auto":
                language = self._detect_language(target)
            
            # Collect files for analysis
            files = self._collect_source_files(target, language)
            
            if not files:
                return ToolResult(
                    success=True,
                    output=f"No {language} source files found in {target}",
                    action_description=f"Architecture analysis - no files found"
                )
            
            # Perform analysis
            analysis_results = {}
            
            if analysis_type in ["all", "dependencies"]:
                analysis_results["dependencies"] = self._analyze_dependencies(files, language, depth)
            
            if analysis_type in ["all", "structure"]:
                analysis_results["structure"] = self._analyze_structure(files, language)
            
            if analysis_type in ["all", "complexity"]:
                analysis_results["complexity"] = self._analyze_complexity(files, language)
            
            if analysis_type in ["all", "patterns"]:
                analysis_results["patterns"] = self._analyze_patterns(files, language)
            
            # Format output
            if output_format == "json":
                output = json.dumps(analysis_results, indent=2)
            elif output_format == "graph":
                output = self._format_graph_output(analysis_results)
            else:
                output = self._format_text_output(analysis_results, target, len(files))
            
            return ToolResult(
                success=True,
                output=output,
                action_description=f"Architecture analysis of {target} ({len(files)} files)"
            )
            
        except Exception as e:
            return ToolResult(
                success=False,
                output=None,
                error=f"Architecture analysis failed: {str(e)}"
            )
    
    def _detect_language(self, target: str) -> str:
        """Auto-detect the primary programming language."""
        extensions = Counter()
        
        for root, dirs, files in os.walk(target):
            dirs[:] = [d for d in dirs if not d.startswith('.') and d not in {'node_modules', '__pycache__', 'build', 'dist'}]
            
            for file in files:
                ext = Path(file).suffix.lower()
                if ext in {'.py', '.js', '.ts', '.java', '.cpp', '.c', '.go', '.rs'}:
                    extensions[ext] += 1
        
        if not extensions:
            return "python"  # Default fallback
        
        # Map extensions to languages
        ext_to_lang = {
            '.py': 'python',
            '.js': 'javascript', 
            '.ts': 'typescript',
            '.java': 'java',
            '.cpp': 'cpp',
            '.c': 'c',
            '.go': 'go',
            '.rs': 'rust'
        }
        
        most_common_ext = extensions.most_common(1)[0][0]
        return ext_to_lang.get(most_common_ext, 'python')
    
    def _collect_source_files(self, target: str, language: str) -> List[str]:
        """Collect source files for analysis."""
        extensions = {
            'python': {'.py'},
            'javascript': {'.js'},
            'typescript': {'.ts'},
            'java': {'.java'},
            'cpp': {'.cpp', '.cc', '.cxx'},
            'c': {'.c', '.h'},
            'go': {'.go'},
            'rust': {'.rs'}
        }
        
        valid_extensions = extensions.get(language, {'.py'})
        files = []
        
        for root, dirs, filenames in os.walk(target):
            # Skip common non-source directories
            dirs[:] = [d for d in dirs if d not in {'.git', '__pycache__', 'node_modules', '.env', 'venv', '.venv', 'build', 'dist', 'target'}]
            
            for filename in filenames:
                if Path(filename).suffix.lower() in valid_extensions:
                    full_path = os.path.join(root, filename)
                    # Skip files that are too large
                    try:
                        if os.path.getsize(full_path) < 1024 * 1024:  # 1MB limit
                            files.append(full_path)
                    except OSError:
                        continue
        
        return files[:200]  # Limit to prevent overwhelming analysis
    
    def _analyze_dependencies(self, files: List[str], language: str, depth: int) -> Dict[str, Any]:
        """Analyze dependencies between modules."""
        if language == "python":
            return self._analyze_python_dependencies(files, depth)
        elif language in ["javascript", "typescript"]:
            return self._analyze_js_dependencies(files, depth)
        else:
            return {"error": f"Dependency analysis not implemented for {language}"}
    
    def _analyze_python_dependencies(self, files: List[str], depth: int) -> Dict[str, Any]:
        """Analyze Python import dependencies."""
        dependencies = defaultdict(set)
        external_deps = set()
        internal_modules = set()
        
        # First pass: identify all internal modules
        for file_path in files:
            try:
                rel_path = os.path.relpath(file_path)
                module_name = rel_path.replace(os.sep, '.').replace('.py', '')
                internal_modules.add(module_name)
            except:
                continue
        
        # Second pass: analyze imports
        for file_path in files:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                try:
                    tree = ast.parse(content)
                except SyntaxError:
                    continue
                
                rel_path = os.path.relpath(file_path)
                current_module = rel_path.replace(os.sep, '.').replace('.py', '')
                
                for node in ast.walk(tree):
                    imports = []
                    
                    if isinstance(node, ast.Import):
                        for alias in node.names:
                            imports.append(alias.name)
                    elif isinstance(node, ast.ImportFrom):
                        if node.module:
                            imports.append(node.module)
                    
                    for imp in imports:
                        # Determine if it's internal or external
                        is_internal = any(imp.startswith(internal_mod.split('.')[0]) for internal_mod in internal_modules)
                        
                        if is_internal:
                            dependencies[current_module].add(imp)
                        else:
                            # Track external dependencies
                            external_deps.add(imp.split('.')[0])
            
            except Exception:
                continue
        
        # Build dependency graph
        graph = {}
        for module, deps in dependencies.items():
            graph[module] = list(deps)
        
        # Find circular dependencies
        circular_deps = self._find_circular_dependencies(graph)
        
        return {
            "internal_dependencies": graph,
            "external_dependencies": sorted(list(external_deps)),
            "circular_dependencies": circular_deps,
            "dependency_count": {mod: len(deps) for mod, deps in dependencies.items()},
            "most_dependent_modules": sorted(dependencies.items(), key=lambda x: len(x[1]), reverse=True)[:10]
        }
    
    def _analyze_js_dependencies(self, files: List[str], depth: int) -> Dict[str, Any]:
        """Analyze JavaScript/TypeScript import dependencies."""
        dependencies = defaultdict(set)
        external_deps = set()
        
        import_patterns = [
            r'import\\s+.*?from\\s+["\']([^"\']+)["\']',  # import ... from '...'
            r'require\\s*\\(["\']([^"\']+)["\']\\)',  # require('...')
            r'import\\s*\\(["\']([^"\']+)["\']\\)',  # dynamic import('...')
        ]
        
        for file_path in files:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                current_module = os.path.relpath(file_path)
                
                for pattern in import_patterns:
                    matches = re.findall(pattern, content)
                    for match in matches:
                        if match.startswith('./') or match.startswith('../'):
                            # Relative import - internal dependency
                            dependencies[current_module].add(match)
                        elif not match.startswith('@') and '/' not in match:
                            # External package
                            external_deps.add(match)
                        else:
                            # Could be external or scoped package
                            external_deps.add(match.split('/')[0])
            
            except Exception:
                continue
        
        graph = {mod: list(deps) for mod, deps in dependencies.items()}
        circular_deps = self._find_circular_dependencies(graph)
        
        return {
            "internal_dependencies": graph,
            "external_dependencies": sorted(list(external_deps)),
            "circular_dependencies": circular_deps,
            "dependency_count": {mod: len(deps) for mod, deps in dependencies.items()}
        }
    
    def _analyze_structure(self, files: List[str], language: str) -> Dict[str, Any]:
        """Analyze code structure and organization."""
        structure = {
            "total_files": len(files),
            "file_sizes": {},
            "directory_structure": {},
            "largest_files": [],
            "file_types": Counter()
        }
        
        total_lines = 0
        file_line_counts = []
        
        for file_path in files:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    lines = f.readlines()
                    line_count = len(lines)
                    non_empty_lines = len([line for line in lines if line.strip()])
                
                file_size = os.path.getsize(file_path)
                rel_path = os.path.relpath(file_path)
                
                structure["file_sizes"][rel_path] = {
                    "bytes": file_size,
                    "lines": line_count,
                    "non_empty_lines": non_empty_lines
                }
                
                total_lines += line_count
                file_line_counts.append((rel_path, line_count))
                
                # Track file types
                ext = Path(file_path).suffix
                structure["file_types"][ext] += 1
                
                # Build directory structure
                dir_path = os.path.dirname(rel_path)
                if dir_path:
                    parts = dir_path.split(os.sep)
                    current = structure["directory_structure"]
                    for part in parts:
                        if part not in current:
                            current[part] = {}
                        current = current[part]
            
            except Exception:
                continue
        
        # Find largest files
        structure["largest_files"] = sorted(file_line_counts, key=lambda x: x[1], reverse=True)[:10]
        structure["total_lines"] = total_lines
        structure["average_file_size"] = total_lines / len(files) if files else 0
        
        return structure
    
    def _analyze_complexity(self, files: List[str], language: str) -> Dict[str, Any]:
        """Analyze code complexity metrics."""
        complexity = {
            "cyclomatic_complexity": {},
            "function_counts": {},
            "class_counts": {},
            "nesting_levels": {},
            "complexity_distribution": Counter()
        }
        
        if language == "python":
            return self._analyze_python_complexity(files)
        else:
            # Basic complexity analysis for other languages
            return self._analyze_general_complexity(files)
    
    def _analyze_python_complexity(self, files: List[str]) -> Dict[str, Any]:
        """Analyze Python-specific complexity metrics."""
        complexity = {
            "files": {},
            "functions": [],
            "classes": [],
            "total_complexity": 0
        }
        
        for file_path in files:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                try:
                    tree = ast.parse(content)
                except SyntaxError:
                    continue
                
                rel_path = os.path.relpath(file_path)
                file_complexity = 0
                functions = []
                classes = []
                
                for node in ast.walk(tree):
                    if isinstance(node, ast.FunctionDef):
                        func_complexity = self._calculate_cyclomatic_complexity(node)
                        functions.append({
                            "name": node.name,
                            "line": node.lineno,
                            "complexity": func_complexity
                        })
                        file_complexity += func_complexity
                    
                    elif isinstance(node, ast.ClassDef):
                        methods = [n for n in node.body if isinstance(n, ast.FunctionDef)]
                        classes.append({
                            "name": node.name,
                            "line": node.lineno,
                            "methods": len(methods)
                        })
                
                complexity["files"][rel_path] = {
                    "complexity": file_complexity,
                    "functions": len(functions),
                    "classes": len(classes)
                }
                
                complexity["functions"].extend([{**f, "file": rel_path} for f in functions])
                complexity["classes"].extend([{**c, "file": rel_path} for c in classes])
                complexity["total_complexity"] += file_complexity
            
            except Exception:
                continue
        
        # Sort by complexity
        complexity["functions"].sort(key=lambda x: x["complexity"], reverse=True)
        complexity["classes"].sort(key=lambda x: x["methods"], reverse=True)
        
        return complexity
    
    def _analyze_general_complexity(self, files: List[str]) -> Dict[str, Any]:
        """General complexity analysis for non-Python files."""
        complexity = {"files": {}, "total_functions": 0, "total_classes": 0}
        
        # Simple pattern-based analysis
        function_patterns = [
            r'^\\s*function\\s+\\w+',  # JavaScript function
            r'^\\s*def\\s+\\w+',  # Python function  
            r'^\\s*public\\s+.*\\s+\\w+\\s*\\(',  # Java method
        ]
        
        class_patterns = [
            r'^\\s*class\\s+\\w+',  # General class
            r'^\\s*public\\s+class\\s+\\w+',  # Java class
        ]
        
        for file_path in files:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                functions = 0
                classes = 0
                
                for pattern in function_patterns:
                    functions += len(re.findall(pattern, content, re.MULTILINE))
                
                for pattern in class_patterns:
                    classes += len(re.findall(pattern, content, re.MULTILINE))
                
                rel_path = os.path.relpath(file_path)
                complexity["files"][rel_path] = {
                    "functions": functions,
                    "classes": classes
                }
                
                complexity["total_functions"] += functions
                complexity["total_classes"] += classes
            
            except Exception:
                continue
        
        return complexity
    
    def _analyze_patterns(self, files: List[str], language: str) -> Dict[str, Any]:
        """Analyze architectural patterns and code smells."""
        patterns = {
            "design_patterns": Counter(),
            "code_smells": [],
            "naming_conventions": {},
            "architecture_issues": []
        }
        
        # Common design patterns to look for
        pattern_indicators = {
            "Singleton": [r'class\\s+\\w+.*:\\s*\\n.*_instance\\s*=', r'getInstance\\(\\)'],
            "Factory": [r'create\\w*\\(', r'Factory\\w*\\('],
            "Observer": [r'addObserver', r'notifyObservers', r'addEventListener'],
            "Strategy": [r'Strategy\\w*', r'\\w*Strategy'],
            "Decorator": [r'@\\w+', r'decorator'],
        }
        
        long_function_threshold = 50
        large_class_threshold = 500
        
        for file_path in files:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                    lines = content.split('\\n')
                
                rel_path = os.path.relpath(file_path)
                
                # Check for design patterns
                for pattern_name, indicators in pattern_indicators.items():
                    for indicator in indicators:
                        if re.search(indicator, content, re.IGNORECASE):
                            patterns["design_patterns"][pattern_name] += 1
                            break
                
                # Check for code smells
                if len(lines) > large_class_threshold:
                    patterns["code_smells"].append({
                        "type": "Large File",
                        "file": rel_path,
                        "lines": len(lines),
                        "severity": "medium"
                    })
                
                # Long functions (basic detection)
                if language == "python":
                    function_starts = [(i, line) for i, line in enumerate(lines) if re.match(r'^\\s*def\\s+', line)]
                    for i, (line_num, func_line) in enumerate(function_starts):
                        next_func_line = function_starts[i + 1][0] if i + 1 < len(function_starts) else len(lines)
                        func_length = next_func_line - line_num
                        
                        if func_length > long_function_threshold:
                            func_name = re.search(r'def\\s+(\\w+)', func_line)
                            patterns["code_smells"].append({
                                "type": "Long Function",
                                "file": rel_path,
                                "function": func_name.group(1) if func_name else "unknown",
                                "lines": func_length,
                                "severity": "medium"
                            })
            
            except Exception:
                continue
        
        return patterns
    
    def _calculate_cyclomatic_complexity(self, node: ast.AST) -> int:
        """Calculate cyclomatic complexity for an AST node."""
        complexity = 1  # Base complexity
        
        for child in ast.walk(node):
            # Decision points increase complexity
            if isinstance(child, (ast.If, ast.While, ast.For, ast.AsyncFor)):
                complexity += 1
            elif isinstance(child, ast.ExceptHandler):
                complexity += 1
            elif isinstance(child, ast.With, ast.AsyncWith):
                complexity += 1
            elif isinstance(child, ast.BoolOp):
                complexity += len(child.values) - 1
        
        return complexity
    
    def _find_circular_dependencies(self, graph: Dict[str, List[str]]) -> List[List[str]]:
        """Find circular dependencies in a dependency graph."""
        def dfs(node, path, visited, rec_stack):
            if node in rec_stack:
                # Found a cycle
                cycle_start = rec_stack.index(node)
                return [rec_stack[cycle_start:]]
            
            if node in visited:
                return []
            
            visited.add(node)
            rec_stack.append(node)
            cycles = []
            
            for neighbor in graph.get(node, []):
                cycles.extend(dfs(neighbor, path, visited, rec_stack))
            
            rec_stack.pop()
            return cycles
        
        all_cycles = []
        visited = set()
        
        for node in graph:
            if node not in visited:
                cycles = dfs(node, [], visited, [])
                all_cycles.extend(cycles)
        
        return all_cycles
    
    def _format_text_output(self, results: Dict[str, Any], target: str, file_count: int) -> str:
        """Format analysis results as human-readable text."""
        output = f"🏗️  Architecture Analysis: {target}\n"
        output += f"📁 Analyzed {file_count} files\n\n"
        
        # Dependencies
        if "dependencies" in results:
            deps = results["dependencies"]
            output += "📦 DEPENDENCIES\n" + "=" * 50 + "\n"
            
            if "external_dependencies" in deps:
                output += f"External packages ({len(deps['external_dependencies'])}): "
                output += ", ".join(deps["external_dependencies"][:10])
                if len(deps["external_dependencies"]) > 10:
                    output += f" ... and {len(deps['external_dependencies']) - 10} more"
                output += "\n\n"
            
            if "circular_dependencies" in deps and deps["circular_dependencies"]:
                output += f"⚠️  Circular Dependencies Found ({len(deps['circular_dependencies'])}):\n"
                for cycle in deps["circular_dependencies"][:5]:
                    output += f"  • {' → '.join(cycle)} → {cycle[0]}\n"
                output += "\n"
        
        # Structure
        if "structure" in results:
            struct = results["structure"]
            output += "📋 STRUCTURE\n" + "=" * 50 + "\n"
            output += f"Total lines of code: {struct.get('total_lines', 0):,}\n"
            output += f"Average file size: {struct.get('average_file_size', 0):.1f} lines\n"
            
            if "largest_files" in struct:
                output += "\nLargest files:\n"
                for file_path, lines in struct["largest_files"][:5]:
                    output += f"  • {file_path}: {lines:,} lines\n"
            output += "\n"
        
        # Complexity
        if "complexity" in results:
            comp = results["complexity"]
            output += "⚡ COMPLEXITY\n" + "=" * 50 + "\n"
            
            if "functions" in comp and comp["functions"]:
                output += "Most complex functions:\n"
                for func in comp["functions"][:5]:
                    output += f"  • {func['file']}:{func['line']} {func['name']} (complexity: {func['complexity']})\n"
            
            if "total_complexity" in comp:
                output += f"\nTotal cyclomatic complexity: {comp['total_complexity']}\n"
            output += "\n"
        
        # Patterns
        if "patterns" in results:
            patterns = results["patterns"]
            output += "🎯 PATTERNS & ISSUES\n" + "=" * 50 + "\n"
            
            if patterns.get("design_patterns"):
                output += "Design patterns detected:\n"
                for pattern, count in patterns["design_patterns"].most_common():
                    output += f"  • {pattern}: {count} occurrences\n"
                output += "\n"
            
            if patterns.get("code_smells"):
                output += f"Code smells found ({len(patterns['code_smells'])}):\n"
                for smell in patterns["code_smells"][:5]:
                    output += f"  • {smell['type']} in {smell['file']}\n"
                output += "\n"
        
        return output
    
    def _format_graph_output(self, results: Dict[str, Any]) -> str:
        """Format results as a simple graph representation."""
        output = "DEPENDENCY GRAPH\n" + "=" * 30 + "\n\n"
        
        if "dependencies" in results and "internal_dependencies" in results["dependencies"]:
            deps = results["dependencies"]["internal_dependencies"]
            
            for module, dependencies in list(deps.items())[:20]:  # Limit output
                output += f"{module}\n"
                for dep in dependencies:
                    output += f"  └─ {dep}\n"
                output += "\n"
        
        return output
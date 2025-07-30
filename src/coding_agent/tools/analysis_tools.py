"""Analysis and summary tools that output plain text."""

import os
import subprocess
from typing import Dict, Any, List
from .base import Tool
from ..types import ToolResult


class SummarizeCodeTool(Tool):
    """Tool for generating plain text summaries of codebases or files."""
    
    @property
    def name(self) -> str:
        return "summarize_code"
    
    @property
    def description(self) -> str:
        return "Analyze and summarize code structure, purpose, and key components. Outputs plain text summary."
    
    @property
    def parameters_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "target": {
                    "type": "string",
                    "description": "Target to summarize: 'codebase' for entire project, or specific file/directory path"
                },
                "focus": {
                    "type": "string", 
                    "enum": ["overview", "architecture", "functionality", "dependencies"],
                    "description": "What aspect to focus the summary on"
                }
            },
            "required": ["target"]
        }
    
    @property
    def is_destructive(self) -> bool:
        return False
    
    def execute(self, **parameters) -> ToolResult:
        target = parameters.get("target", "codebase")
        focus = parameters.get("focus", "overview")
        
        try:
            if target == "codebase":
                output = self._summarize_codebase(focus)
            elif os.path.isfile(target):
                output = self._summarize_file(target, focus)
            elif os.path.isdir(target):
                output = self._summarize_directory(target, focus)
            else:
                return ToolResult(success=False, output=None, error=f"Target '{target}' not found or not accessible.")
            
            return ToolResult(success=True, output=output, action_description=f"Summarized {target} with focus on {focus}")
        except Exception as e:
            return ToolResult(success=False, output=None, error=f"Error summarizing {target}: {str(e)}")
    
    def _summarize_codebase(self, focus: str) -> str:
        """Generate a summary of the entire codebase."""
        summary_parts = []
        
        # Project overview
        summary_parts.append("# Codebase Summary")
        summary_parts.append("")
        
        # Get project structure
        structure = self._get_project_structure()
        summary_parts.append("## Project Structure")
        summary_parts.extend(structure)
        summary_parts.append("")
        
        # Analyze main components based on focus
        if focus in ["overview", "architecture"]:
            components = self._analyze_main_components()
            summary_parts.append("## Main Components")
            summary_parts.extend(components)
            summary_parts.append("")
        
        if focus in ["overview", "functionality"]:
            functionality = self._analyze_functionality()
            summary_parts.append("## Key Functionality")
            summary_parts.extend(functionality)
            summary_parts.append("")
        
        if focus in ["overview", "dependencies"]:
            deps = self._analyze_dependencies()
            summary_parts.append("## Dependencies & Technologies")
            summary_parts.extend(deps)
            summary_parts.append("")
        
        return "\n".join(summary_parts)
    
    def _summarize_file(self, file_path: str, focus: str) -> str:
        """Generate a summary of a specific file."""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
        except Exception as e:
            return f"Error reading file {file_path}: {e}"
        
        summary_parts = []
        summary_parts.append(f"# Summary of {file_path}")
        summary_parts.append("")
        
        # Basic file info
        lines = content.split('\n')
        summary_parts.append(f"**File size:** {len(lines)} lines, {len(content)} characters")
        summary_parts.append("")
        
        # Language-specific analysis
        if file_path.endswith('.py'):
            analysis = self._analyze_python_file(content, focus)
            summary_parts.extend(analysis)
        elif file_path.endswith(('.js', '.ts')):
            analysis = self._analyze_javascript_file(content, focus)
            summary_parts.extend(analysis)
        else:
            # Generic analysis
            summary_parts.append("**Content Preview:**")
            preview_lines = lines[:10]
            for line in preview_lines:
                summary_parts.append(f"    {line}")
            if len(lines) > 10:
                summary_parts.append("    ...")
        
        return "\n".join(summary_parts)
    
    def _summarize_directory(self, dir_path: str, focus: str) -> str:
        """Generate a summary of a directory and its contents."""
        summary_parts = []
        summary_parts.append(f"# Summary of {dir_path}/")
        summary_parts.append("")
        
        try:
            files = []
            for root, dirs, filenames in os.walk(dir_path):
                for filename in filenames:
                    if not filename.startswith('.') and not filename.endswith('.pyc'):
                        rel_path = os.path.relpath(os.path.join(root, filename), dir_path)
                        files.append(rel_path)
            
            summary_parts.append(f"**Directory contains {len(files)} files**")
            summary_parts.append("")
            
            # Group by file type
            file_types = {}
            for file in files:
                ext = os.path.splitext(file)[1] or 'no extension'
                file_types.setdefault(ext, []).append(file)
            
            summary_parts.append("**File breakdown:**")
            for ext, file_list in sorted(file_types.items()):
                summary_parts.append(f"- {ext}: {len(file_list)} files")
                if len(file_list) <= 5:
                    for file in file_list:
                        summary_parts.append(f"  - {file}")
                else:
                    for file in file_list[:3]:
                        summary_parts.append(f"  - {file}")
                    summary_parts.append(f"  - ... and {len(file_list) - 3} more")
            
        except Exception as e:
            summary_parts.append(f"Error analyzing directory: {e}")
        
        return "\n".join(summary_parts)
    
    def _get_project_structure(self) -> List[str]:
        """Get high-level project structure."""
        structure = []
        
        # Look for common project files
        key_files = ['README.md', 'setup.py', 'requirements.txt', 'package.json', 'Dockerfile', 'config.json']
        found_files = [f for f in key_files if os.path.exists(f)]
        
        if found_files:
            structure.append("**Key project files:**")
            for file in found_files:
                structure.append(f"- {file}")
        
        # Main directories
        main_dirs = []
        for item in os.listdir('.'):
            if os.path.isdir(item) and not item.startswith('.') and item != '__pycache__':
                main_dirs.append(item)
        
        if main_dirs:
            structure.append("**Main directories:**")
            for dir_name in sorted(main_dirs):
                structure.append(f"- {dir_name}/")
        
        return structure
    
    def _analyze_main_components(self) -> List[str]:
        """Analyze main code components."""
        components = []
        
        # Look for Python modules in src/
        if os.path.exists('src'):
            for root, dirs, files in os.walk('src'):
                for file in files:
                    if file.endswith('.py') and file != '__init__.py':
                        rel_path = os.path.relpath(os.path.join(root, file), 'src')
                        components.append(f"- {rel_path.replace('.py', '').replace('/', '.')}")
        
        # Look for main entry points
        entry_points = ['main.py', 'app.py', 'run.py', 'index.js', 'server.js']
        for entry in entry_points:
            if os.path.exists(entry):
                components.append(f"- **{entry}** (entry point)")
        
        return components if components else ["- No clear component structure detected"]
    
    def _analyze_functionality(self) -> List[str]:
        """Analyze key functionality by examining file names and structure."""
        functionality = []
        
        # Look for functionality hints in directory/file names
        func_indicators = {
            'api': 'API/Web service functionality',
            'database': 'Database operations',
            'db': 'Database operations', 
            'models': 'Data models/schemas',
            'controllers': 'Request handling/routing',
            'services': 'Business logic services',
            'utils': 'Utility functions',
            'helpers': 'Helper functions',
            'auth': 'Authentication/authorization',
            'config': 'Configuration management',
            'tests': 'Testing framework',
            'cli': 'Command-line interface',
            'ui': 'User interface',
            'tools': 'Development tools'
        }
        
        found_functionality = []
        for root, dirs, files in os.walk('.'):
            for item in dirs + files:
                item_lower = item.lower().replace('.py', '').replace('.js', '')
                for indicator, description in func_indicators.items():
                    if indicator in item_lower and description not in found_functionality:
                        found_functionality.append(description)
        
        return found_functionality if found_functionality else ["- Functionality not clearly identifiable from structure"]
    
    def _analyze_dependencies(self) -> List[str]:
        """Analyze project dependencies."""
        deps = []
        
        # Python dependencies
        if os.path.exists('requirements.txt'):
            try:
                with open('requirements.txt', 'r') as f:
                    python_deps = [line.strip() for line in f if line.strip() and not line.startswith('#')]
                deps.append(f"**Python packages:** {len(python_deps)} dependencies")
                if python_deps:
                    deps.extend([f"- {dep}" for dep in python_deps[:5]])
                    if len(python_deps) > 5:
                        deps.append(f"- ... and {len(python_deps) - 5} more")
            except:
                deps.append("**Python packages:** requirements.txt found but not readable")
        
        # Node.js dependencies
        if os.path.exists('package.json'):
            deps.append("**Node.js project** with package.json")
        
        # Docker
        if os.path.exists('Dockerfile'):
            deps.append("**Docker** containerization")
        
        return deps if deps else ["- No clear dependency files found"]
    
    def _analyze_python_file(self, content: str, focus: str) -> List[str]:
        """Analyze a Python file's structure."""
        analysis = []
        lines = content.split('\n')
        
        # Count different elements
        imports = [line for line in lines if line.strip().startswith(('import ', 'from '))]
        classes = [line for line in lines if line.strip().startswith('class ')]
        functions = [line for line in lines if line.strip().startswith('def ')]
        
        analysis.append("**Python file analysis:**")
        analysis.append(f"- Imports: {len(imports)}")
        analysis.append(f"- Classes: {len(classes)}")
        analysis.append(f"- Functions: {len(functions)}")
        analysis.append("")
        
        if focus in ["overview", "functionality"] and (classes or functions):
            analysis.append("**Key components:**")
            for cls in classes[:3]:
                class_name = cls.strip().split()[1].split('(')[0].rstrip(':')
                analysis.append(f"- Class: {class_name}")
            for func in functions[:5]:
                func_name = func.strip().split()[1].split('(')[0]
                analysis.append(f"- Function: {func_name}")
            
            if len(classes) > 3 or len(functions) > 5:
                analysis.append("- ...")
        
        return analysis
    
    def _analyze_javascript_file(self, content: str, focus: str) -> List[str]:
        """Analyze a JavaScript/TypeScript file's structure."""
        analysis = []
        lines = content.split('\n')
        
        # Basic analysis
        imports = [line for line in lines if 'import' in line or 'require(' in line]
        functions = [line for line in lines if 'function' in line or '=>' in line]
        
        analysis.append("**JavaScript/TypeScript file analysis:**")
        analysis.append(f"- Import statements: {len(imports)}")
        analysis.append(f"- Functions/methods: {len(functions)}")
        
        return analysis


class AnalyzeCodeTool(Tool):
    """Tool for detailed code analysis and structure inspection."""
    
    @property
    def name(self) -> str:
        return "analyze_code"
    
    @property
    def description(self) -> str:
        return "Perform detailed code analysis including complexity, patterns, and potential issues. Outputs plain text analysis."
    
    @property
    def parameters_schema(self) -> Dict[str, Any]:
        return {
            "type": "object", 
            "properties": {
                "target": {
                    "type": "string",
                    "description": "File path or directory to analyze"
                },
                "analysis_type": {
                    "type": "string",
                    "enum": ["complexity", "patterns", "issues", "metrics", "all"],
                    "description": "Type of analysis to perform"
                }
            },
            "required": ["target"]
        }
    
    @property
    def is_destructive(self) -> bool:
        return False
    
    def execute(self, **parameters) -> ToolResult:
        target = parameters.get("target", ".")
        analysis_type = parameters.get("analysis_type", "all")
        
        try:
            if not os.path.exists(target):
                return ToolResult(success=False, output=None, error=f"Target '{target}' not found.")
            
            analysis_parts = []
            analysis_parts.append(f"# Code Analysis: {target}")
            analysis_parts.append("")
            
            if os.path.isfile(target):
                analysis_parts.extend(self._analyze_single_file(target, analysis_type))
            else:
                analysis_parts.extend(self._analyze_directory(target, analysis_type))
            
            output = "\n".join(analysis_parts)
            return ToolResult(success=True, output=output, action_description=f"Analyzed {target} ({analysis_type})")
        except Exception as e:
            return ToolResult(success=False, output=None, error=f"Error analyzing {target}: {str(e)}")
    
    def _analyze_single_file(self, file_path: str, analysis_type: str) -> List[str]:
        """Analyze a single file."""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
        except Exception as e:
            return [f"Error reading file: {e}"]
        
        analysis = []
        lines = content.split('\n')
        
        # Basic metrics
        if analysis_type in ["metrics", "all"]:
            analysis.append("## Metrics")
            analysis.append(f"- Lines of code: {len(lines)}")
            analysis.append(f"- Characters: {len(content)}")
            analysis.append(f"- Non-empty lines: {len([l for l in lines if l.strip()])}")
            analysis.append("")
        
        # Python-specific analysis
        if file_path.endswith('.py'):
            analysis.extend(self._analyze_python_complexity(content, analysis_type))
        
        return analysis
    
    def _analyze_directory(self, dir_path: str, analysis_type: str) -> List[str]:
        """Analyze a directory."""
        analysis = []
        
        # File statistics
        python_files = []
        total_lines = 0
        
        for root, dirs, files in os.walk(dir_path):
            for file in files:
                if file.endswith('.py'):
                    file_path = os.path.join(root, file)
                    try:
                        with open(file_path, 'r', encoding='utf-8') as f:
                            content = f.read()
                            lines = len(content.split('\n'))
                            total_lines += lines
                            python_files.append((file_path, lines))
                    except:
                        continue
        
        if analysis_type in ["metrics", "all"]:
            analysis.append("## Directory Metrics")
            analysis.append(f"- Python files: {len(python_files)}")
            analysis.append(f"- Total lines of Python code: {total_lines}")
            analysis.append("")
            
            # Largest files
            if python_files:
                python_files.sort(key=lambda x: x[1], reverse=True)
                analysis.append("**Largest files:**")
                for file_path, lines in python_files[:5]:
                    rel_path = os.path.relpath(file_path, dir_path)
                    analysis.append(f"- {rel_path}: {lines} lines")
                analysis.append("")
        
        return analysis
    
    def _analyze_python_complexity(self, content: str, analysis_type: str) -> List[str]:
        """Analyze Python code complexity."""
        analysis = []
        lines = content.split('\n')
        
        if analysis_type in ["complexity", "all"]:
            analysis.append("## Complexity Analysis")
            
            # Function/class count
            functions = [line for line in lines if line.strip().startswith('def ')]
            classes = [line for line in lines if line.strip().startswith('class ')]
            
            analysis.append(f"- Functions: {len(functions)}")
            analysis.append(f"- Classes: {len(classes)}")
            
            # Indentation depth (rough complexity measure)
            max_indent = 0
            for line in lines:
                if line.strip():
                    indent = len(line) - len(line.lstrip())
                    max_indent = max(max_indent, indent)
            
            analysis.append(f"- Maximum indentation depth: {max_indent // 4} levels")
            analysis.append("")
        
        if analysis_type in ["patterns", "all"]:
            analysis.append("## Code Patterns")
            
            # Common patterns
            imports = len([line for line in lines if line.strip().startswith(('import ', 'from '))])
            analysis.append(f"- Import statements: {imports}")
            
            # Error handling
            try_blocks = len([line for line in lines if 'try:' in line])
            except_blocks = len([line for line in lines if 'except' in line])
            analysis.append(f"- Try/except blocks: {try_blocks}/{except_blocks}")
            
            # Documentation
            docstrings = len([line for line in lines if '"""' in line or "'''" in line])
            analysis.append(f"- Docstring indicators: {docstrings}")
            analysis.append("")
        
        return analysis
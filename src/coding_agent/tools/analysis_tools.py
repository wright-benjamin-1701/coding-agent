"""Analysis and summary tools that output plain text."""

import os
import subprocess
from typing import Dict, Any, List, Optional
from .base import Tool
from ..types import ToolResult
from ..providers.base import ModelProvider


class SummarizeCodeTool(Tool):
    """Tool for generating LLM-powered summaries of codebases or files."""
    
    def __init__(self, model_provider: Optional[ModelProvider] = None):
        self.model_provider = model_provider
    
    @property
    def name(self) -> str:
        return "summarize_code"
    
    @property
    def description(self) -> str:
        return "Analyze and summarize code structure, purpose, and key components using LLM analysis. Outputs intelligent plain text summary."
    
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
            # Check if LLM is available
            if not self.model_provider or not self.model_provider.is_available():
                return ToolResult(success=False, output=None, error="LLM provider not available for intelligent code analysis")
            
            # Gather code content
            if target == "codebase":
                content = self._gather_codebase_content()
            elif os.path.isfile(target):
                content = self._gather_file_content(target)
            elif os.path.isdir(target):
                content = self._gather_directory_content(target)
            else:
                return ToolResult(success=False, output=None, error=f"Target '{target}' not found or not accessible.")
            
            # Generate LLM summary
            prompt = self._build_summary_prompt(content, target, focus)
            response = self.model_provider.generate(prompt)
            
            if not response.content.strip():
                return ToolResult(success=False, output=None, error="LLM returned empty response")
            
            return ToolResult(success=True, output=response.content.strip(), action_description=f"LLM summarized {target} with focus on {focus}")
        except Exception as e:
            return ToolResult(success=False, output=None, error=f"Error summarizing {target}: {str(e)}")
    
    def _gather_codebase_content(self) -> str:
        """Gather key codebase files for LLM analysis."""
        content_parts = []
        
        # Add project overview files
        overview_files = ['README.md', 'package.json', 'requirements.txt', 'setup.py', 'Cargo.toml']
        for file in overview_files:
            if os.path.exists(file):
                try:
                    with open(file, 'r', encoding='utf-8') as f:
                        content = f.read()[:2000]  # Limit size
                        content_parts.append(f"=== {file} ===\n{content}\n")
                except:
                    continue
        
        # Add key source files (limit to prevent context overflow)
        source_files = []
        for root, dirs, files in os.walk('.'):
            # Skip hidden and build directories
            dirs[:] = [d for d in dirs if not d.startswith('.') and d not in ['__pycache__', 'node_modules', 'target', 'build']]
            
            for file in files:
                if file.endswith(('.py', '.js', '.ts', '.rs', '.go', '.java', '.cpp', '.h')):
                    file_path = os.path.join(root, file)
                    source_files.append(file_path)
        
        # Sort by relevance (main files first, then by name)
        source_files.sort(key=lambda x: (
            0 if 'main' in os.path.basename(x).lower() else
            1 if 'app' in os.path.basename(x).lower() else
            2 if 'index' in os.path.basename(x).lower() else 3,
            x
        ))
        
        # Add top source files (limit to prevent context overflow)
        for file_path in source_files[:10]:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()[:1500]  # Limit size per file
                    content_parts.append(f"=== {file_path} ===\n{content}\n")
            except:
                continue
        
        return "\n".join(content_parts)
    
    def _gather_file_content(self, file_path: str) -> str:
        """Gather content from a specific file for LLM analysis."""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            return f"=== {file_path} ===\n{content}"
        except Exception as e:
            return f"=== {file_path} ===\nError reading file: {e}"
    
    def _gather_directory_content(self, dir_path: str) -> str:
        """Gather content from a directory for LLM analysis."""
        content_parts = []
        
        try:
            # Gather relevant files from the directory
            source_files = []
            for root, dirs, files in os.walk(dir_path):
                # Skip hidden and build directories
                dirs[:] = [d for d in dirs if not d.startswith('.') and d not in ['__pycache__', 'node_modules', 'target', 'build']]
                
                for file in files:
                    if file.endswith(('.py', '.js', '.ts', '.rs', '.go', '.java', '.cpp', '.h', '.md')):
                        file_path = os.path.join(root, file)
                        source_files.append(file_path)
            
            # Add files up to a reasonable limit
            for file_path in sorted(source_files)[:8]:
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        content = f.read()[:2000]  # Limit size per file
                        content_parts.append(f"=== {file_path} ===\n{content}\n")
                except:
                    continue
            
        except Exception as e:
            content_parts.append(f"Error reading directory {dir_path}: {e}")
        
        return "\n".join(content_parts)
    
    def _build_summary_prompt(self, content: str, target: str, focus: str) -> str:
        """Build a prompt for LLM code summarization."""
        focus_instructions = {
            "overview": "Provide a comprehensive overview including purpose, structure, and key components.",
            "architecture": "Focus on the architectural patterns, design decisions, and system structure.",
            "functionality": "Emphasize what the code does, its main features, and user-facing functionality.",
            "dependencies": "Highlight external dependencies, libraries used, and integration points."
        }
        
        focus_instruction = focus_instructions.get(focus, focus_instructions["overview"])
        
        return f"""Please analyze the following code and provide a clear, well-structured summary.

TARGET: {target}
FOCUS: {focus_instruction}

CODE CONTENT:
{content}

Please provide a markdown-formatted summary that includes:
1. **Purpose & Overview** - What this code does and why it exists
2. **Key Components** - Main files, classes, functions, or modules
3. **Architecture & Structure** - How the code is organized and key patterns used
4. **Technologies & Dependencies** - Languages, frameworks, and external dependencies
5. **Notable Features** - Important functionality, algorithms, or design decisions

Keep the summary concise but informative, suitable for developers who need to understand this codebase quickly."""


class AnalyzeCodeTool(Tool):
    """Tool for detailed LLM-powered code analysis and structure inspection."""
    
    def __init__(self, model_provider: Optional[ModelProvider] = None):
        self.model_provider = model_provider
    
    @property
    def name(self) -> str:
        return "analyze_code"
    
    @property
    def description(self) -> str:
        return "Perform detailed code analysis including complexity, patterns, and potential issues using LLM intelligence. Outputs comprehensive plain text analysis."
    
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
            # Check if LLM is available
            if not self.model_provider or not self.model_provider.is_available():
                return ToolResult(success=False, output=None, error="LLM provider not available for intelligent code analysis")
            
            # Check if target exists
            if not os.path.exists(target):
                return ToolResult(success=False, output=None, error=f"Target '{target}' not found.")
            
            # Gather code content
            if os.path.isfile(target):
                content = self._gather_file_content(target)
            else:
                content = self._gather_directory_content(target)
            
            # Generate LLM analysis
            prompt = self._build_analysis_prompt(content, target, analysis_type)
            response = self.model_provider.generate(prompt)
            
            if not response.content.strip():
                return ToolResult(success=False, output=None, error="LLM returned empty response")
            
            return ToolResult(success=True, output=response.content.strip(), action_description=f"LLM analyzed {target} ({analysis_type})")
        except Exception as e:
            return ToolResult(success=False, output=None, error=f"Error analyzing {target}: {str(e)}")
    
    def _gather_file_content(self, file_path: str) -> str:
        """Gather content from a specific file for LLM analysis."""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            return f"=== {file_path} ===\n{content}"
        except Exception as e:
            return f"=== {file_path} ===\nError reading file: {e}"
    
    def _gather_directory_content(self, dir_path: str) -> str:
        """Gather content from a directory for LLM analysis."""
        content_parts = []
        
        try:
            # Gather relevant files from the directory
            source_files = []
            for root, dirs, files in os.walk(dir_path):
                # Skip hidden and build directories
                dirs[:] = [d for d in dirs if not d.startswith('.') and d not in ['__pycache__', 'node_modules', 'target', 'build']]
                
                for file in files:
                    if file.endswith(('.py', '.js', '.ts', '.rs', '.go', '.java', '.cpp', '.h')):
                        file_path = os.path.join(root, file)
                        source_files.append(file_path)
            
            # Add files up to a reasonable limit
            for file_path in sorted(source_files)[:8]:
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        content = f.read()[:2000]  # Limit size per file
                        content_parts.append(f"=== {file_path} ===\n{content}\n")
                except:
                    continue
            
        except Exception as e:
            content_parts.append(f"Error reading directory {dir_path}: {e}")
        
        return "\n".join(content_parts)
    
    def _build_analysis_prompt(self, content: str, target: str, analysis_type: str) -> str:
        """Build a prompt for LLM code analysis."""
        analysis_instructions = {
            "complexity": "Focus on code complexity, cyclomatic complexity, nesting levels, function sizes, and maintainability concerns.",
            "patterns": "Identify design patterns, architectural patterns, code smells, anti-patterns, and coding conventions used.",
            "issues": "Look for potential bugs, security vulnerabilities, performance issues, and code quality problems.",
            "metrics": "Provide detailed metrics including lines of code, complexity scores, test coverage insights, and quantitative analysis.",
            "all": "Provide comprehensive analysis covering complexity, patterns, potential issues, and key metrics."
        }
        
        analysis_instruction = analysis_instructions.get(analysis_type, analysis_instructions["all"])
        
        return f"""Please perform a detailed code analysis of the following code.

TARGET: {target}
ANALYSIS TYPE: {analysis_type}
FOCUS: {analysis_instruction}

CODE CONTENT:
{content}

Please provide a thorough markdown-formatted analysis that includes:

1. **Code Quality Assessment** - Overall code quality, maintainability, and readability
2. **Complexity Analysis** - Cyclomatic complexity, nesting levels, function/class sizes
3. **Architecture & Patterns** - Design patterns used, architectural decisions, code organization
4. **Potential Issues** - Code smells, security concerns, performance bottlenecks, bugs
5. **Best Practices** - Adherence to coding standards, documentation quality, error handling
6. **Recommendations** - Specific suggestions for improvement and refactoring opportunities

Be specific and provide concrete examples from the code. Focus on actionable insights that would help developers improve the codebase."""
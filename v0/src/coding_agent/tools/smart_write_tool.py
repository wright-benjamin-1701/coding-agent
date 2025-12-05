"""Smart write tool that analyzes codebase for optimal placement."""

import os
import re
import ast
import json
from pathlib import Path
from typing import Dict, Any, Optional, List, Tuple
from .base import Tool
from .file_tools import SearchFilesTool, ReadFileTool
from ..types import ToolResult
from ..cache_service import CacheService

try:
    import yaml
    HAS_YAML = True
except ImportError:
    HAS_YAML = False


class SmartWriteTool(Tool):
    """Tool for writing files with intelligent placement analysis."""
    
    def __init__(self, cache_service: Optional[CacheService] = None, 
                 search_tool: Optional[SearchFilesTool] = None,
                 read_tool: Optional[ReadFileTool] = None):
        self.cache_service = cache_service
        self.search_tool = search_tool or SearchFilesTool()
        self.read_tool = read_tool or ReadFileTool(cache_service)
    
    @property
    def name(self) -> str:
        return "smart_write_file"
    
    @property
    def description(self) -> str:
        return "Intelligently write content to a file by analyzing codebase for optimal placement and integration"
    
    @property
    def parameters_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string", 
                    "description": "Path to the file to write (can be new or existing)"
                },
                "content": {
                    "type": "string", 
                    "description": "Content to write"
                },
                "content_type": {
                    "type": "string",
                    "description": "Type of content (function, class, method, config, etc.)",
                    "enum": ["function", "class", "method", "config", "import", "variable", "full_file", "other"]
                },
                "context": {
                    "type": "string",
                    "description": "Additional context about what this code should do"
                },
                "force_overwrite": {
                    "type": "boolean",
                    "description": "Skip analysis and force overwrite the entire file",
                    "default": False
                }
            },
            "required": ["file_path", "content"]
        }
    
    def is_destructive(self) -> bool:
        # Creating new files with unused filenames is not destructive
        # Only modifying existing files is destructive
        return False
    
    def is_destructive_for_params(self, **parameters) -> bool:
        """Check if this specific operation would be destructive."""
        file_path = parameters.get("file_path")
        force_overwrite = parameters.get("force_overwrite", False)
        
        if not file_path:
            return False
        
        # If force_overwrite is True, it's potentially destructive
        if force_overwrite:
            return True
        
        # If file exists, modifying it could be destructive
        return os.path.exists(file_path)
    
    def execute(self, **parameters) -> ToolResult:
        """Write content with intelligent placement."""
        file_path = parameters.get("file_path")
        content = parameters.get("content")
        content_type = parameters.get("content_type", "other")
        context = parameters.get("context", "")
        force_overwrite = parameters.get("force_overwrite", False)
        
        if not file_path or content is None:
            return ToolResult(
                success=False, 
                output=None, 
                error="Missing file_path or content parameter"
            )
        
        try:
            # If force overwrite, just write the file
            if force_overwrite:
                return self._write_file_direct(file_path, content)
            
            # Analyze for optimal placement
            analysis = self._analyze_placement(file_path, content, content_type, context)
            
            # Apply the analysis results
            if analysis["action"] == "create_new":
                return self._create_new_file(file_path, content, analysis)
            elif analysis["action"] == "integrate":
                return self._integrate_with_existing(file_path, content, analysis)
            elif analysis["action"] == "suggest_different_file":
                return self._suggest_different_file(content, analysis)
            else:
                # Fallback to direct write
                return self._write_file_direct(file_path, content)
                
        except Exception as e:
            return ToolResult(success=False, output=None, error=str(e))
    
    def _analyze_placement(self, file_path: str, content: str, content_type: str, context: str) -> Dict[str, Any]:
        """Analyze where and how to place the content."""
        analysis = {
            "action": "create_new",  # create_new, integrate, suggest_different_file
            "target_file": file_path,
            "integration_point": None,
            "existing_content": None,
            "suggestions": [],
            "reasoning": ""
        }
        
        # Check if file exists
        if not os.path.exists(file_path):
            analysis["reasoning"] = f"Creating new file: {file_path}"
            return analysis
        
        # Read existing file
        read_result = self.read_tool.execute(file_path=file_path)
        if not read_result.success:
            analysis["reasoning"] = f"Could not read existing file: {read_result.error}"
            return analysis
        
        existing_content = read_result.output
        analysis["existing_content"] = existing_content
        
        # Analyze based on content type and file type
        file_ext = Path(file_path).suffix.lower()
        
        if file_ext == ".py":
            return self._analyze_python_placement(file_path, content, content_type, context, existing_content, analysis)
        elif file_ext in [".js", ".ts"]:
            return self._analyze_javascript_placement(file_path, content, content_type, context, existing_content, analysis)
        elif file_ext in [".json", ".yaml", ".yml"]:
            return self._analyze_config_placement(file_path, content, content_type, context, existing_content, analysis)
        else:
            # For other file types, check if we should integrate or overwrite
            if len(existing_content.strip()) > 0:
                analysis["action"] = "integrate"
                analysis["integration_point"] = "append"
                analysis["reasoning"] = f"File exists, appending content to end"
            return analysis
    
    def _analyze_python_placement(self, file_path: str, content: str, content_type: str, 
                                context: str, existing_content: str, analysis: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze placement for Python files."""
        try:
            # Parse existing Python content
            existing_tree = ast.parse(existing_content)
            
            # Try to parse new content
            try:
                new_tree = ast.parse(content)
            except SyntaxError:
                # If it's not valid Python on its own, treat as code snippet
                analysis["action"] = "integrate"
                analysis["integration_point"] = self._find_python_integration_point(
                    existing_content, content, content_type
                )
                analysis["reasoning"] = "Content appears to be a code snippet, finding integration point"
                return analysis
            
            # Analyze what we're adding
            new_items = []
            for node in ast.walk(new_tree):
                if isinstance(node, ast.FunctionDef):
                    new_items.append(f"function:{node.name}")
                elif isinstance(node, ast.ClassDef):
                    new_items.append(f"class:{node.name}")
                elif isinstance(node, ast.Import):
                    new_items.append("import")
                elif isinstance(node, ast.ImportFrom):
                    new_items.append("import")
            
            # Check for conflicts with existing content
            existing_items = []
            for node in ast.walk(existing_tree):
                if isinstance(node, ast.FunctionDef):
                    existing_items.append(f"function:{node.name}")
                elif isinstance(node, ast.ClassDef):
                    existing_items.append(f"class:{node.name}")
            
            conflicts = set(new_items) & set(existing_items)
            if conflicts:
                analysis["action"] = "integrate"
                analysis["integration_point"] = "replace_conflicts"
                analysis["conflicts"] = list(conflicts)
                analysis["reasoning"] = f"Found conflicts: {conflicts}. Will replace existing items."
            else:
                analysis["action"] = "integrate"
                analysis["integration_point"] = self._find_python_integration_point(
                    existing_content, content, content_type
                )
                analysis["reasoning"] = f"Adding new items: {new_items}"
            
        except SyntaxError:
            # If existing content isn't valid Python, suggest overwrite
            analysis["action"] = "create_new"
            analysis["reasoning"] = "Existing file contains invalid Python, overwriting"
        
        return analysis
    
    def _find_python_integration_point(self, existing_content: str, new_content: str, content_type: str) -> str:
        """Find the best place to integrate new Python content."""
        lines = existing_content.split('\n')
        
        # For imports, add after existing imports
        if content_type == "import" or "import " in new_content:
            for i, line in enumerate(lines):
                if line.strip() and not (line.startswith("import ") or line.startswith("from ")):
                    return f"line:{i}"
            return "beginning"
        
        # For classes, add at end but before if __name__ == "__main__"
        if content_type == "class" or "class " in new_content:
            for i in range(len(lines) - 1, -1, -1):
                if 'if __name__ == "__main__"' in lines[i]:
                    return f"line:{i}"
            return "end"
        
        # For functions, add at end but before if __name__ == "__main__"
        if content_type == "function" or "def " in new_content:
            for i in range(len(lines) - 1, -1, -1):
                if 'if __name__ == "__main__"' in lines[i]:
                    return f"line:{i}"
            return "end"
        
        # Default to end
        return "end"
    
    def _analyze_javascript_placement(self, file_path: str, content: str, content_type: str,
                                   context: str, existing_content: str, analysis: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze placement for JavaScript/TypeScript files."""
        # Simple analysis for JS/TS files
        if content_type == "function" and "function " in content:
            analysis["action"] = "integrate"
            analysis["integration_point"] = "end"
            analysis["reasoning"] = "Adding function to end of file"
        elif content_type == "import" and ("import " in content or "require(" in content):
            analysis["action"] = "integrate"
            analysis["integration_point"] = "beginning"
            analysis["reasoning"] = "Adding imports to beginning of file"
        else:
            analysis["action"] = "integrate"
            analysis["integration_point"] = "end"
            analysis["reasoning"] = "Adding content to end of file"
        
        return analysis
    
    def _analyze_config_placement(self, file_path: str, content: str, content_type: str,
                                context: str, existing_content: str, analysis: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze placement for configuration files."""
        
        file_ext = Path(file_path).suffix.lower()
        
        try:
            if file_ext == ".json":
                existing_data = json.loads(existing_content)
                try:
                    new_data = json.loads(content)
                    # Merge JSON objects
                    if isinstance(existing_data, dict) and isinstance(new_data, dict):
                        analysis["action"] = "integrate"
                        analysis["integration_point"] = "merge_json"
                        analysis["reasoning"] = "Merging JSON objects"
                    else:
                        analysis["action"] = "create_new"
                        analysis["reasoning"] = "JSON data types don't match, overwriting"
                except json.JSONDecodeError:
                    analysis["action"] = "create_new"
                    analysis["reasoning"] = "New content is not valid JSON, overwriting"
            elif file_ext in [".yaml", ".yml"]:
                if not HAS_YAML:
                    analysis["action"] = "create_new"
                    analysis["reasoning"] = "PyYAML not available, overwriting YAML file"
                else:
                    existing_data = yaml.safe_load(existing_content)
                    try:
                        new_data = yaml.safe_load(content)
                        if isinstance(existing_data, dict) and isinstance(new_data, dict):
                            analysis["action"] = "integrate"
                            analysis["integration_point"] = "merge_yaml"
                            analysis["reasoning"] = "Merging YAML objects"
                        else:
                            analysis["action"] = "create_new"
                            analysis["reasoning"] = "YAML data types don't match, overwriting"
                    except yaml.YAMLError:
                        analysis["action"] = "create_new"
                        analysis["reasoning"] = "New content is not valid YAML, overwriting"
        except Exception:
            # If we can't parse existing content, overwrite
            analysis["action"] = "create_new"
            analysis["reasoning"] = "Could not parse existing configuration file, overwriting"
        
        return analysis
    
    def _create_new_file(self, file_path: str, content: str, analysis: Dict[str, Any]) -> ToolResult:
        """Create a new file or overwrite existing one."""
        return self._write_file_direct(file_path, content)
    
    def _integrate_with_existing(self, file_path: str, content: str, analysis: Dict[str, Any]) -> ToolResult:
        """Integrate new content with existing file."""
        existing_content = analysis["existing_content"]
        integration_point = analysis["integration_point"]
        
        try:
            if integration_point == "beginning":
                new_content = content + "\n" + existing_content
            elif integration_point == "end":
                new_content = existing_content + "\n" + content
            elif integration_point == "append":
                new_content = existing_content + "\n" + content
            elif integration_point.startswith("line:"):
                line_num = int(integration_point.split(":")[1])
                lines = existing_content.split('\n')
                lines.insert(line_num, content)
                new_content = '\n'.join(lines)
            elif integration_point == "merge_json":
                existing_data = json.loads(existing_content)
                new_data = json.loads(content)
                existing_data.update(new_data)
                new_content = json.dumps(existing_data, indent=2)
            elif integration_point == "merge_yaml":
                if HAS_YAML:
                    existing_data = yaml.safe_load(existing_content)
                    new_data = yaml.safe_load(content)
                    existing_data.update(new_data)
                    new_content = yaml.dump(existing_data, default_flow_style=False)
                else:
                    # Fallback to simple append if YAML not available
                    new_content = existing_content + "\n" + content
            elif integration_point == "replace_conflicts":
                # For Python files, replace conflicting functions/classes
                new_content = self._replace_python_conflicts(existing_content, content, analysis.get("conflicts", []))
            else:
                # Default to append
                new_content = existing_content + "\n" + content
            
            return self._write_file_direct(file_path, new_content)
            
        except Exception as e:
            return ToolResult(
                success=False,
                output=None,
                error=f"Integration failed: {str(e)}"
            )
    
    def _replace_python_conflicts(self, existing_content: str, new_content: str, conflicts: List[str]) -> str:
        """Replace conflicting Python functions/classes."""
        # This is a simplified implementation
        # In practice, you'd want more sophisticated AST manipulation
        lines = existing_content.split('\n')
        new_lines = []
        skip_until_dedent = False
        current_indent = 0
        
        for line in lines:
            # Check if this line starts a conflicting item
            line_stripped = line.strip()
            should_skip = False
            
            for conflict in conflicts:
                if conflict.startswith("function:"):
                    func_name = conflict.split(":")[1]
                    if line_stripped.startswith(f"def {func_name}("):
                        should_skip = True
                        current_indent = len(line) - len(line.lstrip())
                        skip_until_dedent = True
                        break
                elif conflict.startswith("class:"):
                    class_name = conflict.split(":")[1]
                    if line_stripped.startswith(f"class {class_name}"):
                        should_skip = True
                        current_indent = len(line) - len(line.lstrip())
                        skip_until_dedent = True
                        break
            
            if skip_until_dedent:
                if line.strip() == "":
                    continue  # Skip empty lines
                line_indent = len(line) - len(line.lstrip())
                if line_indent <= current_indent and line.strip():
                    skip_until_dedent = False
                    # Don't skip this line, it's at the same or less indent
                    new_lines.append(line)
                # else: skip this line as it's part of the conflicting item
            elif not should_skip:
                new_lines.append(line)
        
        # Add the new content
        result = '\n'.join(new_lines) + '\n' + new_content
        return result
    
    def _suggest_different_file(self, content: str, analysis: Dict[str, Any]) -> ToolResult:
        """Suggest a different file for the content."""
        suggestions = analysis.get("suggestions", [])
        suggestion_text = "\n".join([f"  - {s}" for s in suggestions])
        
        return ToolResult(
            success=False,
            output=None,
            error=f"Content might be better placed elsewhere. Suggestions:\n{suggestion_text}\n\nUse force_overwrite=true to override this analysis."
        )
    
    def _write_file_direct(self, file_path: str, content: str) -> ToolResult:
        """Write content directly to file."""
        try:
            # Create directories if needed
            dir_path = os.path.dirname(file_path)
            if dir_path:
                os.makedirs(dir_path, exist_ok=True)
            
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)
            
            return ToolResult(
                success=True, 
                output=f"File written: {file_path}",
                action_description=f"Wrote {file_path}"
            )
        except Exception as e:
            return ToolResult(
                success=False, 
                output=None, 
                error=str(e)
            )
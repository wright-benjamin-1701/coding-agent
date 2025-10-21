"""File operation tools."""

import os
import subprocess
from pathlib import Path
from typing import Dict, Any, Optional
from .base import Tool
from ..types import ToolResult
from ..cache_service import CacheService


class ReadFileTool(Tool):
    """Tool for reading files with caching support."""
    
    def __init__(self, cache_service: Optional[CacheService] = None):
        self.cache_service = cache_service
    
    @property
    def name(self) -> str:
        return "read_file"
    
    @property
    def description(self) -> str:
        return "Read contents of a file"
    
    @property
    def parameters_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "file_path": {"type": "string", "description": "Path to the file to read"}
            },
            "required": ["file_path"]
        }
    
    @property
    def is_destructive(self) -> bool:
        return False
    
    def execute(self, **parameters) -> ToolResult:
        """Read a file with caching support."""
        file_path = parameters.get("file_path")
        
        if not file_path:
            return ToolResult(success=False, output=None, error="Missing file_path parameter")
        
        try:
            # Try cache first if available
            if self.cache_service:
                cached_result = self.cache_service.read_file_cached(file_path)
                if cached_result:
                    content = cached_result["content"]
                    cache_note = " (cached)" if cached_result else ""
                    return ToolResult(success=True, output=content, 
                                    action_description=f"Read {file_path}{cache_note}")
            
            # Fallback to direct file read
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            return ToolResult(success=True, output=content, action_description=f"Read {file_path}")
        except Exception as e:
            return ToolResult(success=False, output=None, error=str(e))


class WriteFileTool(Tool):
    """Tool for writing files."""
    
    @property
    def name(self) -> str:
        return "write_file"
    
    @property
    def description(self) -> str:
        return "Write content to a file"
    
    @property
    def parameters_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "file_path": {"type": "string", "description": "Path to the file to write"},
                "content": {"type": "string", "description": "Content to write to the file"}
            },
            "required": ["file_path", "content"]
        }
    
    @property
    def is_destructive(self) -> bool:
        return True  # Writing files requires confirmation
    
    def execute(self, **parameters) -> ToolResult:
        """Write to a file."""
        file_path = parameters.get("file_path")
        content = parameters.get("content")
        
        if not file_path or content is None:
            return ToolResult(success=False, output=None, error="Missing file_path or content parameter")
        
        try:
            # Smart path resolution: look for project context
            resolved_path = self._resolve_project_path(file_path)
            
            # Only create directories if the file path contains a directory
            dir_path = os.path.dirname(resolved_path)
            if dir_path:
                os.makedirs(dir_path, exist_ok=True)
            
            with open(resolved_path, 'w', encoding='utf-8') as f:
                f.write(content)
            return ToolResult(success=True, output=f"File written: {resolved_path}", action_description=f"Wrote {resolved_path}")
        except Exception as e:
            return ToolResult(success=False, output=None, error=str(e))
    
    def _resolve_project_path(self, file_path: str) -> str:
        """Resolve file path, checking for recent project directories."""
        # If path is already absolute, use as-is
        if os.path.isabs(file_path):
            return file_path
        
        # Look for recently created project directories first
        current_dir = os.getcwd()
        potential_projects = []
        
        try:
            for item in os.listdir(current_dir):
                item_path = os.path.join(current_dir, item)
                if os.path.isdir(item_path):
                    # Check if this looks like a recently created project
                    if any(os.path.exists(os.path.join(item_path, f)) for f in ['package.json', 'tsconfig.json', 'vite.config.ts']):
                        potential_projects.append(item)
            
            # Sort by modification time (most recent first)
            potential_projects.sort(key=lambda p: os.path.getmtime(os.path.join(current_dir, p)), reverse=True)
            
            # If we find potential projects, check if the file path makes sense relative to them
            for project in potential_projects:
                candidate_path = os.path.join(current_dir, project, file_path)
                candidate_dir = os.path.dirname(candidate_path)
                
                # Check if this could be a valid project file path
                if file_path.startswith('src/') and os.path.exists(os.path.join(current_dir, project, 'src')):
                    return candidate_path
                elif os.path.exists(candidate_dir):
                    return candidate_path
                    
        except Exception:
            pass  # If directory scanning fails, fall back to checking current dir
        
        # If the relative path exists from current directory, use it
        if os.path.exists(file_path) or os.path.exists(os.path.dirname(file_path)):
            return file_path
        
        # Return original path as fallback
        return file_path


class SearchFilesTool(Tool):
    """Tool for searching files using ripgrep."""
    
    @property
    def name(self) -> str:
        return "search_files"
    
    @property
    def description(self) -> str:
        return "Search for text in files using ripgrep"
    
    @property
    def parameters_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "pattern": {"type": "string", "description": "Search pattern"},
                "path": {"type": "string", "description": "Path to search in", "default": "."},
                "file_type": {"type": "string", "description": "File type filter (e.g., py, js)"}
            },
            "required": ["pattern"]
        }
    
    @property
    def is_destructive(self) -> bool:
        return False
    
    def execute(self, **parameters) -> ToolResult:
        """Search files with multiple fallback methods."""
        # Handle parameter variations from LLM
        pattern = (parameters.get("pattern") or 
                  parameters.get("search_term") or 
                  parameters.get("query") or
                  parameters.get("text"))
        
        path = (parameters.get("path") or 
                parameters.get("directory") or 
                parameters.get("folder") or ".")
        
        file_type = parameters.get("file_type")
        
        if not pattern:
            return ToolResult(success=False, output=None, error="Missing search pattern parameter")
        
        # Try ripgrep first, then fallback to Python search (more reliable)
        try:
            return self._search_with_ripgrep(pattern, path, file_type)
        except FileNotFoundError:
            # Ripgrep not available, use Python-based search as it's more reliable
            return self._search_with_python(pattern, path, file_type)
    
    def _search_with_ripgrep(self, pattern: str, path: str, file_type: str = None) -> ToolResult:
        """Search using ripgrep."""
        cmd = ["rg", pattern, path, "-n", "--heading"]
        if file_type:
            cmd.extend(["-t", file_type])
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode == 0:
            lines = result.stdout.strip().split('\n')
            if len(lines) > 50:
                output = '\n'.join(lines[:50]) + f'\n... ({len(lines) - 50} more results truncated)'
            else:
                output = result.stdout.strip()
            
            match_count = len([line for line in lines if ':' in line and not line.endswith(':')])
            return ToolResult(
                success=True, 
                output=output, 
                action_description=f"Found {match_count} matches for '{pattern}' in {path}"
            )
        elif result.returncode == 1:
            return ToolResult(
                success=True, 
                output=f"No matches found for '{pattern}' in {path}",
                action_description=f"Searched for '{pattern}' in {path} - no matches"
            )
        else:
            raise Exception(f"Ripgrep failed: {result.stderr}")
    
    def _search_with_system_tools(self, pattern: str, path: str, file_type: str = None) -> ToolResult:
        """Search using system grep/findstr."""
        import platform
        
        if platform.system() == "Windows":
            # Use findstr on Windows - need to handle paths differently
            if file_type:
                file_pattern = f"*.{file_type}"
            else:
                file_pattern = "*.py"  # Default to Python files
            
            # Use absolute path approach for Windows
            abs_path = os.path.abspath(path)
            if file_type:
                search_pattern = os.path.join(abs_path, f"*.{file_type}")
            else:
                search_pattern = os.path.join(abs_path, "*.py")
            
            # Use shell=True to handle Windows paths properly
            cmd_str = f'findstr /S /N "{pattern}" "{search_pattern}"'
            result = subprocess.run(cmd_str, shell=True, capture_output=True, text=True)
            return self._process_findstr_result(result, pattern, path)
        else:
            # Use grep on Unix-like systems
            cmd = ["grep", "-r", "-n", pattern, path]
            if file_type:
                cmd.extend(["--include", f"*.{file_type}"])
            
            result = subprocess.run(cmd, capture_output=True, text=True)
            return self._process_grep_result(result, pattern, path)
    
    def _process_findstr_result(self, result, pattern: str, path: str) -> ToolResult:
        """Process findstr command result."""
        if result.returncode == 0:
            lines = result.stdout.strip().split('\n')
            if len(lines) > 50:
                output = '\n'.join(lines[:50]) + f'\n... ({len(lines) - 50} more results truncated)'
            else:
                output = result.stdout.strip()
            
            match_count = len(lines)
            return ToolResult(
                success=True, 
                output=output, 
                action_description=f"Found {match_count} matches for '{pattern}' in {path}"
            )
        else:
            return ToolResult(
                success=True, 
                output=f"No matches found for '{pattern}' in {path}",
                action_description=f"Searched for '{pattern}' in {path} - no matches"
            )
    
    def _process_grep_result(self, result, pattern: str, path: str) -> ToolResult:
        """Process grep command result."""
        if result.returncode == 0:
            lines = result.stdout.strip().split('\n')
            if len(lines) > 50:
                output = '\n'.join(lines[:50]) + f'\n... ({len(lines) - 50} more results truncated)'
            else:
                output = result.stdout.strip()
            
            match_count = len(lines)
            return ToolResult(
                success=True, 
                output=output, 
                action_description=f"Found {match_count} matches for '{pattern}' in {path}"
            )
        else:
            return ToolResult(
                success=True, 
                output=f"No matches found for '{pattern}' in {path}",
                action_description=f"Searched for '{pattern}' in {path} - no matches"
            )
    
    def _search_with_python(self, pattern: str, path: str, file_type: str = None) -> ToolResult:
        """Fallback Python-based search."""
        import re
        from pathlib import Path
        
        matches = []
        try:
            search_pattern = re.compile(pattern, re.IGNORECASE)
        except re.error:
            # If pattern is not a valid regex, treat as literal string
            search_pattern = re.compile(re.escape(pattern), re.IGNORECASE)
        
        try:
            path_obj = Path(path)
            if not path_obj.exists():
                return ToolResult(
                    success=False, 
                    output=None, 
                    error=f"Path does not exist: {path}"
                )
            
            # Get file extension filter
            extensions = [f".{file_type}"] if file_type else [".py", ".js", ".ts", ".java", ".cpp", ".c", ".h", ".txt", ".md", ".json", ".yaml", ".yml"]
            
            for file_path in path_obj.rglob("*"):
                if file_path.is_file() and file_path.suffix in extensions:
                    try:
                        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                            for line_num, line in enumerate(f, 1):
                                if search_pattern.search(line):
                                    rel_path = file_path.relative_to(Path.cwd()) if path_obj.is_absolute() else file_path
                                    matches.append(f"{rel_path}:{line_num}:{line.strip()}")
                                    if len(matches) >= 100:  # Limit results
                                        break
                    except Exception:
                        continue  # Skip files that can't be read
                
                if len(matches) >= 100:
                    break
            
            if matches:
                output = '\n'.join(matches)
                if len(matches) >= 100:
                    output += "\n... (results limited to 100 matches)"
                
                return ToolResult(
                    success=True, 
                    output=output, 
                    action_description=f"Found {len(matches)} matches for '{pattern}' in {path}"
                )
            else:
                return ToolResult(
                    success=True, 
                    output=f"No matches found for '{pattern}' in {path}",
                    action_description=f"Searched for '{pattern}' in {path} - no matches"
                )
        
        except Exception as e:
            return ToolResult(
                success=False, 
                output=None, 
                error=f"Python search failed: {str(e)}"
            )
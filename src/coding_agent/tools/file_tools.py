"""File operation tools."""

import os
import subprocess
from pathlib import Path
from typing import Dict, Any
from .base import Tool
from ..types import ToolResult


class ReadFileTool(Tool):
    """Tool for reading files."""
    
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
        """Read a file."""
        file_path = parameters.get("file_path")
        
        if not file_path:
            return ToolResult(success=False, output=None, error="Missing file_path parameter")
        
        try:
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
        return True
    
    def execute(self, **parameters) -> ToolResult:
        """Write to a file."""
        file_path = parameters.get("file_path")
        content = parameters.get("content")
        
        if not file_path or content is None:
            return ToolResult(success=False, output=None, error="Missing file_path or content parameter")
        
        try:
            # Only create directories if the file path contains a directory
            dir_path = os.path.dirname(file_path)
            if dir_path:
                os.makedirs(dir_path, exist_ok=True)
            
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)
            return ToolResult(success=True, output=f"File written: {file_path}", action_description=f"Wrote {file_path}")
        except Exception as e:
            return ToolResult(success=False, output=None, error=str(e))


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
        """Search files with ripgrep."""
        pattern = parameters.get("pattern")
        path = parameters.get("path", ".")
        file_type = parameters.get("file_type")
        
        if not pattern:
            return ToolResult(success=False, output=None, error="Missing pattern parameter")
        
        try:
            cmd = ["rg", pattern, path, "--json"]
            if file_type:
                cmd.extend(["-t", file_type])
            
            result = subprocess.run(cmd, capture_output=True, text=True)
            return ToolResult(success=True, output=result.stdout, action_description=f"Searched for '{pattern}' in {path}")
        except Exception as e:
            return ToolResult(success=False, output=None, error=str(e))
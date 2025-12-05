"""Git operation tools."""

import subprocess
from typing import Dict, Any
from .base import Tool
from ..types import ToolResult


class GitStatusTool(Tool):
    """Tool for getting git status."""
    
    @property
    def name(self) -> str:
        return "git_status"
    
    @property
    def description(self) -> str:
        return "Get git repository status"
    
    @property
    def parameters_schema(self) -> Dict[str, Any]:
        return {"type": "object", "properties": {}}
    
    @property
    def is_destructive(self) -> bool:
        return False
    
    def execute(self) -> ToolResult:
        """Get git status."""
        try:
            result = subprocess.run(["git", "status", "--porcelain"], 
                                  capture_output=True, text=True)
            return ToolResult(success=True, output=result.stdout)
        except Exception as e:
            return ToolResult(success=False, output=None, error=str(e))


class GitDiffTool(Tool):
    """Tool for getting git diff."""
    
    @property
    def name(self) -> str:
        return "git_diff"
    
    @property
    def description(self) -> str:
        return "Get git diff for changes"
    
    @property
    def parameters_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "file_path": {"type": "string", "description": "Specific file to diff"}
            }
        }
    
    @property
    def is_destructive(self) -> bool:
        return False
    
    def execute(self, file_path: str = None) -> ToolResult:
        """Get git diff."""
        try:
            cmd = ["git", "diff"]
            if file_path:
                cmd.append(file_path)
            
            result = subprocess.run(cmd, capture_output=True, text=True)
            return ToolResult(success=True, output=result.stdout)
        except Exception as e:
            return ToolResult(success=False, output=None, error=str(e))


class GitCommitHashTool(Tool):
    """Tool for getting current commit hash."""
    
    @property
    def name(self) -> str:
        return "git_commit_hash"
    
    @property
    def description(self) -> str:
        return "Get current git commit hash"
    
    @property
    def parameters_schema(self) -> Dict[str, Any]:
        return {"type": "object", "properties": {}}
    
    @property
    def is_destructive(self) -> bool:
        return False
    
    def execute(self) -> ToolResult:
        """Get current commit hash."""
        try:
            result = subprocess.run(["git", "rev-parse", "HEAD"], 
                                  capture_output=True, text=True)
            return ToolResult(success=True, output=result.stdout.strip())
        except Exception as e:
            return ToolResult(success=False, output=None, error=str(e))
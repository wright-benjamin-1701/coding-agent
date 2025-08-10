"""Directory management tools."""

import os
import shutil
from pathlib import Path
from typing import Dict, Any
from .base import Tool
from ..types import ToolResult


class CreateDirectoryTool(Tool):
    """Tool for creating directories."""
    
    @property
    def name(self) -> str:
        return "create_directory"
    
    @property
    def description(self) -> str:
        return "Create a new directory or nested directory structure"
    
    @property
    def parameters_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Path of the directory to create"
                },
                "parents": {
                    "type": "boolean",
                    "description": "Create parent directories if they don't exist (default: True)",
                    "default": True
                }
            },
            "required": ["path"]
        }
    
    @property
    def is_destructive(self) -> bool:
        return False  # Creating directories is not destructive
    
    def execute(self, **parameters) -> ToolResult:
        """Create a directory."""
        path = parameters.get("path")
        parents = parameters.get("parents", True)
        
        if not path:
            return ToolResult(
                success=False,
                output=None,
                error="Missing path parameter"
            )
        
        try:
            os.makedirs(path, exist_ok=True)
            return ToolResult(
                success=True,
                output=f"Directory created: {path}",
                action_description=f"Created directory {path}"
            )
        except Exception as e:
            return ToolResult(
                success=False,
                output=None,
                error=str(e)
            )


class RemoveDirectoryTool(Tool):
    """Tool for removing directories."""
    
    @property
    def name(self) -> str:
        return "remove_directory"
    
    @property
    def description(self) -> str:
        return "Remove a directory and its contents"
    
    @property
    def parameters_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Path of the directory to remove"
                },
                "force": {
                    "type": "boolean",
                    "description": "Force removal even if directory is not empty (default: False)",
                    "default": False
                }
            },
            "required": ["path"]
        }
    
    @property
    def is_destructive(self) -> bool:
        return True
    
    def execute(self, **parameters) -> ToolResult:
        """Remove a directory."""
        path = parameters.get("path")
        force = parameters.get("force", False)
        
        if not path:
            return ToolResult(
                success=False,
                output=None,
                error="Missing path parameter"
            )
        
        if not os.path.exists(path):
            return ToolResult(
                success=False,
                output=None,
                error=f"Directory not found: {path}"
            )
        
        try:
            if force:
                shutil.rmtree(path)
            else:
                os.rmdir(path)  # Only removes empty directories
            
            return ToolResult(
                success=True,
                output=f"Directory removed: {path}",
                action_description=f"Removed directory {path}"
            )
        except Exception as e:
            return ToolResult(
                success=False,
                output=None,
                error=str(e)
            )


class ListDirectoryTool(Tool):
    """Tool for listing directory contents."""
    
    @property
    def name(self) -> str:
        return "list_directory"
    
    @property
    def description(self) -> str:
        return "List contents of a directory"
    
    @property
    def parameters_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Path of the directory to list",
                    "default": "."
                },
                "show_hidden": {
                    "type": "boolean",
                    "description": "Include hidden files and directories",
                    "default": False
                },
                "details": {
                    "type": "boolean",
                    "description": "Show detailed information (size, permissions, etc.)",
                    "default": False
                }
            }
        }
    
    @property
    def is_destructive(self) -> bool:
        return False
    
    def execute(self, **parameters) -> ToolResult:
        """List directory contents."""
        path = parameters.get("path", ".")
        show_hidden = parameters.get("show_hidden", False)
        details = parameters.get("details", False)
        
        if not os.path.exists(path):
            return ToolResult(
                success=False,
                output=None,
                error=f"Directory not found: {path}"
            )
        
        if not os.path.isdir(path):
            return ToolResult(
                success=False,
                output=None,
                error=f"Path is not a directory: {path}"
            )
        
        try:
            items = []
            for item in os.listdir(path):
                if not show_hidden and item.startswith('.'):
                    continue
                
                item_path = os.path.join(path, item)
                if details:
                    stat = os.stat(item_path)
                    item_type = "DIR" if os.path.isdir(item_path) else "FILE"
                    size = stat.st_size if os.path.isfile(item_path) else "-"
                    items.append(f"{item_type:4} {size:>10} {item}")
                else:
                    items.append(item)
            
            if not items:
                output = f"Directory {path} is empty"
            else:
                items.sort()
                if details:
                    output = f"Contents of {path}:\nTYPE       SIZE NAME\n" + "\n".join(items)
                else:
                    output = f"Contents of {path}:\n" + "\n".join(items)
            
            return ToolResult(
                success=True,
                output=output,
                action_description=f"Listed directory {path}"
            )
        except Exception as e:
            return ToolResult(
                success=False,
                output=None,
                error=str(e)
            )
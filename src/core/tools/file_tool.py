"""
File system operations tool
"""
import os
import aiofiles
from pathlib import Path
from typing import Dict, List, Optional, Any
from .base import BaseTool, ToolParameter, ToolResult


class FileTool(BaseTool):
    """Tool for file system operations"""
    
    def get_description(self) -> str:
        return "Read, write, and manipulate files in the project directory"
    
    def get_parameters(self) -> List[ToolParameter]:
        return [
            ToolParameter(
                name="action",
                type="string",
                description="Action to perform: read, write, list, exists, delete",
                required=True
            ),
            ToolParameter(
                name="path",
                type="string", 
                description="File or directory path",
                required=True
            ),
            ToolParameter(
                name="content",
                type="string",
                description="Content to write (for write action)",
                required=False
            ),
            ToolParameter(
                name="encoding",
                type="string",
                description="File encoding (default: utf-8)",
                required=False,
                default="utf-8"
            )
        ]
    
    async def execute(self, **kwargs) -> ToolResult:
        """Execute file operation"""
        if not self.validate_parameters(kwargs):
            return ToolResult(success=False, error="Invalid parameters")
        
        action = kwargs.get("action")
        path = kwargs.get("path")
        content = kwargs.get("content")
        encoding = kwargs.get("encoding", "utf-8")
        
        try:
            if action == "read":
                return await self._read_file(path, encoding)
            elif action == "write":
                return await self._write_file(path, content, encoding)
            elif action == "list":
                return await self._list_directory(path)
            elif action == "exists":
                return await self._check_exists(path)
            elif action == "delete":
                return await self._delete_file(path)
            else:
                return ToolResult(success=False, error=f"Unknown action: {action}")
        
        except Exception as e:
            return ToolResult(success=False, error=str(e))
    
    async def _read_file(self, path: str, encoding: str) -> ToolResult:
        """Read file content"""
        file_path = Path(path)
        
        if not file_path.exists():
            return ToolResult(success=False, error=f"File not found: {path}")
        
        if not file_path.is_file():
            return ToolResult(success=False, error=f"Path is not a file: {path}")
        
        try:
            async with aiofiles.open(file_path, 'r', encoding=encoding) as f:
                content = await f.read()
            
            return ToolResult(
                success=True,
                content=content,
                data={
                    "path": str(file_path),
                    "size": file_path.stat().st_size,
                    "encoding": encoding
                }
            )
        except UnicodeDecodeError:
            return ToolResult(success=False, error=f"Cannot decode file with {encoding} encoding")
    
    async def _write_file(self, path: str, content: str, encoding: str) -> ToolResult:
        """Write content to file"""
        if not content:
            return ToolResult(success=False, error="Content cannot be empty. Please provide content for the file.")
        
        file_path = Path(path)
        
        # Create parent directories if they don't exist
        file_path.parent.mkdir(parents=True, exist_ok=True)
        
        async with aiofiles.open(file_path, 'w', encoding=encoding) as f:
            await f.write(content)
        
        return ToolResult(
            success=True,
            content=f"File written successfully: {path}",
            data={
                "path": str(file_path),
                "size": len(content.encode(encoding)),
                "encoding": encoding
            }
        )
    
    async def _list_directory(self, path: str) -> ToolResult:
        """List directory contents"""
        dir_path = Path(path)
        
        if not dir_path.exists():
            return ToolResult(success=False, error=f"Directory not found: {path}")
        
        if not dir_path.is_dir():
            return ToolResult(success=False, error=f"Path is not a directory: {path}")
        
        items = []
        for item in dir_path.iterdir():
            items.append({
                "name": item.name,
                "type": "directory" if item.is_dir() else "file",
                "size": item.stat().st_size if item.is_file() else None,
                "path": str(item)
            })
        
        items.sort(key=lambda x: (x["type"], x["name"]))
        
        return ToolResult(
            success=True,
            data={
                "path": str(dir_path),
                "items": items,
                "count": len(items)
            }
        )
    
    async def _check_exists(self, path: str) -> ToolResult:
        """Check if path exists"""
        file_path = Path(path)
        exists = file_path.exists()
        
        data = {
            "path": str(file_path),
            "exists": exists
        }
        
        if exists:
            data.update({
                "type": "directory" if file_path.is_dir() else "file",
                "size": file_path.stat().st_size if file_path.is_file() else None
            })
        
        return ToolResult(
            success=True,
            content=f"Path {'exists' if exists else 'does not exist'}: {path}",
            data=data
        )
    
    async def _delete_file(self, path: str) -> ToolResult:
        """Delete file or directory"""
        file_path = Path(path)
        
        if not file_path.exists():
            return ToolResult(success=False, error=f"Path not found: {path}")
        
        if file_path.is_file():
            file_path.unlink()
            return ToolResult(success=True, content=f"File deleted: {path}")
        elif file_path.is_dir():
            # Only delete empty directories for safety
            try:
                file_path.rmdir()
                return ToolResult(success=True, content=f"Directory deleted: {path}")
            except OSError:
                return ToolResult(success=False, error=f"Directory not empty: {path}")
        
        return ToolResult(success=False, error=f"Cannot delete: {path}")
    
    def get_capabilities(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "description": self.get_description(),
            "async": True,
            "safe": False,  # File operations can be destructive
            "categories": ["filesystem", "io"]
        }
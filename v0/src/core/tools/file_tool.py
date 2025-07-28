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
                description="Action to perform: read, read_multiple, write, list, exists, delete",
                required=True
            ),
            ToolParameter(
                name="path",
                type="string", 
                description="File or directory path",
                required=False
            ),
            ToolParameter(
                name="paths",
                type="array",
                description="List of file paths (for read_multiple action)",
                required=False
            ),
            ToolParameter(
                name="max_files",
                type="number",
                description="Maximum number of files to read (for read_multiple action)",
                required=False,
                default=5
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
        action = kwargs.get("action")
        
        # Custom parameter validation since path is not always required
        if not action:
            return ToolResult(success=False, error="Action parameter is required")
        
        # Check required parameters based on action
        if action in ["read", "write", "list", "exists", "delete"] and not kwargs.get("path"):
            return ToolResult(success=False, error=f"Path parameter is required for {action} action")
        
        if action == "read_multiple" and not kwargs.get("paths"):
            return ToolResult(success=False, error="Paths parameter is required for read_multiple action")
        
        path = kwargs.get("path")
        content = kwargs.get("content")
        encoding = kwargs.get("encoding", "utf-8")
        
        try:
            if action == "read":
                return await self._read_file(path, encoding)
            elif action == "read_multiple":
                return await self._read_multiple_files(kwargs.get("paths", []), kwargs.get("max_files", 5), encoding)
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
    
    async def _read_multiple_files(self, paths, max_files: int, encoding: str) -> ToolResult:
        """Read multiple files and combine their content"""
        
        # Handle template substitution if paths is a string template
        if isinstance(paths, str) and paths.startswith("{{") and paths.endswith("}}"):
            # This will be resolved by the orchestrator during execution
            return ToolResult(success=False, error=f"Template not resolved: {paths}")
        
        # Ensure paths is a list
        if isinstance(paths, str):
            paths = [paths]
        elif not isinstance(paths, list):
            paths = []
        
        if not paths:
            return ToolResult(success=False, error="No file paths provided")
        
        # Limit number of files
        paths = paths[:max_files]
        
        file_contents = {}
        files_read = 0
        total_content = ""
        
        for file_path in paths:
            if files_read >= max_files:
                break
                
            try:
                path_obj = Path(file_path)
                
                if not path_obj.exists():
                    continue
                
                if not path_obj.is_file():
                    continue
                
                # Read file content
                async with aiofiles.open(path_obj, 'r', encoding=encoding) as f:
                    content = await f.read()
                
                # Truncate very long files
                if len(content) > 10000:  # 10KB limit per file
                    content = content[:10000] + "\n... [TRUNCATED]"
                
                file_contents[str(path_obj)] = content
                total_content += f"\n\n=== FILE: {path_obj} ===\n{content}\n"
                files_read += 1
                
            except (UnicodeDecodeError, PermissionError, OSError):
                # Skip files that can't be read
                continue
        
        if files_read == 0:
            return ToolResult(success=False, error="No files could be read")
        
        return ToolResult(
            success=True,
            content=total_content,
            data={
                "files_read": files_read,
                "file_contents": file_contents,
                "total_files_attempted": len(paths)
            }
        )
    
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
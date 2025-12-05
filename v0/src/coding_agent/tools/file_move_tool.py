"""File movement tool with automatic import updating."""

import os
import ast
import re
import shutil
from pathlib import Path
from typing import Dict, Any, List, Tuple, Optional, Set
from .base import Tool
from .file_tools import ReadFileTool, SearchFilesTool
from ..types import ToolResult
from ..cache_service import CacheService


class FileMoverTool(Tool):
    """Tool for moving files and automatically updating imports across the codebase."""
    
    def __init__(self, cache_service: Optional[CacheService] = None,
                 read_tool: Optional[ReadFileTool] = None,
                 search_tool: Optional[SearchFilesTool] = None):
        self.cache_service = cache_service
        self.read_tool = read_tool or ReadFileTool(cache_service)
        self.search_tool = search_tool or SearchFilesTool()
    
    @property
    def name(self) -> str:
        return "move_file"
    
    @property
    def description(self) -> str:
        return "Move files and automatically update all imports/references across the codebase"
    
    @property
    def parameters_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "source_path": {
                    "type": "string",
                    "description": "Current path of the file to move"
                },
                "destination_path": {
                    "type": "string",
                    "description": "New path for the file"
                },
                "update_imports": {
                    "type": "boolean",
                    "description": "Whether to automatically update imports (default: True)",
                    "default": True
                },
                "dry_run": {
                    "type": "boolean",
                    "description": "Preview changes without actually moving files (default: False)",
                    "default": False
                },
                "backup": {
                    "type": "boolean",
                    "description": "Create backup of modified files (default: True)",
                    "default": True
                },
                "project_root": {
                    "type": "string",
                    "description": "Project root directory (auto-detected if not provided)"
                }
            },
            "required": ["source_path", "destination_path"]
        }
    
    @property
    def is_destructive(self) -> bool:
        return True
    
    def execute(self, **parameters) -> ToolResult:
        """Move file and update imports."""
        source_path = parameters.get("source_path")
        destination_path = parameters.get("destination_path")
        update_imports = parameters.get("update_imports", True)
        dry_run = parameters.get("dry_run", False)
        backup = parameters.get("backup", True)
        project_root = parameters.get("project_root")
        
        if not source_path or not destination_path:
            return ToolResult(
                success=False,
                output=None,
                error="Missing source_path or destination_path parameter"
            )
        
        # Convert to absolute paths
        source_path = os.path.abspath(source_path)
        destination_path = os.path.abspath(destination_path)
        
        if not os.path.exists(source_path):
            return ToolResult(
                success=False,
                output=None,
                error=f"Source file not found: {source_path}"
            )
        
        if os.path.exists(destination_path):
            return ToolResult(
                success=False,
                output=None,
                error=f"Destination already exists: {destination_path}"
            )
        
        try:
            # Detect project root if not provided
            if not project_root:
                project_root = self._detect_project_root(source_path)
            
            # Analyze the move operation
            analysis = self._analyze_move_operation(source_path, destination_path, project_root)
            
            # Find all files that import the source file
            affected_files = []
            if update_imports:
                affected_files = self._find_affected_files(source_path, project_root)
            
            # Preview mode
            if dry_run:
                return self._generate_preview(source_path, destination_path, analysis, affected_files)
            
            # Create destination directory if needed
            dest_dir = os.path.dirname(destination_path)
            if dest_dir and not os.path.exists(dest_dir):
                os.makedirs(dest_dir, exist_ok=True)
            
            # Backup affected files if requested
            backup_info = []
            if backup and affected_files:
                backup_info = self._create_backups(affected_files)
            
            # Move the file
            shutil.move(source_path, destination_path)
            
            # Update imports in affected files
            updated_files = []
            if update_imports and affected_files:
                updated_files = self._update_imports(
                    affected_files, source_path, destination_path, project_root
                )
            
            # Generate summary
            summary = f"Successfully moved {source_path} to {destination_path}\n"
            if updated_files:
                summary += f"Updated imports in {len(updated_files)} files:\n"
                for file_path in updated_files:
                    summary += f"  • {file_path}\n"
            
            if backup_info:
                summary += f"Created backups:\n"
                for original, backup_path in backup_info:
                    summary += f"  • {original} → {backup_path}\n"
            
            return ToolResult(
                success=True,
                output=summary,
                action_description=f"Moved {os.path.basename(source_path)} and updated {len(updated_files)} imports"
            )
            
        except Exception as e:
            return ToolResult(
                success=False,
                output=None,
                error=f"File move failed: {str(e)}"
            )
    
    def _detect_project_root(self, file_path: str) -> str:
        """Detect the project root directory."""
        current_dir = os.path.dirname(os.path.abspath(file_path))
        
        while current_dir != os.path.dirname(current_dir):  # Not at filesystem root
            if any(os.path.exists(os.path.join(current_dir, marker)) for marker in 
                   [".git", "package.json", "pyproject.toml", "setup.py", "requirements.txt", ".gitignore"]):
                return current_dir
            current_dir = os.path.dirname(current_dir)
        
        return os.path.dirname(os.path.abspath(file_path))
    
    def _analyze_move_operation(self, source_path: str, destination_path: str, project_root: str) -> Dict[str, Any]:
        """Analyze the move operation to understand import implications."""
        source_rel = os.path.relpath(source_path, project_root)
        dest_rel = os.path.relpath(destination_path, project_root)
        
        analysis = {
            "source_module": self._path_to_module_name(source_rel),
            "dest_module": self._path_to_module_name(dest_rel),
            "file_type": Path(source_path).suffix.lower(),
            "is_python": Path(source_path).suffix.lower() == ".py",
            "is_javascript": Path(source_path).suffix.lower() in [".js", ".ts", ".jsx", ".tsx"],
            "directory_changed": os.path.dirname(source_path) != os.path.dirname(destination_path),
            "name_changed": os.path.basename(source_path) != os.path.basename(destination_path)
        }
        
        return analysis
    
    def _path_to_module_name(self, rel_path: str) -> str:
        """Convert a relative file path to a module name."""
        # Remove file extension and convert path separators to dots
        module_name = os.path.splitext(rel_path)[0].replace(os.sep, '.')
        # Handle __init__.py files
        if module_name.endswith('.__init__'):
            module_name = module_name[:-9]  # Remove .__init__
        return module_name
    
    def _find_affected_files(self, source_path: str, project_root: str) -> List[str]:
        """Find all files that import the source file."""
        affected_files = []
        source_rel = os.path.relpath(source_path, project_root)
        source_module = self._path_to_module_name(source_rel)
        source_name = Path(source_path).stem
        
        # Search patterns based on file type
        if Path(source_path).suffix.lower() == ".py":
            search_patterns = [
                f"from {source_module} import",
                f"import {source_module}",
                f"from .{source_name} import",
                f"from ..{source_name} import"
            ]
        else:
            # JavaScript/TypeScript patterns
            search_patterns = [
                f'import.*from.*["\'].*{source_name}["\']',
                f'require\\(["\'].*{source_name}["\']\\)'
            ]
        
        # Search for each pattern
        for pattern in search_patterns:
            try:
                search_result = self.search_tool.execute(
                    pattern=pattern,
                    path=project_root,
                    file_type="py" if Path(source_path).suffix == ".py" else None
                )
                
                if search_result.success and search_result.output:
                    # Extract file paths from search results
                    files = self._extract_file_paths_from_search(search_result.output)
                    affected_files.extend(files)
                    
            except Exception:
                continue  # Skip failed searches
        
        # Remove duplicates and the source file itself
        affected_files = list(set(affected_files))
        if source_path in affected_files:
            affected_files.remove(source_path)
        
        return affected_files
    
    def _extract_file_paths_from_search(self, search_output: str) -> List[str]:
        """Extract file paths from search tool output."""
        files = []
        lines = search_output.split('\n')
        
        for line in lines:
            if ':' in line:
                # Format: filepath:line_number:content
                file_path = line.split(':', 1)[0].strip()
                if os.path.exists(file_path):
                    files.append(os.path.abspath(file_path))
        
        return files
    
    def _create_backups(self, file_paths: List[str]) -> List[Tuple[str, str]]:
        """Create backups of files that will be modified."""
        backup_info = []
        
        for file_path in file_paths:
            try:
                backup_path = f"{file_path}.backup"
                counter = 1
                while os.path.exists(backup_path):
                    backup_path = f"{file_path}.backup{counter}"
                    counter += 1
                
                shutil.copy2(file_path, backup_path)
                backup_info.append((file_path, backup_path))
                
            except Exception:
                continue  # Skip failed backups
        
        return backup_info
    
    def _update_imports(self, affected_files: List[str], source_path: str, 
                       destination_path: str, project_root: str) -> List[str]:
        """Update imports in affected files."""
        updated_files = []
        
        source_rel = os.path.relpath(source_path, project_root)
        dest_rel = os.path.relpath(destination_path, project_root)
        source_module = self._path_to_module_name(source_rel)
        dest_module = self._path_to_module_name(dest_rel)
        
        for file_path in affected_files:
            try:
                if self._update_file_imports(file_path, source_path, destination_path, 
                                           source_module, dest_module, project_root):
                    updated_files.append(file_path)
            except Exception:
                continue  # Skip failed updates
        
        return updated_files
    
    def _update_file_imports(self, file_path: str, source_path: str, destination_path: str,
                           source_module: str, dest_module: str, project_root: str) -> bool:
        """Update imports in a single file."""
        read_result = self.read_tool.execute(file_path=file_path)
        if not read_result.success:
            return False
        
        content = read_result.output
        original_content = content
        file_ext = Path(file_path).suffix.lower()
        
        if file_ext == ".py":
            content = self._update_python_imports(content, file_path, source_path, 
                                                destination_path, source_module, dest_module, project_root)
        elif file_ext in [".js", ".ts", ".jsx", ".tsx"]:
            content = self._update_javascript_imports(content, file_path, source_path,
                                                    destination_path, project_root)
        
        # Write updated content if changed
        if content != original_content:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)
            return True
        
        return False
    
    def _update_python_imports(self, content: str, file_path: str, source_path: str,
                             destination_path: str, source_module: str, dest_module: str,
                             project_root: str) -> str:
        """Update Python imports in file content."""
        lines = content.split('\n')
        updated_lines = []
        source_name = Path(source_path).stem
        
        for line in lines:
            original_line = line
            
            # Handle different import patterns
            if f"from {source_module} import" in line:
                line = line.replace(f"from {source_module} import", f"from {dest_module} import")
            elif f"import {source_module}" in line:
                line = line.replace(f"import {source_module}", f"import {dest_module}")
            elif f"from .{source_name} import" in line:
                # Relative imports - need to calculate new relative path
                new_relative = self._calculate_relative_import(file_path, destination_path, project_root)
                if new_relative:
                    line = line.replace(f"from .{source_name} import", f"from {new_relative} import")
            elif f"from ..{source_name} import" in line:
                # Parent relative imports
                new_relative = self._calculate_relative_import(file_path, destination_path, project_root)
                if new_relative:
                    line = line.replace(f"from ..{source_name} import", f"from {new_relative} import")
            
            updated_lines.append(line)
        
        return '\n'.join(updated_lines)
    
    def _update_javascript_imports(self, content: str, file_path: str, source_path: str,
                                 destination_path: str, project_root: str) -> str:
        """Update JavaScript/TypeScript imports in file content."""
        source_name = Path(source_path).stem
        dest_name = Path(destination_path).stem
        
        # Calculate relative paths from the importing file
        file_dir = os.path.dirname(file_path)
        old_relative = os.path.relpath(source_path, file_dir)
        new_relative = os.path.relpath(destination_path, file_dir)
        
        # Normalize path separators for import statements
        old_relative = old_relative.replace(os.sep, '/')
        new_relative = new_relative.replace(os.sep, '/')
        
        # Remove file extensions for imports
        old_import_path = os.path.splitext(old_relative)[0]
        new_import_path = os.path.splitext(new_relative)[0]
        
        # Update import statements
        escaped_source = re.escape(source_name)
        patterns = [
            (rf'import\s+([^{{}}]+)\s+from\s+["\']([^"\']*{escaped_source}[^"\']*)["\']', 
             lambda m: f'import {m.group(1)} from "{new_import_path}"'),
            (rf'import\s+["\']([^"\']*{escaped_source}[^"\']*)["\']',
             lambda m: f'import "{new_import_path}"'),
            (rf'require\s*\(\s*["\']([^"\']*{escaped_source}[^"\']*)["\']\s*\)',
             lambda m: f'require("{new_import_path}")')
        ]
        
        for pattern, replacement in patterns:
            content = re.sub(pattern, replacement, content)
        
        return content
    
    def _calculate_relative_import(self, importing_file: str, target_file: str, project_root: str) -> Optional[str]:
        """Calculate the correct relative import path."""
        try:
            importing_dir = os.path.dirname(importing_file)
            target_rel = os.path.relpath(target_file, importing_dir)
            target_module = self._path_to_module_name(target_rel)
            
            # Convert to relative import notation
            if target_module.startswith('..'):
                return target_module
            elif '/' in target_module or '\\' in target_module:
                return f".{target_module}"
            else:
                return f".{target_module}"
                
        except Exception:
            return None
    
    def _generate_preview(self, source_path: str, destination_path: str, 
                         analysis: Dict[str, Any], affected_files: List[str]) -> ToolResult:
        """Generate a preview of the move operation."""
        preview = f"PREVIEW: Move {source_path} → {destination_path}\n\n"
        
        preview += "File Analysis:\n"
        preview += f"  • File type: {analysis['file_type']}\n"
        preview += f"  • Module: {analysis['source_module']} → {analysis['dest_module']}\n"
        preview += f"  • Directory changed: {analysis['directory_changed']}\n"
        preview += f"  • Name changed: {analysis['name_changed']}\n\n"
        
        if affected_files:
            preview += f"Files that will be updated ({len(affected_files)}):\n"
            for file_path in affected_files:
                preview += f"  • {file_path}\n"
        else:
            preview += "No files need import updates.\n"
        
        preview += "\nRun with dry_run=false to execute the move operation."
        
        return ToolResult(
            success=True,
            output=preview,
            action_description="Generated move preview"
        )
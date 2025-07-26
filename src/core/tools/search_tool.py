"""
Code search and navigation tool
"""
import re
import os
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
from .base import BaseTool, ToolParameter, ToolResult


class SearchTool(BaseTool):
    """Tool for searching code patterns, functions, and content across the project"""
    
    def get_description(self) -> str:
        return "Search for code patterns, functions, classes, and text across the project"
    
    def get_parameters(self) -> List[ToolParameter]:
        return [
            ToolParameter(
                name="query",
                type="string",
                description="Search query (text, regex, or function/class name)",
                required=True
            ),
            ToolParameter(
                name="search_type",
                type="string",
                description="Type of search: text, regex, function, class, import, filename",
                required=False,
                default="text"
            ),
            ToolParameter(
                name="file_pattern",
                type="string",
                description="File pattern to search in (e.g., '*.py', '*.js')",
                required=False,
                default="*"
            ),
            ToolParameter(
                name="max_results",
                type="integer",
                description="Maximum number of results to return",
                required=False,
                default=50
            ),
            ToolParameter(
                name="context_lines",
                type="integer", 
                description="Number of context lines around matches",
                required=False,
                default=3
            )
        ]
    
    async def execute(self, **kwargs) -> ToolResult:
        """Execute search operation"""
        if not self.validate_parameters(kwargs):
            return ToolResult(success=False, error="Invalid parameters")
        
        query = kwargs.get("query")
        search_type = kwargs.get("search_type", "text")
        file_pattern = kwargs.get("file_pattern", "*")
        max_results = kwargs.get("max_results", 50)
        context_lines = kwargs.get("context_lines", 3)
        
        try:
            if search_type == "text":
                return await self._text_search(query, file_pattern, max_results, context_lines)
            elif search_type == "regex":
                return await self._regex_search(query, file_pattern, max_results, context_lines)
            elif search_type == "function":
                return await self._function_search(query, file_pattern, max_results)
            elif search_type == "class":
                return await self._class_search(query, file_pattern, max_results)
            elif search_type == "import":
                return await self._import_search(query, file_pattern, max_results)
            elif search_type == "filename":
                return await self._filename_search(query, file_pattern, max_results)
            else:
                return ToolResult(success=False, error=f"Unknown search type: {search_type}")
        
        except Exception as e:
            return ToolResult(success=False, error=str(e))
    
    async def _text_search(self, query: str, file_pattern: str, max_results: int, context_lines: int) -> ToolResult:
        """Search for text in files"""
        results = []
        found_count = 0
        
        for file_path in self._get_matching_files(file_pattern):
            if found_count >= max_results:
                break
            
            try:
                matches = await self._search_in_file(file_path, query, context_lines, is_regex=False)
                if matches:
                    results.append({
                        "file": str(file_path),
                        "matches": matches
                    })
                    found_count += len(matches)
            except Exception:
                continue
        
        return ToolResult(
            success=True,
            content=f"Found {found_count} matches in {len(results)} files",
            data={"results": results, "query": query, "type": "text"}
        )
    
    async def _regex_search(self, pattern: str, file_pattern: str, max_results: int, context_lines: int) -> ToolResult:
        """Search using regex pattern"""
        try:
            compiled_pattern = re.compile(pattern, re.MULTILINE)
        except re.error as e:
            return ToolResult(success=False, error=f"Invalid regex pattern: {e}")
        
        results = []
        found_count = 0
        
        for file_path in self._get_matching_files(file_pattern):
            if found_count >= max_results:
                break
            
            try:
                matches = await self._search_in_file(file_path, pattern, context_lines, is_regex=True)
                if matches:
                    results.append({
                        "file": str(file_path),
                        "matches": matches
                    })
                    found_count += len(matches)
            except Exception:
                continue
        
        return ToolResult(
            success=True,
            content=f"Found {found_count} regex matches in {len(results)} files",
            data={"results": results, "pattern": pattern, "type": "regex"}
        )
    
    async def _function_search(self, function_name: str, file_pattern: str, max_results: int) -> ToolResult:
        """Search for function definitions"""
        results = []
        found_count = 0
        
        # Different function definition patterns for various languages
        patterns = {
            "*.py": [
                rf"^\s*def\s+{re.escape(function_name)}\s*\(",
                rf"^\s*async\s+def\s+{re.escape(function_name)}\s*\("
            ],
            "*.js": [
                rf"function\s+{re.escape(function_name)}\s*\(",
                rf"const\s+{re.escape(function_name)}\s*=.*=>"
            ],
            "*.ts": [
                rf"function\s+{re.escape(function_name)}\s*\(",
                rf"const\s+{re.escape(function_name)}\s*=.*=>"
            ],
            "*.java": [
                rf"\w+\s+{re.escape(function_name)}\s*\("
            ],
            "*.c": [
                rf"\w+\s+{re.escape(function_name)}\s*\("
            ],
            "*.cpp": [
                rf"\w+\s+{re.escape(function_name)}\s*\("
            ]
        }
        
        for file_path in self._get_matching_files(file_pattern):
            if found_count >= max_results:
                break
            
            file_ext = "*" + file_path.suffix
            if file_ext not in patterns:
                continue
            
            try:
                for pattern in patterns[file_ext]:
                    matches = await self._search_in_file(file_path, pattern, 5, is_regex=True)
                    if matches:
                        results.append({
                            "file": str(file_path),
                            "function": function_name,
                            "matches": matches
                        })
                        found_count += len(matches)
                        break
            except Exception:
                continue
        
        return ToolResult(
            success=True,
            content=f"Found {found_count} function definitions for '{function_name}' in {len(results)} files",
            data={"results": results, "function_name": function_name, "type": "function"}
        )
    
    async def _class_search(self, class_name: str, file_pattern: str, max_results: int) -> ToolResult:
        """Search for class definitions"""
        results = []
        found_count = 0
        
        patterns = {
            "*.py": [rf"^\s*class\s+{re.escape(class_name)}\s*[\(:]"],
            "*.js": [rf"class\s+{re.escape(class_name)}\s*[\{{]"],
            "*.ts": [rf"class\s+{re.escape(class_name)}\s*[\{{<]"],
            "*.java": [rf"class\s+{re.escape(class_name)}\s*[\{{<]"],
            "*.cpp": [rf"class\s+{re.escape(class_name)}\s*[\{{;]"],
            "*.c": [rf"struct\s+{re.escape(class_name)}\s*[\{{;]"]
        }
        
        for file_path in self._get_matching_files(file_pattern):
            if found_count >= max_results:
                break
            
            file_ext = "*" + file_path.suffix
            if file_ext not in patterns:
                continue
            
            try:
                for pattern in patterns[file_ext]:
                    matches = await self._search_in_file(file_path, pattern, 10, is_regex=True)
                    if matches:
                        results.append({
                            "file": str(file_path),
                            "class": class_name,
                            "matches": matches
                        })
                        found_count += len(matches)
                        break
            except Exception:
                continue
        
        return ToolResult(
            success=True,
            content=f"Found {found_count} class definitions for '{class_name}' in {len(results)} files",
            data={"results": results, "class_name": class_name, "type": "class"}
        )
    
    async def _import_search(self, import_name: str, file_pattern: str, max_results: int) -> ToolResult:
        """Search for import statements"""
        results = []
        found_count = 0
        
        patterns = {
            "*.py": [
                rf"^\s*import\s+{re.escape(import_name)}",
                rf"^\s*from\s+{re.escape(import_name)}\s+import",
                rf"^\s*from\s+\w+\s+import.*{re.escape(import_name)}"
            ],
            "*.js": [
                rf"import.*{re.escape(import_name)}",
                rf"require\s*\(\s*['\"].*{re.escape(import_name)}"
            ],
            "*.ts": [
                rf"import.*{re.escape(import_name)}",
                rf"require\s*\(\s*['\"].*{re.escape(import_name)}"
            ]
        }
        
        for file_path in self._get_matching_files(file_pattern):
            if found_count >= max_results:
                break
            
            file_ext = "*" + file_path.suffix
            if file_ext not in patterns:
                continue
            
            try:
                for pattern in patterns[file_ext]:
                    matches = await self._search_in_file(file_path, pattern, 2, is_regex=True)
                    if matches:
                        results.append({
                            "file": str(file_path),
                            "import": import_name,
                            "matches": matches
                        })
                        found_count += len(matches)
                        break
            except Exception:
                continue
        
        return ToolResult(
            success=True,
            content=f"Found {found_count} imports for '{import_name}' in {len(results)} files",
            data={"results": results, "import_name": import_name, "type": "import"}
        )
    
    async def _filename_search(self, query: str, file_pattern: str, max_results: int) -> ToolResult:
        """Search for files by filename pattern"""
        results = []
        found_count = 0
        
        # Support regex patterns in filename search
        try:
            # If query contains regex characters, treat as regex
            if any(char in query for char in ['|', '^', '$', '*', '+', '?', '[', ']', '(', ')']):
                pattern = re.compile(query, re.IGNORECASE)
                is_regex = True
            else:
                # Simple text search in filename
                pattern = query.lower()
                is_regex = False
        except re.error:
            # If regex compilation fails, fall back to text search
            pattern = query.lower()
            is_regex = False
        
        for file_path in self._get_matching_files(file_pattern):
            if found_count >= max_results:
                break
            
            filename = file_path.name
            
            # Check if filename matches
            if is_regex:
                if pattern.search(filename):
                    results.append({
                        "file": str(file_path),
                        "filename": filename,
                        "type": "directory" if file_path.is_dir() else "file",
                        "size": file_path.stat().st_size if file_path.is_file() else None
                    })
                    found_count += 1
            else:
                if pattern in filename.lower():
                    results.append({
                        "file": str(file_path),
                        "filename": filename,
                        "type": "directory" if file_path.is_dir() else "file",
                        "size": file_path.stat().st_size if file_path.is_file() else None
                    })
                    found_count += 1
        
        return ToolResult(
            success=True,
            content=f"Found {found_count} files matching '{query}'",
            data={"results": results, "query": query, "type": "filename"}
        )
    
    async def _search_in_file(self, file_path: Path, query: str, context_lines: int, is_regex: bool = False) -> List[Dict[str, Any]]:
        """Search for query in a single file with context"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()
        except (UnicodeDecodeError, IOError):
            return []
        
        matches = []
        
        if is_regex:
            try:
                pattern = re.compile(query, re.MULTILINE)
            except re.error:
                return []
            
            for i, line in enumerate(lines):
                if pattern.search(line):
                    matches.append(self._create_match_context(lines, i, context_lines, line.strip()))
        else:
            # Simple text search
            for i, line in enumerate(lines):
                if query.lower() in line.lower():
                    matches.append(self._create_match_context(lines, i, context_lines, line.strip()))
        
        return matches
    
    def _create_match_context(self, lines: List[str], match_line: int, context_lines: int, matched_content: str) -> Dict[str, Any]:
        """Create match result with context"""
        start_line = max(0, match_line - context_lines)
        end_line = min(len(lines), match_line + context_lines + 1)
        
        context = []
        for i in range(start_line, end_line):
            context.append({
                "line_number": i + 1,
                "content": lines[i].rstrip(),
                "is_match": i == match_line
            })
        
        return {
            "line_number": match_line + 1,
            "matched_content": matched_content,
            "context": context
        }
    
    def _get_matching_files(self, pattern: str) -> List[Path]:
        """Get files matching the pattern"""
        current_dir = Path.cwd()
        
        # Convert glob pattern to pathlib pattern
        if pattern == "*":
            # Search all text files
            extensions = [".py", ".js", ".ts", ".java", ".c", ".cpp", ".h", ".hpp", 
                         ".go", ".rs", ".rb", ".php", ".css", ".html", ".sql", ".sh"]
            files = []
            for ext in extensions:
                files.extend(current_dir.rglob(f"*{ext}"))
        else:
            files = list(current_dir.rglob(pattern))
        
        # Filter out common ignore patterns
        ignore_dirs = {".git", "__pycache__", "node_modules", ".vscode", ".idea", 
                      ".pytest_cache", ".mypy_cache", "venv", "env"}
        
        filtered_files = []
        for file_path in files:
            # Skip if any parent directory is in ignore list
            if any(part in ignore_dirs for part in file_path.parts):
                continue
            
            # Skip if file is too large (>1MB)
            try:
                if file_path.stat().st_size > 1024 * 1024:
                    continue
            except OSError:
                continue
            
            filtered_files.append(file_path)
        
        return filtered_files[:1000]  # Limit to prevent overwhelming results
    
    def get_capabilities(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "description": self.get_description(),
            "async": True,
            "safe": True,
            "categories": ["search", "navigation", "code-analysis"]
        }
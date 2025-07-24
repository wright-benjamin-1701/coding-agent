"""
Code refactoring and modification tool
"""
import ast
import re
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
from .base import BaseTool, ToolParameter, ToolResult


class RefactorTool(BaseTool):
    """Tool for refactoring and modifying code while preserving logic and style"""
    
    def get_description(self) -> str:
        return "Refactor code, rename variables/functions, extract methods, and modify code structure"
    
    def get_parameters(self) -> List[ToolParameter]:
        return [
            ToolParameter(
                name="action",
                type="string",
                description="Refactor action: rename, extract_function, inline, move_function, add_docstring",
                required=True
            ),
            ToolParameter(
                name="file_path",
                type="string",
                description="Path to the file to refactor",
                required=True
            ),
            ToolParameter(
                name="target",
                type="string",
                description="Target to refactor (variable/function/class name)",
                required=False
            ),
            ToolParameter(
                name="new_name",
                type="string",
                description="New name for rename operations",
                required=False
            ),
            ToolParameter(
                name="start_line",
                type="integer",
                description="Start line for extraction/modification",
                required=False
            ),
            ToolParameter(
                name="end_line",
                type="integer",
                description="End line for extraction/modification",
                required=False
            ),
            ToolParameter(
                name="content",
                type="string",
                description="New content for replacement operations",
                required=False
            )
        ]
    
    async def execute(self, **kwargs) -> ToolResult:
        """Execute refactoring operation"""
        if not self.validate_parameters(kwargs):
            return ToolResult(success=False, error="Invalid parameters")
        
        action = kwargs.get("action")
        file_path = kwargs.get("file_path")
        
        if not Path(file_path).exists():
            return ToolResult(success=False, error=f"File not found: {file_path}")
        
        try:
            if action == "rename":
                return await self._rename_symbol(file_path, kwargs.get("target"), kwargs.get("new_name"))
            elif action == "extract_function":
                return await self._extract_function(
                    file_path, 
                    kwargs.get("new_name"),
                    kwargs.get("start_line"), 
                    kwargs.get("end_line")
                )
            elif action == "inline":
                return await self._inline_function(file_path, kwargs.get("target"))
            elif action == "move_function":
                return await self._move_function(file_path, kwargs.get("target"))
            elif action == "add_docstring":
                return await self._add_docstring(file_path, kwargs.get("target"), kwargs.get("content"))
            else:
                return ToolResult(success=False, error=f"Unknown action: {action}")
        
        except Exception as e:
            return ToolResult(success=False, error=str(e))
    
    async def _rename_symbol(self, file_path: str, old_name: str, new_name: str) -> ToolResult:
        """Rename a variable, function, or class throughout the file"""
        if not old_name or not new_name:
            return ToolResult(success=False, error="Both old_name and new_name are required")
        
        path = Path(file_path)
        
        # Read file content
        with open(path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        if path.suffix == '.py':
            return await self._rename_python_symbol(path, content, old_name, new_name)
        else:
            return await self._rename_generic_symbol(path, content, old_name, new_name)
    
    async def _rename_python_symbol(self, path: Path, content: str, old_name: str, new_name: str) -> ToolResult:
        """Rename Python symbol using AST analysis"""
        try:
            tree = ast.parse(content)
        except SyntaxError as e:
            return ToolResult(success=False, error=f"Syntax error in Python file: {e}")
        
        # Find all occurrences of the symbol
        occurrences = []
        
        class SymbolFinder(ast.NodeVisitor):
            def visit_Name(self, node):
                if node.id == old_name:
                    occurrences.append((node.lineno, node.col_offset))
                self.generic_visit(node)
            
            def visit_FunctionDef(self, node):
                if node.name == old_name:
                    occurrences.append((node.lineno, node.col_offset))
                self.generic_visit(node)
            
            def visit_ClassDef(self, node):
                if node.name == old_name:
                    occurrences.append((node.lineno, node.col_offset))
                self.generic_visit(node)
        
        finder = SymbolFinder()
        finder.visit(tree)
        
        if not occurrences:
            return ToolResult(
                success=True,
                content=f"No occurrences of '{old_name}' found",
                data={"renamed_count": 0}
            )
        
        # Apply replacements (work backwards to maintain line numbers)
        lines = content.split('\n')
        occurrences.sort(reverse=True)
        
        renamed_count = 0
        for line_num, col_offset in occurrences:
            line_idx = line_num - 1
            line = lines[line_idx]
            
            # Use word boundaries to avoid partial matches
            pattern = rf'\b{re.escape(old_name)}\b'
            if re.search(pattern, line[col_offset:]):
                lines[line_idx] = re.sub(pattern, new_name, line, count=1)
                renamed_count += 1
        
        # Write back to file
        new_content = '\n'.join(lines)
        with open(path, 'w', encoding='utf-8') as f:
            f.write(new_content)
        
        return ToolResult(
            success=True,
            content=f"Renamed {renamed_count} occurrences of '{old_name}' to '{new_name}'",
            data={"renamed_count": renamed_count, "file": str(path)}
        )
    
    async def _rename_generic_symbol(self, path: Path, content: str, old_name: str, new_name: str) -> ToolResult:
        """Generic symbol renaming using regex"""
        
        # Use word boundaries to avoid partial matches
        pattern = rf'\b{re.escape(old_name)}\b'
        matches = list(re.finditer(pattern, content))
        
        if not matches:
            return ToolResult(
                success=True,
                content=f"No occurrences of '{old_name}' found",
                data={"renamed_count": 0}
            )
        
        # Replace all occurrences
        new_content = re.sub(pattern, new_name, content)
        
        # Write back to file
        with open(path, 'w', encoding='utf-8') as f:
            f.write(new_content)
        
        return ToolResult(
            success=True,
            content=f"Renamed {len(matches)} occurrences of '{old_name}' to '{new_name}'",
            data={"renamed_count": len(matches), "file": str(path)}
        )
    
    async def _extract_function(self, file_path: str, function_name: str, start_line: int, end_line: int) -> ToolResult:
        """Extract lines into a new function"""
        if not function_name or not start_line or not end_line:
            return ToolResult(success=False, error="function_name, start_line, and end_line are required")
        
        if start_line > end_line:
            return ToolResult(success=False, error="start_line must be <= end_line")
        
        path = Path(file_path)
        
        with open(path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        
        if start_line < 1 or end_line > len(lines):
            return ToolResult(success=False, error="Line numbers out of range")
        
        # Extract the code block (convert to 0-based indexing)
        extracted_lines = lines[start_line-1:end_line]
        
        # Determine indentation level
        base_indent = self._get_base_indentation(extracted_lines)
        
        # Create function definition
        function_def = f"def {function_name}():\n"
        
        # Add extracted code with proper indentation
        function_body = []
        for line in extracted_lines:
            # Adjust indentation if needed
            if line.strip():
                # Remove base indentation and add function indentation
                cleaned_line = line[base_indent:] if len(line) > base_indent else line.lstrip()
                function_body.append("    " + cleaned_line)
            else:
                function_body.append(line)
        
        # Insert function before the extracted code location
        insert_pos = start_line - 1
        while insert_pos > 0 and lines[insert_pos-1].strip() == "":
            insert_pos -= 1  # Skip empty lines
        
        # Create new file content
        new_lines = (
            lines[:insert_pos] +
            [function_def] +
            function_body +
            ["\n\n"] +
            lines[insert_pos:start_line-1] +
            [f"    {function_name}()\n"] +  # Function call
            lines[end_line:]
        )
        
        # Write back to file
        with open(path, 'w', encoding='utf-8') as f:
            f.writelines(new_lines)
        
        return ToolResult(
            success=True,
            content=f"Extracted {end_line - start_line + 1} lines into function '{function_name}'",
            data={
                "function_name": function_name,
                "extracted_lines": len(extracted_lines),
                "file": str(path)
            }
        )
    
    async def _inline_function(self, file_path: str, function_name: str) -> ToolResult:
        """Inline a function by replacing calls with function body"""
        if not function_name:
            return ToolResult(success=False, error="function_name is required")
        
        path = Path(file_path)
        
        with open(path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        if path.suffix == '.py':
            return await self._inline_python_function(path, content, function_name)
        else:
            return ToolResult(success=False, error="Inline function only supported for Python files")
    
    async def _inline_python_function(self, path: Path, content: str, function_name: str) -> ToolResult:
        """Inline Python function using AST analysis"""
        try:
            tree = ast.parse(content)
        except SyntaxError as e:
            return ToolResult(success=False, error=f"Syntax error: {e}")
        
        # Find function definition
        function_def = None
        function_calls = []
        
        class FunctionAnalyzer(ast.NodeVisitor):
            def visit_FunctionDef(self, node):
                if node.name == function_name:
                    nonlocal function_def
                    function_def = node
                self.generic_visit(node)
            
            def visit_Call(self, node):
                if isinstance(node.func, ast.Name) and node.func.id == function_name:
                    function_calls.append((node.lineno, node.col_offset))
                self.generic_visit(node)
        
        analyzer = FunctionAnalyzer()
        analyzer.visit(tree)
        
        if not function_def:
            return ToolResult(success=False, error=f"Function '{function_name}' not found")
        
        if len(function_calls) == 0:
            return ToolResult(
                success=True,
                content=f"No calls to function '{function_name}' found",
                data={"inlined_calls": 0}
            )
        
        # For simplicity, only inline simple functions without parameters
        if function_def.args.args:
            return ToolResult(success=False, error="Can only inline functions without parameters")
        
        # Extract function body
        lines = content.split('\n')
        func_start = function_def.lineno - 1
        func_end = func_start
        
        # Find end of function
        for i in range(func_start + 1, len(lines)):
            if lines[i] and not lines[i].startswith('    ') and not lines[i].startswith('\t'):
                func_end = i
                break
        else:
            func_end = len(lines)
        
        # Extract function body (skip def line)
        func_body_lines = lines[func_start + 1:func_end]
        
        # Remove function definition
        new_lines = lines[:func_start] + lines[func_end:]
        
        # Replace function calls with body (work backwards to maintain line numbers)
        function_calls.sort(reverse=True)
        inlined_count = 0
        
        for line_num, _ in function_calls:
            # Adjust line number after function removal
            adjusted_line = line_num - 1
            if line_num > function_def.lineno:
                adjusted_line -= (func_end - func_start)
            
            if 0 <= adjusted_line < len(new_lines):
                # Replace function call with body
                call_line = new_lines[adjusted_line]
                indent = len(call_line) - len(call_line.lstrip())
                
                # Insert function body with proper indentation
                indented_body = []
                for body_line in func_body_lines:
                    if body_line.strip():
                        # Add call site indentation
                        indented_body.append(' ' * indent + body_line.strip())
                    else:
                        indented_body.append('')
                
                # Replace the call line
                new_lines[adjusted_line:adjusted_line+1] = indented_body
                inlined_count += 1
        
        # Write back to file
        with open(path, 'w', encoding='utf-8') as f:
            f.write('\n'.join(new_lines))
        
        return ToolResult(
            success=True,
            content=f"Inlined {inlined_count} calls to function '{function_name}'",
            data={"inlined_calls": inlined_count, "file": str(path)}
        )
    
    async def _move_function(self, file_path: str, function_name: str) -> ToolResult:
        """Move function to a different location in the file"""
        return ToolResult(success=False, error="Move function not yet implemented")
    
    async def _add_docstring(self, file_path: str, target: str, docstring: str) -> ToolResult:
        """Add docstring to a function or class"""
        if not target or not docstring:
            return ToolResult(success=False, error="Both target and docstring content are required")
        
        path = Path(file_path)
        
        with open(path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        
        # Find the target function/class
        for i, line in enumerate(lines):
            if (line.strip().startswith(f'def {target}(') or 
                line.strip().startswith(f'class {target}(')):
                
                # Insert docstring after the definition line
                indent = len(line) - len(line.lstrip()) + 4  # Add 4 spaces
                docstring_lines = [
                    ' ' * indent + '"""' + docstring + '"""\n'
                ]
                
                # Insert after function/class definition
                lines.insert(i + 1, docstring_lines[0])
                
                # Write back to file
                with open(path, 'w', encoding='utf-8') as f:
                    f.writelines(lines)
                
                return ToolResult(
                    success=True,
                    content=f"Added docstring to {target}",
                    data={"target": target, "file": str(path)}
                )
        
        return ToolResult(success=False, error=f"Target '{target}' not found")
    
    def _get_base_indentation(self, lines: List[str]) -> int:
        """Get the base indentation level from a list of lines"""
        for line in lines:
            if line.strip():
                return len(line) - len(line.lstrip())
        return 0
    
    def get_capabilities(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "description": self.get_description(),
            "async": True,
            "safe": False,  # Code modifications can be destructive
            "categories": ["refactoring", "code-modification"]
        }
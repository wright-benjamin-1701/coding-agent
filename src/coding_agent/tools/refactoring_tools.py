"""Refactoring tools for code transformation and improvement."""

import os
import re
import ast
from typing import Dict, Any, List, Optional, Tuple
from pathlib import Path
from .base import Tool
from ..types import ToolResult


class RefactoringTool(Tool):
    """Tool for performing code refactoring operations like extracting functions and renaming variables."""
    
    @property
    def name(self) -> str:
        return "refactor_code"
    
    @property
    def description(self) -> str:
        return "Perform code refactoring operations: extract functions, rename variables, move code blocks"
    
    @property
    def parameters_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "operation": {
                    "type": "string",
                    "enum": ["extract_function", "rename_variable", "move_code", "inline_function"],
                    "description": "Type of refactoring operation to perform"
                },
                "file_path": {
                    "type": "string",
                    "description": "Path to the file to refactor"
                },
                "start_line": {
                    "type": "integer",
                    "description": "Starting line number for code selection (1-indexed)"
                },
                "end_line": {
                    "type": "integer", 
                    "description": "Ending line number for code selection (1-indexed)"
                },
                "old_name": {
                    "type": "string",
                    "description": "Current name of variable/function to rename"
                },
                "new_name": {
                    "type": "string",
                    "description": "New name for variable/function"
                },
                "function_name": {
                    "type": "string",
                    "description": "Name for extracted function"
                },
                "target_file": {
                    "type": "string",
                    "description": "Target file path for move operations"
                },
                "scope": {
                    "type": "string",
                    "enum": ["local", "class", "module", "global"],
                    "description": "Scope of the refactoring operation"
                }
            },
            "required": ["operation", "file_path"]
        }
    
    @property
    def is_destructive(self) -> bool:
        return True  # Modifies source files
    
    def execute(self, **parameters) -> ToolResult:
        """Execute refactoring operation."""
        operation = parameters.get("operation")
        file_path = parameters.get("file_path")
        
        if not os.path.exists(file_path):
            return ToolResult(
                success=False,
                output=None,
                error=f"File not found: {file_path}"
            )
        
        try:
            if operation == "extract_function":
                return self._extract_function(parameters)
            elif operation == "rename_variable":
                return self._rename_variable(parameters)
            elif operation == "move_code":
                return self._move_code(parameters)
            elif operation == "inline_function":
                return self._inline_function(parameters)
            else:
                return ToolResult(
                    success=False,
                    output=None,
                    error=f"Unknown refactoring operation: {operation}"
                )
                
        except Exception as e:
            return ToolResult(
                success=False,
                output=None,
                error=f"Refactoring failed: {str(e)}"
            )
    
    def _extract_function(self, params: dict) -> ToolResult:
        """Extract selected lines into a new function."""
        file_path = params.get("file_path")
        start_line = params.get("start_line")
        end_line = params.get("end_line")
        function_name = params.get("function_name")
        
        if not all([start_line, end_line, function_name]):
            return ToolResult(
                success=False,
                output=None,
                error="extract_function requires start_line, end_line, and function_name"
            )
        
        # Read file content
        with open(file_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        
        if start_line < 1 or end_line > len(lines) or start_line > end_line:
            return ToolResult(
                success=False,
                output=None,
                error=f"Invalid line range: {start_line}-{end_line} for file with {len(lines)} lines"
            )
        
        # Extract the selected code (convert to 0-indexed)
        selected_lines = lines[start_line-1:end_line]
        selected_code = ''.join(selected_lines)
        
        # Analyze the code to determine parameters and return values
        analysis = self._analyze_code_block(selected_code, file_path)
        
        # Generate function signature
        params_str = ", ".join(analysis['parameters'])
        
        # Determine indentation from the first line
        first_line = selected_lines[0] if selected_lines else ""
        base_indent = len(first_line) - len(first_line.lstrip())
        function_indent = max(0, base_indent - 4)  # Function should be less indented
        
        # Create new function
        indent = " " * function_indent
        func_indent = " " * (function_indent + 4)
        
        new_function = f"{indent}def {function_name}({params_str}):\n"
        new_function += f'{func_indent}"""Extracted function {function_name}."""\n'
        
        # Add the extracted code with adjusted indentation
        for line in selected_lines:
            if line.strip():  # Don't adjust empty lines
                # Adjust indentation relative to function
                line_indent = len(line) - len(line.lstrip())
                adjusted_indent = func_indent + " " * max(0, line_indent - base_indent)
                new_function += adjusted_indent + line.lstrip()
            else:
                new_function += line
        
        # Add return statement if needed
        if analysis['return_vars']:
            return_stmt = ", ".join(analysis['return_vars'])
            new_function += f"{func_indent}return {return_stmt}\n"
        
        new_function += "\n"
        
        # Replace selected lines with function call
        call_indent = " " * base_indent
        if analysis['return_vars']:
            return_assignment = ", ".join(analysis['return_vars']) + " = "
        else:
            return_assignment = ""
        
        function_call = f"{call_indent}{return_assignment}{function_name}({params_str})\n"
        
        # Create new file content
        new_lines = []
        new_lines.extend(lines[:start_line-1])  # Lines before selection
        new_lines.append(function_call)  # Function call
        new_lines.extend(lines[end_line:])  # Lines after selection
        
        # Find a good place to insert the new function (before the current function/class)
        insert_pos = self._find_function_insert_position(new_lines, start_line-1)
        new_lines.insert(insert_pos, new_function)
        
        # Write back to file
        with open(file_path, 'w', encoding='utf-8') as f:
            f.writelines(new_lines)
        
        return ToolResult(
            success=True,
            output=f"Extracted function '{function_name}' from lines {start_line}-{end_line}\n\nNew function:\n{new_function}",
            action_description=f"Extracted function {function_name} from lines {start_line}-{end_line}"
        )
    
    def _rename_variable(self, params: dict) -> ToolResult:
        """Rename a variable throughout the specified scope."""
        file_path = params.get("file_path")
        old_name = params.get("old_name")
        new_name = params.get("new_name")
        scope = params.get("scope", "local")
        
        if not all([old_name, new_name]):
            return ToolResult(
                success=False,
                output=None,
                error="rename_variable requires old_name and new_name"
            )
        
        # Read and parse the file
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        try:
            # Parse the AST for Python files
            if file_path.endswith('.py'):
                return self._rename_python_variable(file_path, content, old_name, new_name, scope)
            else:
                # For non-Python files, do simple text replacement with word boundaries
                return self._rename_text_variable(file_path, content, old_name, new_name)
                
        except SyntaxError as e:
            return ToolResult(
                success=False,
                output=None,
                error=f"Syntax error in file: {str(e)}"
            )
    
    def _move_code(self, params: dict) -> ToolResult:
        """Move code block to another location."""
        file_path = params.get("file_path")
        target_file = params.get("target_file")
        start_line = params.get("start_line")
        end_line = params.get("end_line")
        
        if not all([start_line, end_line]):
            return ToolResult(
                success=False,
                output=None,
                error="move_code requires start_line and end_line"
            )
        
        # Read source file
        with open(file_path, 'r', encoding='utf-8') as f:
            source_lines = f.readlines()
        
        # Extract code to move
        if start_line < 1 or end_line > len(source_lines) or start_line > end_line:
            return ToolResult(
                success=False,
                output=None,
                error=f"Invalid line range: {start_line}-{end_line}"
            )
        
        moved_code = ''.join(source_lines[start_line-1:end_line])
        
        # Remove from source file
        new_source_lines = source_lines[:start_line-1] + source_lines[end_line:]
        
        with open(file_path, 'w', encoding='utf-8') as f:
            f.writelines(new_source_lines)
        
        # Add to target file (or append to same file if no target specified)
        target_path = target_file or file_path
        
        if target_file and target_file != file_path:
            # Ensure target directory exists
            os.makedirs(os.path.dirname(target_path), exist_ok=True)
            
            if os.path.exists(target_path):
                with open(target_path, 'a', encoding='utf-8') as f:
                    f.write("\n" + moved_code)
            else:
                with open(target_path, 'w', encoding='utf-8') as f:
                    f.write(moved_code)
        
        return ToolResult(
            success=True,
            output=f"Moved code from lines {start_line}-{end_line} to {target_path}\n\nMoved code:\n{moved_code}",
            action_description=f"Moved code block to {target_path}"
        )
    
    def _inline_function(self, params: dict) -> ToolResult:
        """Inline a simple function at its call sites."""
        file_path = params.get("file_path")
        function_name = params.get("function_name")
        
        if not function_name:
            return ToolResult(
                success=False,
                output=None,
                error="inline_function requires function_name"
            )
        
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Find function definition
        func_pattern = rf'^(\s*)def\s+{re.escape(function_name)}\s*\([^)]*\)\s*:'
        func_match = re.search(func_pattern, content, re.MULTILINE)
        
        if not func_match:
            return ToolResult(
                success=False,
                output=None,
                error=f"Function '{function_name}' not found"
            )
        
        return ToolResult(
            success=False,
            output=None,
            error="Function inlining is complex and not yet implemented. Consider using extract_function instead."
        )
    
    def _analyze_code_block(self, code: str, file_path: str) -> dict:
        """Analyze a code block to determine parameters and return values."""
        analysis = {
            'parameters': [],
            'return_vars': [],
            'imports': []
        }
        
        if not file_path.endswith('.py'):
            return analysis
        
        try:
            # Create a simple analysis by looking for variable usage
            lines = code.strip().split('\\n')
            
            # Simple heuristic: variables assigned to might be return values
            assigned_vars = set()
            used_vars = set()
            
            for line in lines:
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                
                # Find assignments
                if '=' in line and not line.startswith('if ') and not line.startswith('while ') and not line.startswith('for '):
                    parts = line.split('=', 1)
                    if len(parts) == 2:
                        left = parts[0].strip()
                        # Simple variable names only
                        if re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*$', left):
                            assigned_vars.add(left)
                
                # Find variable usage (very basic)
                words = re.findall(r'\b[a-zA-Z_][a-zA-Z0-9_]*\b', line)
                for word in words:
                    if word not in ['if', 'else', 'elif', 'for', 'while', 'def', 'class', 'import', 'from', 'return']:
                        used_vars.add(word)
            
            # Parameters are variables used but not assigned (simple heuristic)
            potential_params = used_vars - assigned_vars
            # Filter out likely built-ins and common functions
            builtin_names = {'print', 'len', 'str', 'int', 'float', 'list', 'dict', 'set', 'tuple', 'range', 'enumerate', 'zip'}
            analysis['parameters'] = sorted(list(potential_params - builtin_names))[:5]  # Limit to 5 params
            
            # Return values are assigned variables (simple heuristic)
            analysis['return_vars'] = sorted(list(assigned_vars))[:3]  # Limit to 3 return values
            
        except Exception:
            # If analysis fails, provide empty analysis
            pass
        
        return analysis
    
    def _find_function_insert_position(self, lines: List[str], current_pos: int) -> int:
        """Find appropriate position to insert a new function."""
        # Look backwards for a good insertion point
        for i in range(current_pos - 1, -1, -1):
            line = lines[i].strip()
            if line.startswith('def ') or line.startswith('class '):
                return i
        
        # If no function/class found, insert at beginning (after imports)
        for i, line in enumerate(lines):
            if not (line.strip().startswith('import ') or 
                   line.strip().startswith('from ') or 
                   line.strip() == '' or 
                   line.strip().startswith('#')):
                return i
        
        return 0
    
    def _rename_python_variable(self, file_path: str, content: str, old_name: str, new_name: str, scope: str) -> ToolResult:
        """Rename variable in Python file using AST analysis."""
        try:
            tree = ast.parse(content)
        except SyntaxError as e:
            return ToolResult(
                success=False,
                output=None,
                error=f"Cannot parse Python file: {str(e)}"
            )
        
        # For now, do simple text replacement with word boundaries
        # TODO: Implement proper AST-based renaming with scope awareness
        return self._rename_text_variable(file_path, content, old_name, new_name)
    
    def _rename_text_variable(self, file_path: str, content: str, old_name: str, new_name: str) -> ToolResult:
        """Rename variable using text replacement with word boundaries."""
        # Use word boundaries to avoid partial replacements
        pattern = r'\\b' + re.escape(old_name) + r'\\b'
        new_content = re.sub(pattern, new_name, content)
        
        if new_content == content:
            return ToolResult(
                success=False,
                output=None,
                error=f"Variable '{old_name}' not found in file"
            )
        
        # Count replacements
        matches = len(re.findall(pattern, content))
        
        # Write back to file
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(new_content)
        
        return ToolResult(
            success=True,
            output=f"Renamed '{old_name}' to '{new_name}' in {matches} locations",
            action_description=f"Renamed variable '{old_name}' to '{new_name}' ({matches} occurrences)"
        )
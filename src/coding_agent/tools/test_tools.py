"""Testing and linting tools."""

import subprocess
from typing import Dict, Any
from .base import Tool
from ..types import ToolResult


class RunTestsTool(Tool):
    """Tool for running tests."""
    
    @property
    def name(self) -> str:
        return "run_tests"
    
    @property
    def description(self) -> str:
        return "Run tests using common test runners"
    
    @property
    def parameters_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "test_file": {"type": "string", "description": "Specific test file to run"},
                "test_framework": {"type": "string", "description": "Test framework (pytest, npm, go, etc.)"}
            }
        }
    
    @property
    def is_destructive(self) -> bool:
        return False
    
    def execute(self, test_file: str = None, test_framework: str = None) -> ToolResult:
        """Run tests."""
        try:
            # Auto-detect test framework if not specified
            if not test_framework:
                if test_file and test_file.endswith('.py'):
                    test_framework = 'pytest'
                elif test_file and test_file.endswith('.js'):
                    test_framework = 'npm'
                elif test_file and test_file.endswith('.go'):
                    test_framework = 'go'
                else:
                    test_framework = 'pytest'  # default
            
            # Build command
            if test_framework == 'pytest':
                cmd = ['pytest', '-v']
                if test_file:
                    cmd.append(test_file)
            elif test_framework == 'npm':
                cmd = ['npm', 'test']
            elif test_framework == 'go':
                cmd = ['go', 'test']
                if test_file:
                    cmd.append(test_file)
            else:
                return ToolResult(success=False, output=None, error=f"Unknown test framework: {test_framework}")
            
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            return ToolResult(
                success=result.returncode == 0,
                output=result.stdout + result.stderr
            )
        except Exception as e:
            return ToolResult(success=False, output=None, error=str(e))


class LintCodeTool(Tool):
    """Tool for linting code."""
    
    @property
    def name(self) -> str:
        return "lint_code"
    
    @property
    def description(self) -> str:
        return "Run linter on code files"
    
    @property
    def parameters_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "file_path": {"type": "string", "description": "File to lint"},
                "linter": {"type": "string", "description": "Linter to use (flake8, eslint, etc.)"}
            }
        }
    
    @property
    def is_destructive(self) -> bool:
        return False
    
    def execute(self, file_path: str = None, linter: str = None) -> ToolResult:
        """Run linter."""
        try:
            # Auto-detect linter if not specified
            if not linter:
                if file_path and file_path.endswith('.py'):
                    linter = 'flake8'
                elif file_path and file_path.endswith('.js'):
                    linter = 'eslint'
                else:
                    linter = 'flake8'
            
            cmd = [linter]
            if file_path:
                cmd.append(file_path)
            else:
                cmd.append('.')
            
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            return ToolResult(
                success=result.returncode == 0,
                output=result.stdout + result.stderr
            )
        except Exception as e:
            return ToolResult(success=False, output=None, error=str(e))
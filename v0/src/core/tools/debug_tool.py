"""
Error diagnosis and debugging tool
"""
import ast
import re
import subprocess
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
from .base import BaseTool, ToolParameter, ToolResult


class DebugTool(BaseTool):
    """Tool for diagnosing errors and suggesting fixes"""
    
    def get_description(self) -> str:
        return "Diagnose compiler/runtime errors, analyze stack traces, and suggest fixes"
    
    def get_parameters(self) -> List[ToolParameter]:
        return [
            ToolParameter(
                name="action",
                type="string",
                description="Debug action: analyze_error, check_syntax, find_issues, run_linter",
                required=True
            ),
            ToolParameter(
                name="file_path",
                type="string",
                description="Path to the file to analyze",
                required=False
            ),
            ToolParameter(
                name="error_message",
                type="string",
                description="Error message or stack trace to analyze",
                required=False
            ),
            ToolParameter(
                name="language",
                type="string",
                description="Programming language (python, javascript, etc.)",
                required=False
            ),
            ToolParameter(
                name="code",
                type="string",
                description="Code snippet to analyze",
                required=False
            )
        ]
    
    async def execute(self, **kwargs) -> ToolResult:
        """Execute debug operation"""
        if not self.validate_parameters(kwargs):
            return ToolResult(success=False, error="Invalid parameters")
        
        action = kwargs.get("action")
        
        try:
            if action == "analyze_error":
                return await self._analyze_error(
                    kwargs.get("error_message"), 
                    kwargs.get("file_path"),
                    kwargs.get("language")
                )
            elif action == "check_syntax":
                return await self._check_syntax(
                    kwargs.get("file_path"),
                    kwargs.get("code"),
                    kwargs.get("language")
                )
            elif action == "find_issues":
                return await self._find_common_issues(
                    kwargs.get("file_path"),
                    kwargs.get("language")
                )
            elif action == "run_linter":
                return await self._run_linter(
                    kwargs.get("file_path"),
                    kwargs.get("language")
                )
            else:
                return ToolResult(success=False, error=f"Unknown action: {action}")
        
        except Exception as e:
            return ToolResult(success=False, error=str(e))
    
    async def _analyze_error(self, error_message: str, file_path: Optional[str] = None, language: Optional[str] = None) -> ToolResult:
        """Analyze error message and provide diagnosis"""
        
        if not error_message:
            return ToolResult(success=False, error="Error message is required")
        
        # Detect language from file path if not provided
        if not language and file_path:
            language = self._detect_language(Path(file_path))
        
        # Parse error message
        error_info = self._parse_error_message(error_message, language)
        
        # Generate diagnosis and suggestions
        diagnosis = await self._diagnose_error(error_info, file_path, language)
        
        return ToolResult(
            success=True,
            content=f"Error Analysis: {diagnosis['summary']}",
            data={
                "error_type": error_info["type"],
                "line_number": error_info.get("line"),
                "diagnosis": diagnosis,
                "suggestions": diagnosis.get("suggestions", []),
                "fix_examples": diagnosis.get("fix_examples", [])
            }
        )
    
    async def _check_syntax(self, file_path: Optional[str] = None, code: Optional[str] = None, language: Optional[str] = None) -> ToolResult:
        """Check syntax of code or file"""
        
        if not file_path and not code:
            return ToolResult(success=False, error="Either file_path or code is required")
        
        if file_path:
            path = Path(file_path)
            if not path.exists():
                return ToolResult(success=False, error=f"File not found: {file_path}")
            
            with open(path, 'r', encoding='utf-8') as f:
                code = f.read()
            
            if not language:
                language = self._detect_language(path)
        
        syntax_issues = []
        
        if language == "python":
            syntax_issues = await self._check_python_syntax(code, file_path)
        elif language in ["javascript", "typescript"]:
            syntax_issues = await self._check_javascript_syntax(code, file_path)
        else:
            return ToolResult(success=False, error=f"Syntax checking not supported for {language}")
        
        if syntax_issues:
            return ToolResult(
                success=True,
                content=f"Found {len(syntax_issues)} syntax issues",
                data={"issues": syntax_issues, "has_errors": True}
            )
        else:
            return ToolResult(
                success=True,
                content="No syntax errors found",
                data={"issues": [], "has_errors": False}
            )
    
    async def _find_common_issues(self, file_path: str, language: Optional[str] = None) -> ToolResult:
        """Find common programming issues in code"""
        
        if not file_path or not Path(file_path).exists():
            return ToolResult(success=False, error=f"File not found: {file_path}")
        
        path = Path(file_path)
        if not language:
            language = self._detect_language(path)
        
        with open(path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        issues = []
        
        if language == "python":
            issues = await self._find_python_issues(content, str(path))
        elif language in ["javascript", "typescript"]:
            issues = await self._find_javascript_issues(content, str(path))
        
        severity_counts = {"error": 0, "warning": 0, "info": 0}
        for issue in issues:
            severity_counts[issue.get("severity", "info")] += 1
        
        return ToolResult(
            success=True,
            content=f"Found {len(issues)} potential issues: {severity_counts['error']} errors, {severity_counts['warning']} warnings",
            data={
                "issues": issues,
                "severity_counts": severity_counts,
                "file": str(path)
            }
        )
    
    async def _run_linter(self, file_path: str, language: Optional[str] = None) -> ToolResult:
        """Run appropriate linter for the file"""
        
        if not file_path or not Path(file_path).exists():
            return ToolResult(success=False, error=f"File not found: {file_path}")
        
        path = Path(file_path)
        if not language:
            language = self._detect_language(path)
        
        try:
            if language == "python":
                return await self._run_python_linter(str(path))
            elif language in ["javascript", "typescript"]:
                return await self._run_javascript_linter(str(path))
            else:
                return ToolResult(success=False, error=f"No linter available for {language}")
        
        except Exception as e:
            return ToolResult(success=False, error=f"Linter execution failed: {e}")
    
    def _parse_error_message(self, error_message: str, language: Optional[str] = None) -> Dict[str, Any]:
        """Parse error message to extract key information"""
        
        error_info = {
            "type": "unknown",
            "message": error_message,
            "line": None,
            "column": None,
            "file": None
        }
        
        # Python error patterns
        if language == "python" or "Traceback" in error_message:
            # Extract line number
            line_match = re.search(r'line (\d+)', error_message)
            if line_match:
                error_info["line"] = int(line_match.group(1))
            
            # Extract error type
            if "SyntaxError" in error_message:
                error_info["type"] = "syntax_error"
            elif "NameError" in error_message:
                error_info["type"] = "name_error"
            elif "TypeError" in error_message:
                error_info["type"] = "type_error"
            elif "ImportError" in error_message or "ModuleNotFoundError" in error_message:
                error_info["type"] = "import_error"
            elif "IndentationError" in error_message:
                error_info["type"] = "indentation_error"
        
        # JavaScript error patterns
        elif language in ["javascript", "typescript"] or "Error:" in error_message:
            # Extract line number
            line_match = re.search(r':(\d+):(\d+)', error_message)
            if line_match:
                error_info["line"] = int(line_match.group(1))
                error_info["column"] = int(line_match.group(2))
            
            if "SyntaxError" in error_message:
                error_info["type"] = "syntax_error"
            elif "ReferenceError" in error_message:
                error_info["type"] = "reference_error"
            elif "TypeError" in error_message:
                error_info["type"] = "type_error"
        
        return error_info
    
    async def _diagnose_error(self, error_info: Dict[str, Any], file_path: Optional[str], language: Optional[str]) -> Dict[str, Any]:
        """Generate diagnosis and suggestions for the error"""
        
        error_type = error_info["type"]
        
        diagnoses = {
            "syntax_error": {
                "summary": "Syntax error detected - code structure is invalid",
                "common_causes": [
                    "Missing or mismatched parentheses, brackets, or braces",
                    "Incorrect indentation",
                    "Invalid keyword usage",
                    "Missing colons or semicolons"
                ],
                "suggestions": [
                    "Check for matching parentheses and brackets",
                    "Verify proper indentation",
                    "Look for typos in keywords",
                    "Ensure proper statement termination"
                ]
            },
            "name_error": {
                "summary": "Undefined variable or function referenced",
                "common_causes": [
                    "Variable used before definition",
                    "Typo in variable/function name",
                    "Variable out of scope",
                    "Missing import statement"
                ],
                "suggestions": [
                    "Check variable spelling and definition",
                    "Ensure variable is defined before use",
                    "Verify variable scope",
                    "Add missing import statements"
                ]
            },
            "type_error": {
                "summary": "Operation performed on incompatible types",
                "common_causes": [
                    "Calling non-function as function",
                    "Wrong number of arguments",
                    "Incompatible type operations",
                    "Null/undefined access"
                ],
                "suggestions": [
                    "Check function call syntax",
                    "Verify argument count and types",
                    "Add type checks or conversions",
                    "Handle null/undefined values"
                ]
            },
            "import_error": {
                "summary": "Module or package import failed",
                "common_causes": [
                    "Module not installed",
                    "Incorrect module name",
                    "Wrong import path",
                    "Circular imports"
                ],
                "suggestions": [
                    "Install missing packages",
                    "Check module name spelling",
                    "Verify import paths",
                    "Restructure to avoid circular imports"
                ]
            }
        }
        
        return diagnoses.get(error_type, {
            "summary": "Unknown error type",
            "common_causes": ["Error pattern not recognized"],
            "suggestions": ["Manual debugging required"]
        })
    
    async def _check_python_syntax(self, code: str, file_path: Optional[str] = None) -> List[Dict[str, Any]]:
        """Check Python syntax using AST"""
        
        issues = []
        
        try:
            ast.parse(code)
        except SyntaxError as e:
            issues.append({
                "type": "syntax_error",
                "line": e.lineno,
                "column": e.offset,
                "message": str(e),
                "severity": "error",
                "file": file_path
            })
        
        return issues
    
    async def _check_javascript_syntax(self, code: str, file_path: Optional[str] = None) -> List[Dict[str, Any]]:
        """Basic JavaScript syntax checking"""
        
        issues = []
        
        # Basic pattern matching for common syntax errors
        lines = code.split('\n')
        
        for i, line in enumerate(lines, 1):
            # Check for mismatched brackets
            open_brackets = line.count('{') + line.count('[') + line.count('(')
            close_brackets = line.count('}') + line.count(']') + line.count(')')
            
            if open_brackets != close_brackets:
                issues.append({
                    "type": "bracket_mismatch",
                    "line": i,
                    "message": "Possible bracket mismatch",
                    "severity": "warning",
                    "file": file_path
                })
        
        return issues
    
    async def _find_python_issues(self, content: str, file_path: str) -> List[Dict[str, Any]]:
        """Find common Python issues"""
        
        issues = []
        lines = content.split('\n')
        
        for i, line in enumerate(lines, 1):
            # Check for common issues
            
            # Long lines
            if len(line) > 100:
                issues.append({
                    "type": "long_line",
                    "line": i,
                    "message": f"Line too long ({len(line)} characters)",
                    "severity": "info",
                    "file": file_path
                })
            
            # TODO comments
            if "TODO" in line or "FIXME" in line:
                issues.append({
                    "type": "todo",
                    "line": i,
                    "message": "TODO/FIXME comment found",
                    "severity": "info",
                    "file": file_path
                })
            
            # Potential issues
            if re.search(r'print\s*\(', line) and not line.strip().startswith('#'):
                issues.append({
                    "type": "debug_print",
                    "line": i,
                    "message": "Debug print statement found",
                    "severity": "warning",
                    "file": file_path
                })
        
        return issues
    
    async def _find_javascript_issues(self, content: str, file_path: str) -> List[Dict[str, Any]]:
        """Find common JavaScript issues"""
        
        issues = []
        lines = content.split('\n')
        
        for i, line in enumerate(lines, 1):
            # Console.log statements
            if re.search(r'console\.log\s*\(', line) and not line.strip().startswith('//'):
                issues.append({
                    "type": "debug_log",
                    "line": i,
                    "message": "Debug console.log found",
                    "severity": "warning",
                    "file": file_path
                })
            
            # TODO comments
            if "TODO" in line or "FIXME" in line:
                issues.append({
                    "type": "todo",
                    "line": i,
                    "message": "TODO/FIXME comment found",
                    "severity": "info",
                    "file": file_path
                })
        
        return issues
    
    async def _run_python_linter(self, file_path: str) -> ToolResult:
        """Run Python linter (flake8 or pycodestyle if available)"""
        
        linters = ["flake8", "pycodestyle"]
        
        for linter in linters:
            try:
                result = subprocess.run(
                    [linter, file_path],
                    capture_output=True,
                    text=True,
                    timeout=30
                )
                
                if result.returncode == 0:
                    return ToolResult(
                        success=True,
                        content="No linting issues found",
                        data={"linter": linter, "issues": []}
                    )
                else:
                    # Parse linter output
                    issues = self._parse_linter_output(result.stdout, linter)
                    return ToolResult(
                        success=True,
                        content=f"Found {len(issues)} linting issues",
                        data={"linter": linter, "issues": issues}
                    )
            
            except (subprocess.TimeoutExpired, FileNotFoundError):
                continue
        
        return ToolResult(success=False, error="No Python linter available (install flake8 or pycodestyle)")
    
    async def _run_javascript_linter(self, file_path: str) -> ToolResult:
        """Run JavaScript linter (eslint if available)"""
        
        try:
            result = subprocess.run(
                ["eslint", file_path, "--format", "json"],
                capture_output=True,
                text=True,
                timeout=30
            )
            
            # ESLint returns non-zero for linting issues, which is expected
            issues = []
            if result.stdout:
                import json
                try:
                    lint_results = json.loads(result.stdout)
                    for file_result in lint_results:
                        issues.extend(file_result.get("messages", []))
                except json.JSONDecodeError:
                    pass
            
            return ToolResult(
                success=True,
                content=f"Found {len(issues)} linting issues",
                data={"linter": "eslint", "issues": issues}
            )
        
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return ToolResult(success=False, error="ESLint not available (install with npm install -g eslint)")
    
    def _parse_linter_output(self, output: str, linter: str) -> List[Dict[str, Any]]:
        """Parse linter output into structured issues"""
        
        issues = []
        
        for line in output.split('\n'):
            if not line.strip():
                continue
            
            # Parse flake8/pycodestyle format: filename:line:column: error_code message
            match = re.match(r'^([^:]+):(\d+):(\d+):\s*(\w+)\s+(.+)$', line)
            if match:
                filename, line_num, col_num, error_code, message = match.groups()
                
                issues.append({
                    "file": filename,
                    "line": int(line_num),
                    "column": int(col_num),
                    "code": error_code,
                    "message": message,
                    "severity": "error" if error_code.startswith('E') else "warning"
                })
        
        return issues
    
    def _detect_language(self, file_path: Path) -> str:
        """Detect programming language from file extension"""
        
        extension = file_path.suffix.lower()
        language_map = {
            '.py': 'python',
            '.js': 'javascript',
            '.ts': 'typescript',
            '.java': 'java',
            '.c': 'c',
            '.cpp': 'cpp',
            '.go': 'go',
            '.rs': 'rust'
        }
        
        return language_map.get(extension, 'unknown')
    
    def get_capabilities(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "description": self.get_description(),
            "async": True,
            "safe": True,
            "categories": ["debugging", "error-analysis", "code-quality"]
        }
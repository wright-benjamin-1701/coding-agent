"""Test generator tool that creates comprehensive tests for existing code."""

import os
import ast
import re
import json
from pathlib import Path
from typing import Dict, Any, List, Tuple, Optional, Set
from .base import Tool
from .file_tools import ReadFileTool, SearchFilesTool
from ..types import ToolResult
from ..cache_service import CacheService


class TestGeneratorTool(Tool):
    """Tool for automatically generating tests from existing code."""
    
    def __init__(self, model_provider, cache_service: Optional[CacheService] = None,
                 read_tool: Optional[ReadFileTool] = None,
                 search_tool: Optional[SearchFilesTool] = None):
        self.model_provider = model_provider
        self.cache_service = cache_service
        self.read_tool = read_tool or ReadFileTool(cache_service)
        self.search_tool = search_tool or SearchFilesTool()
    
    @property
    def name(self) -> str:
        return "generate_tests"
    
    @property
    def description(self) -> str:
        return "Generate comprehensive tests for existing code by analyzing function signatures, logic, and edge cases"
    
    @property
    def parameters_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": "Path to the source file to generate tests for"
                },
                "function_name": {
                    "type": "string",
                    "description": "Specific function to test (optional, if not provided tests all functions)"
                },
                "test_framework": {
                    "type": "string",
                    "description": "Testing framework to use",
                    "enum": ["pytest", "unittest", "jest", "vitest", "mocha", "auto"],
                    "default": "auto"
                },
                "test_types": {
                    "type": "array",
                    "description": "Types of tests to generate",
                    "items": {
                        "type": "string",
                        "enum": ["unit", "integration", "edge_cases", "error_handling", "performance"]
                    },
                    "default": ["unit", "edge_cases", "error_handling"]
                },
                "coverage_target": {
                    "type": "string",
                    "description": "Target test coverage level",
                    "enum": ["basic", "comprehensive", "exhaustive"],
                    "default": "comprehensive"
                },
                "output_file": {
                    "type": "string",
                    "description": "Output file path for tests (auto-generated if not provided)"
                },
                "mock_dependencies": {
                    "type": "boolean",
                    "description": "Whether to generate mocks for external dependencies",
                    "default": True
                }
            },
            "required": ["file_path"]
        }
    
    @property
    def is_destructive(self) -> bool:
        return True  # Creates new test files
    
    def execute(self, **parameters) -> ToolResult:
        """Generate tests for the specified code."""
        file_path = parameters.get("file_path")
        function_name = parameters.get("function_name")
        test_framework = parameters.get("test_framework", "auto")
        test_types = parameters.get("test_types", ["unit", "edge_cases", "error_handling"])
        coverage_target = parameters.get("coverage_target", "comprehensive")
        output_file = parameters.get("output_file")
        mock_dependencies = parameters.get("mock_dependencies", True)
        
        if not file_path:
            return ToolResult(
                success=False,
                output=None,
                error="Missing file_path parameter"
            )
        
        if not os.path.exists(file_path):
            return ToolResult(
                success=False,
                output=None,
                error=f"Source file not found: {file_path}"
            )
        
        try:
            # Read the source file
            read_result = self.read_tool.execute(file_path=file_path)
            if not read_result.success:
                return ToolResult(
                    success=False,
                    output=None,
                    error=f"Could not read source file: {read_result.error}"
                )
            
            source_code = read_result.output
            file_ext = Path(file_path).suffix.lower()
            
            # Analyze the code and extract testable elements
            if file_ext == ".py":
                analysis = self._analyze_python_code(source_code, file_path)
            elif file_ext in [".js", ".ts", ".jsx", ".tsx"]:
                analysis = self._analyze_javascript_code(source_code, file_path)
            else:
                return ToolResult(
                    success=False,
                    output=None,
                    error=f"Unsupported file type: {file_ext}"
                )
            
            # Filter to specific function if requested
            if function_name:
                analysis["functions"] = [f for f in analysis["functions"] if f["name"] == function_name]
                if not analysis["functions"]:
                    return ToolResult(
                        success=False,
                        output=None,
                        error=f"Function '{function_name}' not found in {file_path}"
                    )
            
            # Determine test framework if auto
            if test_framework == "auto":
                test_framework = self._detect_test_framework(file_path, file_ext)
            
            # Generate output file path if not provided
            if not output_file:
                output_file = self._generate_test_file_path(file_path, test_framework)
            
            # Generate the test code
            test_code = self._generate_test_code(
                analysis, test_framework, test_types, coverage_target, mock_dependencies
            )
            
            # Write the test file
            test_dir = os.path.dirname(output_file)
            if test_dir:
                os.makedirs(test_dir, exist_ok=True)
            
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(test_code)
            
            # Generate summary
            function_count = len(analysis["functions"])
            class_count = len(analysis["classes"])
            
            summary = f"Generated {test_framework} tests for {file_path}:\n"
            summary += f"  • {function_count} functions tested\n"
            summary += f"  • {class_count} classes tested\n"
            summary += f"  • Test types: {', '.join(test_types)}\n"
            summary += f"  • Coverage target: {coverage_target}\n"
            summary += f"  • Output: {output_file}\n"
            
            if mock_dependencies and analysis["dependencies"]:
                summary += f"  • Mocked {len(analysis['dependencies'])} dependencies\n"
            
            return ToolResult(
                success=True,
                output=summary,
                action_description=f"Generated tests for {file_path}"
            )
            
        except Exception as e:
            return ToolResult(
                success=False,
                output=None,
                error=f"Test generation failed: {str(e)}"
            )
    
    def _analyze_python_code(self, source_code: str, file_path: str) -> Dict[str, Any]:
        """Analyze Python code to extract testable elements."""
        try:
            tree = ast.parse(source_code)
        except SyntaxError as e:
            raise ValueError(f"Invalid Python syntax: {e}")
        
        analysis = {
            "language": "python",
            "file_path": file_path,
            "functions": [],
            "classes": [],
            "imports": [],
            "dependencies": [],
            "constants": []
        }
        
        # Extract imports and dependencies
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    analysis["imports"].append(alias.name)
                    if not alias.name.startswith('.') and '.' not in alias.name:
                        analysis["dependencies"].append(alias.name)
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ""
                for alias in node.names:
                    analysis["imports"].append(f"{module}.{alias.name}")
                if module and not module.startswith('.'):
                    analysis["dependencies"].append(module)
        
        # Extract functions and classes
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                if not node.name.startswith('_'):  # Skip private functions
                    func_info = self._analyze_python_function(node, source_code)
                    analysis["functions"].append(func_info)
            elif isinstance(node, ast.ClassDef):
                class_info = self._analyze_python_class(node, source_code)
                analysis["classes"].append(class_info)
            elif isinstance(node, ast.Assign):
                # Extract module-level constants
                for target in node.targets:
                    if isinstance(target, ast.Name) and target.id.isupper():
                        analysis["constants"].append(target.id)
        
        return analysis
    
    def _analyze_python_function(self, node: ast.FunctionDef, source_code: str) -> Dict[str, Any]:
        """Analyze a Python function for test generation."""
        func_info = {
            "name": node.name,
            "args": [],
            "return_annotation": None,
            "docstring": None,
            "complexity": "simple",
            "has_conditionals": False,
            "has_loops": False,
            "has_exceptions": False,
            "calls_external": [],
            "edge_cases": []
        }
        
        # Extract arguments
        for arg in node.args.args:
            arg_info = {"name": arg.arg, "annotation": None, "default": None}
            if arg.annotation:
                arg_info["annotation"] = ast.unparse(arg.annotation)
            func_info["args"].append(arg_info)
        
        # Add defaults
        defaults = node.args.defaults
        if defaults:
            for i, default in enumerate(defaults):
                arg_index = len(func_info["args"]) - len(defaults) + i
                if arg_index >= 0:
                    func_info["args"][arg_index]["default"] = ast.unparse(default)
        
        # Extract return annotation
        if node.returns:
            func_info["return_annotation"] = ast.unparse(node.returns)
        
        # Extract docstring
        if (node.body and isinstance(node.body[0], ast.Expr) and
            isinstance(node.body[0].value, ast.Constant) and
            isinstance(node.body[0].value.value, str)):
            func_info["docstring"] = node.body[0].value.value
        
        # Analyze complexity
        for child in ast.walk(node):
            if isinstance(child, (ast.If, ast.IfExp)):
                func_info["has_conditionals"] = True
            elif isinstance(child, (ast.For, ast.While)):
                func_info["has_loops"] = True
            elif isinstance(child, (ast.Try, ast.Raise)):
                func_info["has_exceptions"] = True
            elif isinstance(child, ast.Call):
                if isinstance(child.func, ast.Name):
                    func_info["calls_external"].append(child.func.id)
                elif isinstance(child.func, ast.Attribute):
                    func_info["calls_external"].append(ast.unparse(child.func))
        
        # Determine complexity
        complexity_score = (
            len(func_info["calls_external"]) +
            (2 if func_info["has_conditionals"] else 0) +
            (2 if func_info["has_loops"] else 0) +
            (1 if func_info["has_exceptions"] else 0)
        )
        
        if complexity_score > 5:
            func_info["complexity"] = "complex"
        elif complexity_score > 2:
            func_info["complexity"] = "moderate"
        
        # Generate edge cases based on arguments
        func_info["edge_cases"] = self._generate_edge_cases(func_info["args"])
        
        return func_info
    
    def _analyze_python_class(self, node: ast.ClassDef, source_code: str) -> Dict[str, Any]:
        """Analyze a Python class for test generation."""
        class_info = {
            "name": node.name,
            "methods": [],
            "properties": [],
            "inheritance": [],
            "docstring": None
        }
        
        # Extract inheritance
        for base in node.bases:
            class_info["inheritance"].append(ast.unparse(base))
        
        # Extract docstring
        if (node.body and isinstance(node.body[0], ast.Expr) and
            isinstance(node.body[0].value, ast.Constant) and
            isinstance(node.body[0].value.value, str)):
            class_info["docstring"] = node.body[0].value.value
        
        # Extract methods
        for item in node.body:
            if isinstance(item, ast.FunctionDef) and not item.name.startswith('_'):
                method_info = self._analyze_python_function(item, source_code)
                method_info["is_method"] = True
                class_info["methods"].append(method_info)
        
        return class_info
    
    def _analyze_javascript_code(self, source_code: str, file_path: str) -> Dict[str, Any]:
        """Analyze JavaScript/TypeScript code (simplified analysis)."""
        analysis = {
            "language": "javascript",
            "file_path": file_path,
            "functions": [],
            "classes": [],
            "imports": [],
            "dependencies": [],
            "constants": []
        }
        
        lines = source_code.split('\n')
        
        # Extract imports
        for line in lines:
            line = line.strip()
            if line.startswith('import ') or line.startswith('const ') and ' = require(' in line:
                analysis["imports"].append(line)
                # Extract dependency names (simplified)
                if 'from ' in line:
                    dep = line.split('from ')[-1].strip().strip('\'"')
                    if not dep.startswith('.'):
                        analysis["dependencies"].append(dep)
        
        # Extract functions (simplified regex-based approach)
        function_patterns = [
            r'function\s+(\w+)\s*\([^)]*\)',
            r'const\s+(\w+)\s*=\s*\([^)]*\)\s*=>',
            r'(\w+)\s*:\s*function\s*\([^)]*\)',
            r'(\w+)\s*\([^)]*\)\s*\{'
        ]
        
        for line_num, line in enumerate(lines):
            for pattern in function_patterns:
                match = re.search(pattern, line)
                if match:
                    func_name = match.group(1)
                    if not func_name.startswith('_'):
                        func_info = {
                            "name": func_name,
                            "args": [],  # Could be enhanced to parse args
                            "line_number": line_num + 1,
                            "complexity": "simple",
                            "edge_cases": []
                        }
                        analysis["functions"].append(func_info)
        
        # Extract classes
        for line_num, line in enumerate(lines):
            match = re.search(r'class\s+(\w+)', line)
            if match:
                class_name = match.group(1)
                class_info = {
                    "name": class_name,
                    "methods": [],
                    "line_number": line_num + 1
                }
                analysis["classes"].append(class_info)
        
        return analysis
    
    def _generate_edge_cases(self, args: List[Dict[str, Any]]) -> List[str]:
        """Generate edge cases based on function arguments."""
        edge_cases = []
        
        for arg in args:
            arg_name = arg["name"]
            annotation = arg.get("annotation", "")
            
            if "int" in annotation.lower() or "number" in annotation.lower():
                edge_cases.extend([f"{arg_name}=0", f"{arg_name}=-1", f"{arg_name}=sys.maxsize"])
            elif "str" in annotation.lower() or "string" in annotation.lower():
                edge_cases.extend([f'{arg_name}=""', f'{arg_name}="test"', f'{arg_name}=None'])
            elif "list" in annotation.lower() or "array" in annotation.lower():
                edge_cases.extend([f"{arg_name}=[]", f'{arg_name}=[1, 2, 3]', f"{arg_name}=None"])
            elif "dict" in annotation.lower() or "object" in annotation.lower():
                edge_cases.extend([f"{arg_name}={{}}", f'{arg_name}={{"key": "value"}}', f"{arg_name}=None"])
            elif "bool" in annotation.lower():
                edge_cases.extend([f"{arg_name}=True", f"{arg_name}=False"])
            else:
                edge_cases.extend([f"{arg_name}=None"])
        
        return edge_cases[:10]  # Limit to reasonable number
    
    def _detect_test_framework(self, file_path: str, file_ext: str) -> str:
        """Detect the appropriate test framework based on project context."""
        project_root = self._find_project_root(file_path)
        
        if file_ext == ".py":
            # Check for pytest.ini, setup.cfg, or pytest in requirements
            if os.path.exists(os.path.join(project_root, "pytest.ini")):
                return "pytest"
            
            # Check requirements files
            for req_file in ["requirements.txt", "requirements-dev.txt", "pyproject.toml"]:
                req_path = os.path.join(project_root, req_file)
                if os.path.exists(req_path):
                    try:
                        with open(req_path, 'r') as f:
                            content = f.read()
                            if "pytest" in content:
                                return "pytest"
                    except:
                        pass
            
            return "pytest"  # Default for Python
        
        elif file_ext in [".js", ".ts", ".jsx", ".tsx"]:
            # Check package.json for test framework
            package_json = os.path.join(project_root, "package.json")
            if os.path.exists(package_json):
                try:
                    with open(package_json, 'r') as f:
                        data = json.loads(f.read())
                        deps = {**data.get("dependencies", {}), **data.get("devDependencies", {})}
                        
                        if "vitest" in deps:
                            return "vitest"
                        elif "jest" in deps:
                            return "jest"
                        elif "mocha" in deps:
                            return "mocha"
                except:
                    pass
            
            return "jest"  # Default for JavaScript
        
        return "pytest"
    
    def _find_project_root(self, file_path: str) -> str:
        """Find the project root directory."""
        current_dir = os.path.dirname(os.path.abspath(file_path))
        
        while current_dir != os.path.dirname(current_dir):  # Not at filesystem root
            if any(os.path.exists(os.path.join(current_dir, marker)) for marker in 
                   [".git", "package.json", "pyproject.toml", "setup.py", "requirements.txt"]):
                return current_dir
            current_dir = os.path.dirname(current_dir)
        
        return os.path.dirname(os.path.abspath(file_path))
    
    def _generate_test_file_path(self, source_file: str, test_framework: str) -> str:
        """Generate appropriate test file path."""
        source_path = Path(source_file)
        project_root = self._find_project_root(source_file)
        
        if test_framework in ["pytest", "unittest"]:
            # Python convention: test_filename.py or tests/test_filename.py
            test_name = f"test_{source_path.stem}.py"
            
            # Check if tests directory exists
            tests_dir = os.path.join(project_root, "tests")
            if os.path.exists(tests_dir):
                return os.path.join(tests_dir, test_name)
            else:
                return os.path.join(source_path.parent, test_name)
        
        elif test_framework in ["jest", "vitest", "mocha"]:
            # JavaScript convention: filename.test.js or __tests__/filename.test.js
            test_name = f"{source_path.stem}.test{source_path.suffix}"
            
            # Check if __tests__ directory exists
            tests_dir = os.path.join(source_path.parent, "__tests__")
            if os.path.exists(tests_dir):
                return os.path.join(tests_dir, test_name)
            else:
                return os.path.join(source_path.parent, test_name)
        
        return f"test_{source_path.stem}{source_path.suffix}"
    
    def _generate_test_code(self, analysis: Dict[str, Any], test_framework: str,
                          test_types: List[str], coverage_target: str, mock_dependencies: bool) -> str:
        """Generate the actual test code."""
        if analysis["language"] == "python":
            return self._generate_python_tests(analysis, test_framework, test_types, coverage_target, mock_dependencies)
        elif analysis["language"] == "javascript":
            return self._generate_javascript_tests(analysis, test_framework, test_types, coverage_target, mock_dependencies)
        else:
            raise ValueError(f"Unsupported language: {analysis['language']}")
    
    def _generate_python_tests(self, analysis: Dict[str, Any], test_framework: str,
                             test_types: List[str], coverage_target: str, mock_dependencies: bool) -> str:
        """Generate Python test code."""
        source_file = analysis["file_path"]
        module_name = Path(source_file).stem
        
        # Build imports
        imports = []
        if test_framework == "pytest":
            imports.append("import pytest")
        elif test_framework == "unittest":
            imports.append("import unittest")
        
        if mock_dependencies:
            imports.append("from unittest.mock import Mock, patch, MagicMock")
        
        # Import the module being tested
        imports.append(f"from {module_name} import *")
        
        # Add any specific imports based on detected dependencies
        for dep in analysis["dependencies"]:
            if dep not in ["sys", "os", "json", "re"]:  # Skip standard library
                imports.append(f"# import {dep}  # May need mocking")
        
        test_code = "\n".join(imports) + "\n\n"
        
        # Generate tests for each function
        for func in analysis["functions"]:
            test_code += self._generate_function_tests(func, test_framework, test_types, coverage_target, mock_dependencies)
        
        # Generate tests for each class
        for cls in analysis["classes"]:
            test_code += self._generate_class_tests(cls, test_framework, test_types, coverage_target, mock_dependencies)
        
        return test_code
    
    def _generate_function_tests(self, func: Dict[str, Any], test_framework: str,
                               test_types: List[str], coverage_target: str, mock_dependencies: bool) -> str:
        """Generate tests for a single function."""
        func_name = func["name"]
        test_class_name = f"Test{func_name.capitalize()}"
        
        if test_framework == "pytest":
            tests = f"class {test_class_name}:\n"
            tests += f'    """Tests for {func_name}() function."""\n\n'
            
            # Basic functionality test
            if "unit" in test_types:
                tests += f"    def test_{func_name}_basic(self):\n"
                tests += f'        """Test basic functionality of {func_name}."""\n'
                tests += f"        # Arrange\n"
                
                # Generate sample arguments
                args_str = self._generate_sample_args(func["args"])
                tests += f"        {args_str}\n"
                tests += f"        \n"
                tests += f"        # Act\n"
                args_names = [arg["name"] for arg in func["args"]]
                call_args = ", ".join(args_names) if args_names else ""
                tests += f"        result = {func_name}({call_args})\n"
                tests += f"        \n"
                tests += f"        # Assert\n"
                tests += f"        assert result is not None  # Replace with specific assertion\n"
                tests += f"        # TODO: Add specific assertions based on expected behavior\n\n"
            
            # Edge cases
            if "edge_cases" in test_types and func["edge_cases"]:
                for i, edge_case in enumerate(func["edge_cases"][:5]):  # Limit to 5 edge cases
                    tests += f"    def test_{func_name}_edge_case_{i+1}(self):\n"
                    tests += f'        """Test edge case: {edge_case}."""\n'
                    tests += f"        # Test with {edge_case}\n"
                    tests += f"        result = {func_name}({edge_case})\n"
                    tests += f"        # TODO: Add appropriate assertions\n"
                    tests += f"        assert True  # Replace with actual assertion\n\n"
            
            # Error handling
            if "error_handling" in test_types:
                tests += f"    def test_{func_name}_error_handling(self):\n"
                tests += f'        """Test error handling in {func_name}."""\n'
                tests += f"        with pytest.raises(Exception):  # Replace with specific exception\n"
                tests += f"            {func_name}(None)  # Or other invalid input\n"
                tests += f"        # TODO: Add specific error condition tests\n\n"
            
            # Mock external calls if needed
            if mock_dependencies and func["calls_external"]:
                for ext_call in func["calls_external"][:3]:  # Limit to 3 mocks
                    tests += f"    @patch('{ext_call}')\n"
                    tests += f"    def test_{func_name}_with_mock_{ext_call.lower()}(self, mock_{ext_call.lower()}):\n"
                    tests += f'        """Test {func_name} with mocked {ext_call}."""\n'
                    tests += f"        # Configure mock\n"
                    tests += f"        mock_{ext_call.lower()}.return_value = None  # Set expected return\n"
                    tests += f"        \n"
                    args_str = self._generate_sample_args(func["args"])
                    tests += f"        {args_str}\n"
                    args_names = [arg["name"] for arg in func["args"]]
                    call_args = ", ".join(args_names) if args_names else ""
                    tests += f"        result = {func_name}({call_args})\n"
                    tests += f"        \n"
                    tests += f"        # Assert mock was called and result is correct\n"
                    tests += f"        mock_{ext_call.lower()}.assert_called_once()\n"
                    tests += f"        assert result is not None  # Replace with specific assertion\n\n"
        
        elif test_framework == "unittest":
            tests = f"class {test_class_name}(unittest.TestCase):\n"
            tests += f'    """Tests for {func_name}() function."""\n\n'
            
            tests += f"    def test_{func_name}_basic(self):\n"
            tests += f'        """Test basic functionality of {func_name}."""\n'
            args_str = self._generate_sample_args(func["args"])
            tests += f"        {args_str}\n"
            args_names = [arg["name"] for arg in func["args"]]
            call_args = ", ".join(args_names) if args_names else ""
            tests += f"        result = {func_name}({call_args})\n"
            tests += f"        self.assertIsNotNone(result)  # Replace with specific assertion\n\n"
        
        return tests
    
    def _generate_class_tests(self, cls: Dict[str, Any], test_framework: str,
                            test_types: List[str], coverage_target: str, mock_dependencies: bool) -> str:
        """Generate tests for a class."""
        cls_name = cls["name"]
        test_class_name = f"Test{cls_name}"
        
        tests = f"class {test_class_name}:\n" if test_framework == "pytest" else f"class {test_class_name}(unittest.TestCase):\n"
        tests += f'    """Tests for {cls_name} class."""\n\n'
        
        # Setup method
        if test_framework == "pytest":
            tests += f"    def setup_method(self):\n"
            tests += f'        """Set up test fixtures before each test method."""\n'
        else:
            tests += f"    def setUp(self):\n"
            tests += f'        """Set up test fixtures before each test method."""\n'
        
        tests += f"        self.instance = {cls_name}()  # Adjust constructor args as needed\n\n"
        
        # Test each method
        for method in cls["methods"]:
            method_name = method["name"]
            tests += f"    def test_{method_name}(self):\n"
            tests += f'        """Test {method_name} method."""\n'
            tests += f"        # TODO: Implement test for {method_name}\n"
            tests += f"        result = self.instance.{method_name}()\n"
            tests += f"        assert result is not None  # Replace with specific assertion\n\n"
        
        return tests
    
    def _generate_sample_args(self, args: List[Dict[str, Any]]) -> str:
        """Generate sample argument assignments for test setup."""
        if not args:
            return "        # No arguments needed"
        
        lines = []
        for arg in args:
            arg_name = arg["name"]
            annotation = arg.get("annotation", "")
            default = arg.get("default")
            
            if default:
                lines.append(f"        {arg_name} = {default}")
            elif "int" in annotation.lower():
                lines.append(f"        {arg_name} = 42")
            elif "str" in annotation.lower():
                lines.append(f'        {arg_name} = "test_value"')
            elif "list" in annotation.lower():
                lines.append(f"        {arg_name} = [1, 2, 3]")
            elif "dict" in annotation.lower():
                lines.append(f'        {arg_name} = {{"key": "value"}}')
            elif "bool" in annotation.lower():
                lines.append(f"        {arg_name} = True")
            else:
                lines.append(f'        {arg_name} = "test_{arg_name}"')
        
        return "\n".join(lines)
    
    def _generate_javascript_tests(self, analysis: Dict[str, Any], test_framework: str,
                                 test_types: List[str], coverage_target: str, mock_dependencies: bool) -> str:
        """Generate JavaScript test code."""
        source_file = analysis["file_path"]
        module_name = Path(source_file).stem
        
        # Build imports
        imports = []
        if test_framework == "jest":
            imports.append(f"const {{{', '.join([f['name'] for f in analysis['functions']])}}} = require('./{module_name}');")
        elif test_framework == "vitest":
            imports.append("import { describe, it, expect } from 'vitest';")
            imports.append(f"import {{ {', '.join([f['name'] for f in analysis['functions']])} }} from './{module_name}';")
        
        test_code = "\n".join(imports) + "\n\n"
        
        # Generate test suites
        for func in analysis["functions"]:
            func_name = func["name"]
            test_code += f"describe('{func_name}', () => {{\n"
            test_code += f"  it('should work with basic input', () => {{\n"
            test_code += f"    // Arrange\n"
            test_code += f"    const input = 'test';  // Adjust based on function signature\n"
            test_code += f"    \n"
            test_code += f"    // Act\n"
            test_code += f"    const result = {func_name}(input);\n"
            test_code += f"    \n"
            test_code += f"    // Assert\n"
            test_code += f"    expect(result).toBeDefined();\n"
            test_code += f"    // TODO: Add specific assertions\n"
            test_code += f"  }});\n"
            test_code += f"  \n"
            test_code += f"  it('should handle edge cases', () => {{\n"
            test_code += f"    // TODO: Add edge case tests\n"
            test_code += f"    expect(() => {func_name}(null)).not.toThrow();\n"
            test_code += f"  }});\n"
            test_code += f"}});\n\n"
        
        return test_code
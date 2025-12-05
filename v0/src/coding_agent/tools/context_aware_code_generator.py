"""Context-aware code generation tool that adapts to existing codebase patterns."""

import ast
import re
import os
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple, Set
from collections import defaultdict, Counter
from .base import Tool
from ..types import ToolResult
from ..providers.base import ModelProvider


class CodebasePatternAnalyzer(ast.NodeVisitor):
    """Analyze codebase to extract patterns and conventions."""
    
    def __init__(self):
        self.patterns = {
            'naming_conventions': {
                'functions': [],
                'classes': [],
                'variables': [],
                'constants': []
            },
            'architectural_patterns': {
                'class_hierarchies': {},
                'common_imports': Counter(),
                'design_patterns': [],
                'error_handling': [],
                'logging_patterns': []
            },
            'style_conventions': {
                'docstring_style': None,
                'type_hints': False,
                'async_usage': False,
                'exception_types': Counter(),
                'return_patterns': []
            },
            'framework_patterns': {
                'frameworks': set(),
                'common_decorators': Counter(),
                'base_classes': Counter(),
                'interface_patterns': []
            }
        }
    
    def analyze_codebase(self, files_content: Dict[str, str]) -> Dict[str, Any]:
        """Analyze multiple files to extract patterns."""
        for file_path, content in files_content.items():
            try:
                tree = ast.parse(content)
                self.current_file = file_path
                self.visit(tree)
            except (SyntaxError, UnicodeDecodeError):
                continue
        
        return self._consolidate_patterns()
    
    def visit_Import(self, node):
        """Track import patterns."""
        for alias in node.names:
            self.patterns['architectural_patterns']['common_imports'][alias.name] += 1
    
    def visit_ImportFrom(self, node):
        """Track from-import patterns."""
        if node.module:
            self.patterns['architectural_patterns']['common_imports'][node.module] += 1
            
            # Detect frameworks
            framework_indicators = {
                'flask': 'Flask',
                'django': 'Django',
                'fastapi': 'FastAPI',
                'sqlalchemy': 'SQLAlchemy',
                'pytest': 'Pytest',
                'unittest': 'unittest',
                'asyncio': 'AsyncIO',
                'pydantic': 'Pydantic'
            }
            
            for framework, name in framework_indicators.items():
                if framework in node.module.lower():
                    self.patterns['framework_patterns']['frameworks'].add(name)
    
    def visit_FunctionDef(self, node):
        """Analyze function patterns."""
        # Naming conventions
        self.patterns['naming_conventions']['functions'].append(node.name)
        
        # Docstring style
        if node.body and isinstance(node.body[0], ast.Expr) and isinstance(node.body[0].value, ast.Constant):
            docstring = node.body[0].value.value
            if isinstance(docstring, str):
                self._analyze_docstring_style(docstring)
        
        # Type hints
        if node.returns or any(arg.annotation for arg in node.args.args):
            self.patterns['style_conventions']['type_hints'] = True
        
        # Decorators
        for decorator in node.decorator_list:
            if isinstance(decorator, ast.Name):
                self.patterns['framework_patterns']['common_decorators'][decorator.id] += 1
        
        # Error handling patterns
        for stmt in ast.walk(node):
            if isinstance(stmt, ast.Try):
                self._analyze_error_handling(stmt)
        
        self.generic_visit(node)
    
    def visit_AsyncFunctionDef(self, node):
        """Track async patterns."""
        self.patterns['style_conventions']['async_usage'] = True
        self.visit_FunctionDef(node)
    
    def visit_ClassDef(self, node):
        """Analyze class patterns."""
        # Naming conventions
        self.patterns['naming_conventions']['classes'].append(node.name)
        
        # Base classes
        for base in node.bases:
            if isinstance(base, ast.Name):
                self.patterns['framework_patterns']['base_classes'][base.id] += 1
        
        # Class hierarchy
        if node.bases:
            base_names = [base.id for base in node.bases if isinstance(base, ast.Name)]
            self.patterns['architectural_patterns']['class_hierarchies'][node.name] = base_names
        
        self.generic_visit(node)
    
    def visit_Assign(self, node):
        """Analyze variable assignment patterns."""
        for target in node.targets:
            if isinstance(target, ast.Name):
                name = target.id
                # Detect constants (all caps)
                if name.isupper():
                    self.patterns['naming_conventions']['constants'].append(name)
                else:
                    self.patterns['naming_conventions']['variables'].append(name)
    
    def _analyze_docstring_style(self, docstring: str):
        """Analyze docstring style patterns."""
        if '"""' in docstring:
            if docstring.count('\n') > 2 and 'Args:' in docstring:
                self.patterns['style_conventions']['docstring_style'] = 'google'
            elif 'Parameters' in docstring and '----------' in docstring:
                self.patterns['style_conventions']['docstring_style'] = 'numpy'
            else:
                self.patterns['style_conventions']['docstring_style'] = 'basic'
    
    def _analyze_error_handling(self, try_node: ast.Try):
        """Analyze error handling patterns."""
        for handler in try_node.handlers:
            if handler.type:
                if isinstance(handler.type, ast.Name):
                    self.patterns['style_conventions']['exception_types'][handler.type.id] += 1
    
    def _consolidate_patterns(self) -> Dict[str, Any]:
        """Consolidate and analyze collected patterns."""
        consolidated = {}
        
        # Naming conventions analysis
        consolidated['naming'] = {
            'function_style': self._analyze_naming_style(self.patterns['naming_conventions']['functions']),
            'class_style': self._analyze_naming_style(self.patterns['naming_conventions']['classes'], is_class=True),
            'variable_style': self._analyze_naming_style(self.patterns['naming_conventions']['variables'])
        }
        
        # Most common patterns
        consolidated['common_imports'] = dict(self.patterns['architectural_patterns']['common_imports'].most_common(10))
        consolidated['common_decorators'] = dict(self.patterns['framework_patterns']['common_decorators'].most_common(5))
        consolidated['common_bases'] = dict(self.patterns['framework_patterns']['base_classes'].most_common(5))
        consolidated['frameworks'] = list(self.patterns['framework_patterns']['frameworks'])
        
        # Style preferences
        consolidated['style'] = {
            'docstring_style': self.patterns['style_conventions']['docstring_style'],
            'uses_type_hints': self.patterns['style_conventions']['type_hints'],
            'uses_async': self.patterns['style_conventions']['async_usage'],
            'common_exceptions': dict(self.patterns['style_conventions']['exception_types'].most_common(5))
        }
        
        return consolidated
    
    def _analyze_naming_style(self, names: List[str], is_class: bool = False) -> str:
        """Analyze naming style patterns."""
        if not names:
            return 'unknown'
        
        snake_case_count = sum(1 for name in names if '_' in name and name.islower())
        camel_case_count = sum(1 for name in names if any(c.isupper() for c in name[1:]) and '_' not in name)
        pascal_case_count = sum(1 for name in names if name[0].isupper() and any(c.isupper() for c in name[1:]))
        
        if is_class:
            return 'PascalCase' if pascal_case_count > len(names) * 0.7 else 'mixed'
        else:
            if snake_case_count > len(names) * 0.7:
                return 'snake_case'
            elif camel_case_count > len(names) * 0.7:
                return 'camelCase'
            else:
                return 'mixed'


class ContextAwareCodeGenerator(Tool):
    """Generate code that follows existing codebase patterns and conventions."""
    
    def __init__(self, model_provider: Optional[ModelProvider] = None):
        self.model_provider = model_provider
        self.patterns_cache = {}
    
    @property
    def name(self) -> str:
        return "context_aware_code_generator"
    
    @property
    def description(self) -> str:
        return "Generate code that follows existing codebase patterns, conventions, and architectural styles"
    
    @property
    def parameters_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "code_type": {
                    "type": "string",
                    "enum": ["function", "class", "module", "test", "api_endpoint", "data_model", "utility"],
                    "description": "Type of code to generate"
                },
                "description": {
                    "type": "string",
                    "description": "Description of what the code should do"
                },
                "context_path": {
                    "type": "string",
                    "default": ".",
                    "description": "Path to analyze for context patterns"
                },
                "similar_code": {
                    "type": "string",
                    "description": "Path to similar existing code to use as reference"
                },
                "integration_point": {
                    "type": "string",
                    "description": "Where this code will be integrated (file path or class name)"
                },
                "requirements": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Specific requirements or constraints"
                },
                "style_preferences": {
                    "type": "object",
                    "properties": {
                        "docstring_style": {"type": "string", "enum": ["google", "numpy", "basic"]},
                        "use_type_hints": {"type": "boolean"},
                        "use_async": {"type": "boolean"},
                        "error_handling": {"type": "string", "enum": ["exceptions", "return_codes", "optional"]}
                    },
                    "description": "Override default style preferences"
                },
                "output_file": {
                    "type": "string",
                    "description": "File path to write generated code (optional)"
                },
                "generate_tests": {
                    "type": "boolean",
                    "default": False,
                    "description": "Also generate corresponding tests"
                }
            },
            "required": ["code_type", "description"]
        }
    
    @property
    def is_destructive(self) -> bool:
        return True  # Can write files
    
    def _get_files_for_analysis(self, context_path: str) -> Dict[str, str]:
        """Get files to analyze for context patterns."""
        files_content = {}
        context_path_obj = Path(context_path)
        
        if not context_path_obj.exists():
            return {}
        
        # Get Python files for analysis
        if context_path_obj.is_file():
            files_to_analyze = [context_path_obj]
        else:
            files_to_analyze = list(context_path_obj.rglob("*.py"))[:50]  # Limit to avoid performance issues
        
        for file_path in files_to_analyze:
            try:
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
                if content.strip():  # Skip empty files
                    files_content[str(file_path)] = content
            except Exception:
                continue
        
        return files_content
    
    def _analyze_codebase_patterns(self, context_path: str) -> Dict[str, Any]:
        """Analyze codebase to extract patterns."""
        # Check cache first
        cache_key = str(Path(context_path).resolve())
        if cache_key in self.patterns_cache:
            return self.patterns_cache[cache_key]
        
        files_content = self._get_files_for_analysis(context_path)
        if not files_content:
            return {}
        
        analyzer = CodebasePatternAnalyzer()
        patterns = analyzer.analyze_codebase(files_content)
        
        # Cache results
        self.patterns_cache[cache_key] = patterns
        return patterns
    
    def _get_similar_code_context(self, similar_code_path: str) -> Dict[str, Any]:
        """Analyze similar existing code for reference."""
        if not similar_code_path:
            return {}
        
        path = Path(similar_code_path)
        if not path.exists():
            return {}
        
        try:
            with open(path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            tree = ast.parse(content)
            
            # Extract key patterns from the similar code
            context = {
                'imports': [],
                'functions': [],
                'classes': [],
                'patterns': []
            }
            
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        context['imports'].append(alias.name)
                elif isinstance(node, ast.ImportFrom) and node.module:
                    context['imports'].append(node.module)
                elif isinstance(node, ast.FunctionDef):
                    func_info = {
                        'name': node.name,
                        'args': [arg.arg for arg in node.args.args],
                        'has_docstring': bool(node.body and isinstance(node.body[0], ast.Expr)),
                        'decorators': [d.id for d in node.decorator_list if isinstance(d, ast.Name)]
                    }
                    context['functions'].append(func_info)
                elif isinstance(node, ast.ClassDef):
                    class_info = {
                        'name': node.name,
                        'bases': [base.id for base in node.bases if isinstance(base, ast.Name)],
                        'methods': [n.name for n in node.body if isinstance(n, ast.FunctionDef)]
                    }
                    context['classes'].append(class_info)
            
            return context
        
        except Exception:
            return {}
    
    def _generate_code_prompt(self, code_type: str, description: str, patterns: Dict[str, Any], 
                            similar_context: Dict[str, Any], requirements: List[str], 
                            style_preferences: Dict[str, Any]) -> str:
        """Generate prompt for code generation."""
        
        # Base prompt
        prompt_parts = [
            f"Generate {code_type} code that follows the existing codebase patterns and conventions.",
            f"\nDescription: {description}",
        ]
        
        # Add requirements
        if requirements:
            prompt_parts.append(f"\nRequirements:")
            for req in requirements:
                prompt_parts.append(f"- {req}")
        
        # Add codebase patterns context
        if patterns:
            prompt_parts.append(f"\nExisting Codebase Patterns:")
            
            if patterns.get('naming'):
                naming = patterns['naming']
                prompt_parts.append(f"- Function naming: {naming.get('function_style', 'unknown')}")
                prompt_parts.append(f"- Class naming: {naming.get('class_style', 'unknown')}")
                prompt_parts.append(f"- Variable naming: {naming.get('variable_style', 'unknown')}")
            
            if patterns.get('common_imports'):
                imports = list(patterns['common_imports'].keys())[:5]
                prompt_parts.append(f"- Common imports: {', '.join(imports)}")
            
            if patterns.get('frameworks'):
                prompt_parts.append(f"- Frameworks used: {', '.join(patterns['frameworks'])}")
            
            if patterns.get('style'):
                style = patterns['style']
                if style.get('docstring_style'):
                    prompt_parts.append(f"- Docstring style: {style['docstring_style']}")
                if style.get('uses_type_hints'):
                    prompt_parts.append(f"- Uses type hints: {style['uses_type_hints']}")
                if style.get('uses_async'):
                    prompt_parts.append(f"- Uses async/await: {style['uses_async']}")
        
        # Add similar code context
        if similar_context:
            prompt_parts.append(f"\nReference code patterns:")
            if similar_context.get('functions'):
                func_names = [f['name'] for f in similar_context['functions'][:3]]
                prompt_parts.append(f"- Similar function names: {', '.join(func_names)}")
            if similar_context.get('imports'):
                imports = similar_context['imports'][:5]
                prompt_parts.append(f"- Imports to consider: {', '.join(imports)}")
        
        # Add style preferences
        if style_preferences:
            prompt_parts.append(f"\nStyle preferences:")
            for key, value in style_preferences.items():
                if value is not None:
                    prompt_parts.append(f"- {key}: {value}")
        
        # Add generation instructions
        prompt_parts.extend([
            f"\nGenerate complete, production-ready {code_type} code that:",
            "- Follows the identified patterns and conventions",
            "- Includes appropriate error handling",
            "- Has clear, consistent documentation",
            "- Is well-structured and maintainable",
            "- Integrates seamlessly with the existing codebase",
            "",
            "Provide only the code without explanations unless specifically requested."
        ])
        
        return "\n".join(prompt_parts)
    
    def _generate_test_prompt(self, generated_code: str, code_type: str) -> str:
        """Generate prompt for test code generation."""
        return f"""
Generate comprehensive tests for the following {code_type} code:

```python
{generated_code}
```

Requirements:
- Use the testing framework commonly used in this codebase
- Cover happy path, edge cases, and error conditions
- Follow existing test naming and organization patterns
- Include appropriate fixtures and mocks if needed
- Ensure good test coverage

Provide complete test code that can be run immediately.
"""
    
    def execute(self, **parameters) -> ToolResult:
        """Execute context-aware code generation."""
        try:
            code_type = parameters.get("code_type")
            description = parameters.get("description")
            context_path = parameters.get("context_path", ".")
            similar_code = parameters.get("similar_code")
            integration_point = parameters.get("integration_point")
            requirements = parameters.get("requirements", [])
            style_preferences = parameters.get("style_preferences", {})
            output_file = parameters.get("output_file")
            generate_tests = parameters.get("generate_tests", False)
            
            if not self.model_provider:
                return ToolResult(
                    success=False,
                    error="Model provider required for code generation"
                )
            
            # Analyze codebase patterns
            patterns = self._analyze_codebase_patterns(context_path)
            
            # Get similar code context if provided
            similar_context = self._get_similar_code_context(similar_code) if similar_code else {}
            
            # Generate code prompt
            prompt = self._generate_code_prompt(
                code_type, description, patterns, similar_context, 
                requirements, style_preferences
            )
            
            # Generate code
            response = self.model_provider.generate(prompt, max_tokens=2000)
            if not response or not response.content:
                return ToolResult(
                    success=False,
                    error="Failed to generate code"
                )
            
            generated_code = response.content.strip()
            
            # Extract code from markdown if present
            if "```python" in generated_code:
                start = generated_code.find("```python") + 9
                end = generated_code.find("```", start)
                if end != -1:
                    generated_code = generated_code[start:end].strip()
            elif "```" in generated_code:
                start = generated_code.find("```") + 3
                end = generated_code.find("```", start)
                if end != -1:
                    generated_code = generated_code[start:end].strip()
            
            result_parts = [f"Generated {code_type} code:\n"]
            result_parts.append("```python")
            result_parts.append(generated_code)
            result_parts.append("```")
            
            # Generate tests if requested
            test_code = None
            if generate_tests:
                test_prompt = self._generate_test_prompt(generated_code, code_type)
                test_response = self.model_provider.generate(test_prompt, max_tokens=1500)
                
                if test_response and test_response.content:
                    test_code = test_response.content.strip()
                    
                    # Extract test code from markdown
                    if "```python" in test_code:
                        start = test_code.find("```python") + 9
                        end = test_code.find("```", start)
                        if end != -1:
                            test_code = test_code[start:end].strip()
                    
                    result_parts.append(f"\nGenerated test code:\n")
                    result_parts.append("```python")
                    result_parts.append(test_code)
                    result_parts.append("```")
            
            # Write to file if requested
            if output_file:
                try:
                    output_path = Path(output_file)
                    output_path.parent.mkdir(parents=True, exist_ok=True)
                    
                    with open(output_path, 'w', encoding='utf-8') as f:
                        f.write(generated_code)
                    
                    result_parts.append(f"\n✅ Code written to: {output_file}")
                    
                    # Write test file if tests were generated
                    if test_code:
                        test_file = output_path.parent / f"test_{output_path.name}"
                        with open(test_file, 'w', encoding='utf-8') as f:
                            f.write(test_code)
                        result_parts.append(f"✅ Tests written to: {test_file}")
                
                except Exception as e:
                    result_parts.append(f"\n⚠️ Failed to write file: {str(e)}")
            
            # Add pattern analysis summary
            if patterns:
                result_parts.append(f"\n📊 **Codebase Analysis Summary:**")
                if patterns.get('frameworks'):
                    result_parts.append(f"   • Frameworks detected: {', '.join(patterns['frameworks'])}")
                if patterns.get('naming'):
                    naming = patterns['naming']
                    result_parts.append(f"   • Naming style: {naming.get('function_style', 'mixed')} functions, {naming.get('class_style', 'mixed')} classes")
                if patterns.get('style'):
                    style = patterns['style']
                    features = []
                    if style.get('uses_type_hints'):
                        features.append("type hints")
                    if style.get('uses_async'):
                        features.append("async/await")
                    if style.get('docstring_style'):
                        features.append(f"{style['docstring_style']} docstrings")
                    if features:
                        result_parts.append(f"   • Style features: {', '.join(features)}")
            
            return ToolResult(
                success=True,
                output="\n".join(result_parts),
                action_description=f"Generated {code_type} code following codebase patterns"
            )
        
        except Exception as e:
            return ToolResult(
                success=False,
                error=f"Code generation error: {str(e)}"
            )
"""Code generation tools for creating boilerplate, templates, and scaffolding."""

import os
import re
from typing import Dict, Any, List, Optional
from pathlib import Path
from .base import Tool
from ..types import ToolResult
from ..providers.base import ModelProvider


class CodeGeneratorTool(Tool):
    """Tool for generating code from templates, boilerplate, and LLM-powered scaffolding."""
    
    def __init__(self, model_provider: Optional[ModelProvider] = None):
        self.model_provider = model_provider
    
    @property
    def name(self) -> str:
        return "generate_code"
    
    @property
    def description(self) -> str:
        return "Generate code files, boilerplate, templates, or scaffolding using predefined templates or LLM assistance"
    
    @property
    def parameters_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "template": {
                    "type": "string",
                    "enum": ["class", "function", "api_endpoint", "react_component", "test_file", "config", "custom"],
                    "description": "Type of code to generate"
                },
                "language": {
                    "type": "string",
                    "enum": ["python", "javascript", "typescript", "java", "go", "rust", "cpp"],
                    "description": "Programming language for generated code"
                },
                "name": {
                    "type": "string", 
                    "description": "Name of the class, function, component, or file"
                },
                "file_path": {
                    "type": "string",
                    "description": "Path where the generated code should be saved"
                },
                "description": {
                    "type": "string",
                    "description": "Detailed description of what the code should do (for LLM generation)"
                },
                "parameters": {
                    "type": "object",
                    "description": "Additional parameters for template customization",
                    "properties": {
                        "base_class": {"type": "string"},
                        "methods": {"type": "array", "items": {"type": "string"}},
                        "imports": {"type": "array", "items": {"type": "string"}},
                        "framework": {"type": "string"},
                        "async": {"type": "boolean"}
                    }
                }
            },
            "required": ["template", "language", "name"]
        }
    
    @property
    def is_destructive(self) -> bool:
        return True  # Creates new files
    
    def execute(self, **parameters) -> ToolResult:
        """Generate code based on template type and parameters."""
        template = parameters.get("template")
        language = parameters.get("language")
        name = parameters.get("name")
        file_path = parameters.get("file_path")
        description = parameters.get("description", "")
        template_params = parameters.get("parameters", {})
        
        try:
            # Generate code based on template type
            if template == "custom" and description:
                # Use LLM for custom code generation
                if not self.model_provider or not self.model_provider.is_available():
                    return ToolResult(
                        success=False,
                        output=None,
                        error="LLM provider not available for custom code generation"
                    )
                generated_code = self._generate_custom_code(language, name, description, template_params)
            else:
                # Use predefined templates
                generated_code = self._generate_template_code(template, language, name, template_params)
            
            if not generated_code:
                return ToolResult(
                    success=False,
                    output=None,
                    error=f"Failed to generate {template} code for {language}"
                )
            
            # Determine file path if not provided
            if not file_path:
                file_path = self._determine_file_path(template, language, name)
            
            # Optionally write to file
            if file_path:
                try:
                    # Ensure directory exists
                    os.makedirs(os.path.dirname(file_path), exist_ok=True)
                    
                    with open(file_path, 'w', encoding='utf-8') as f:
                        f.write(generated_code)
                    
                    return ToolResult(
                        success=True,
                        output=f"Generated {template} code:\n\n{generated_code}",
                        action_description=f"Generated {template} code and saved to {file_path}"
                    )
                except Exception as e:
                    return ToolResult(
                        success=True,  # Code was generated successfully
                        output=f"Generated {template} code:\n\n{generated_code}\n\nNote: Could not save to {file_path}: {str(e)}",
                        action_description=f"Generated {template} code (file save failed)"
                    )
            else:
                return ToolResult(
                    success=True,
                    output=f"Generated {template} code:\n\n{generated_code}",
                    action_description=f"Generated {template} code"
                )
                
        except Exception as e:
            return ToolResult(
                success=False,
                output=None,
                error=f"Error generating code: {str(e)}"
            )
    
    def _generate_custom_code(self, language: str, name: str, description: str, params: dict) -> str:
        """Generate custom code using LLM."""
        prompt = self._build_generation_prompt(language, name, description, params)
        response = self.model_provider.generate(prompt)
        
        if not response.content.strip():
            return None
        
        # Extract code from LLM response
        return self._extract_code_from_response(response.content.strip(), language)
    
    def _generate_template_code(self, template: str, language: str, name: str, params: dict) -> str:
        """Generate code using predefined templates."""
        if language == "python":
            return self._generate_python_template(template, name, params)
        elif language in ["javascript", "typescript"]:
            return self._generate_js_template(template, name, params, language == "typescript")
        elif language == "java":
            return self._generate_java_template(template, name, params)
        else:
            # For other languages, fall back to LLM if available
            if self.model_provider and self.model_provider.is_available():
                description = f"Create a {template} named {name} in {language}"
                return self._generate_custom_code(language, name, description, params)
            return None
    
    def _generate_python_template(self, template: str, name: str, params: dict) -> str:
        """Generate Python code templates."""
        if template == "class":
            base_class = params.get("base_class", "")
            methods = params.get("methods", [])
            imports = params.get("imports", [])
            
            code = ""
            if imports:
                code += "\n".join(f"from {imp}" for imp in imports if imp) + "\n\n"
            
            inheritance = f"({base_class})" if base_class else ""
            code += f"class {name}{inheritance}:\n"
            code += f'    """Class {name}."""\n\n'
            
            if not methods:
                code += "    def __init__(self):\n"
                code += "        pass\n"
            else:
                for method in methods:
                    if method:
                        code += f"    def {method}(self):\n"
                        code += f'        """Method {method}."""\n'
                        code += "        pass\n\n"
            
            return code
            
        elif template == "function":
            is_async = params.get("async", False)
            func_prefix = "async def" if is_async else "def"
            
            return f'{func_prefix} {name}():\n    """Function {name}."""\n    pass\n'
            
        elif template == "api_endpoint":
            framework = params.get("framework", "flask")
            if framework == "flask":
                return f'''from flask import Flask, jsonify, request

app = Flask(__name__)

@app.route('/{name}', methods=['GET', 'POST'])
def {name}():
    """API endpoint for {name}."""
    if request.method == 'GET':
        return jsonify({{"message": "GET {name}"}})
    elif request.method == 'POST':
        return jsonify({{"message": "POST {name}"}})

if __name__ == '__main__':
    app.run(debug=True)
'''
            
        elif template == "test_file":
            return f'''import unittest

class Test{name.title()}(unittest.TestCase):
    """Test cases for {name}."""
    
    def setUp(self):
        """Set up test fixtures."""
        pass
    
    def test_{name.lower()}_basic(self):
        """Test basic {name} functionality."""
        self.assertTrue(True)
    
    def tearDown(self):
        """Clean up after tests."""
        pass

if __name__ == '__main__':
    unittest.main()
'''
        
        return None
    
    def _generate_js_template(self, template: str, name: str, params: dict, is_typescript: bool) -> str:
        """Generate JavaScript/TypeScript code templates."""
        type_annotation = ": void" if is_typescript else ""
        
        if template == "function":
            is_async = params.get("async", False)
            func_prefix = "async function" if is_async else "function"
            return f'{func_prefix} {name}(){type_annotation} {{\\n    // Function {name}\\n}}\\n'
            
        elif template == "react_component":
            if is_typescript:
                return f'''import React from 'react';

interface {name}Props {{
    // Define props here
}}

const {name}: React.FC<{name}Props> = (props) => {{
    return (
        <div>
            <h1>{name} Component</h1>
        </div>
    );
}};

export default {name};
'''
            else:
                return f'''import React from 'react';

const {name} = (props) => {{
    return (
        <div>
            <h1>{name} Component</h1>
        </div>
    );
}};

export default {name};
'''
                
        elif template == "api_endpoint":
            return f'''const express = require('express');
const app = express();

app.use(express.json());

app.get('/{name.lower()}', (req, res) => {{
    res.json({{ message: 'GET {name}' }});
}});

app.post('/{name.lower()}', (req, res) => {{
    res.json({{ message: 'POST {name}', data: req.body }});
}});

const PORT = process.env.PORT || 3000;
app.listen(PORT, () => {{
    console.log(`Server running on port ${{PORT}}`);
}});
'''
        
        return None
    
    def _generate_java_template(self, template: str, name: str, params: dict) -> str:
        """Generate Java code templates."""
        if template == "class":
            base_class = params.get("base_class", "")
            methods = params.get("methods", [])
            
            inheritance = f" extends {base_class}" if base_class else ""
            code = f"public class {name}{inheritance} {{\n"
            
            # Constructor
            code += f"    public {name}() {{\n"
            code += "        // Constructor\n"
            code += "    }\n\n"
            
            # Methods
            for method in methods:
                if method:
                    code += f"    public void {method}() {{\n"
                    code += f"        // Method {method}\n"
                    code += "    }\n\n"
            
            code += "}\n"
            return code
            
        elif template == "function":
            return f"public static void {name}() {{\n    // Method {name}\n}}\n"
        
        return None
    
    def _build_generation_prompt(self, language: str, name: str, description: str, params: dict) -> str:
        """Build prompt for LLM code generation."""
        prompt = f"Generate {language} code for: {description}\n\n"
        prompt += f"Requirements:\n"
        prompt += f"- Name: {name}\n"
        prompt += f"- Language: {language}\n"
        
        if params.get("framework"):
            prompt += f"- Framework: {params['framework']}\n"
        if params.get("async"):
            prompt += f"- Use async/await patterns\n"
        if params.get("base_class"):
            prompt += f"- Inherit from: {params['base_class']}\n"
        if params.get("methods"):
            prompt += f"- Include methods: {', '.join(params['methods'])}\n"
        if params.get("imports"):
            prompt += f"- Required imports: {', '.join(params['imports'])}\n"
        
        prompt += "\nGenerate clean, well-documented code with appropriate comments."
        prompt += "\nReturn ONLY the code, no explanations or markdown formatting."
        
        return prompt
    
    def _extract_code_from_response(self, response: str, language: str) -> str:
        """Extract clean code from LLM response."""
        # Remove markdown code blocks if present
        response = re.sub(f'```{language}\\n', '', response, flags=re.IGNORECASE)
        response = re.sub('```\\n?', '', response)
        response = re.sub('```', '', response)
        
        # Remove common prefixes
        response = re.sub(r'^(Here\'s|Here is).*?:\\n', '', response, flags=re.IGNORECASE | re.MULTILINE)
        
        return response.strip()
    
    def _determine_file_path(self, template: str, language: str, name: str) -> str:
        """Determine appropriate file path for generated code."""
        extensions = {
            "python": ".py",
            "javascript": ".js", 
            "typescript": ".ts",
            "java": ".java",
            "go": ".go",
            "rust": ".rs",
            "cpp": ".cpp"
        }
        
        ext = extensions.get(language, ".txt")
        
        if template == "test_file":
            return f"tests/test_{name.lower()}{ext}"
        elif template == "react_component":
            return f"src/components/{name}{extensions.get('typescript', '.js') if language == 'typescript' else '.js'}"
        elif template == "api_endpoint":
            return f"src/{name.lower()}{ext}"
        else:
            return f"src/{name.lower()}{ext}"
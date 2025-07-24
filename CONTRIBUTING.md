# Contributing to Coding Agent

Thank you for your interest in contributing to the Open Source Coding Agent! This document provides guidelines for contributing to the project.

## 🤝 How to Contribute

### **Ways to Contribute**
- 🐛 **Bug Reports**: Report issues and bugs
- 💡 **Feature Requests**: Suggest new features or improvements
- 💻 **Code Contributions**: Submit pull requests with fixes or features
- 📚 **Documentation**: Improve docs, guides, and examples
- 🧪 **Testing**: Add tests or improve test coverage
- 🌐 **Translations**: Help localize the project

## 🚀 Getting Started

### **Development Setup**
```bash
# Fork and clone the repository
git clone https://github.com/YOUR_USERNAME/coding-agent.git
cd coding-agent

# Create virtual environment
python -m venv venv
source venv/bin/activate  # or venv\Scripts\activate on Windows

# Install dependencies
pip install -r requirements.txt
pip install pytest

# Install Ollama and models
curl -fsSL https://ollama.com/install.sh | sh
ollama serve
ollama pull qwen2.5-coder:7b

# Run tests to verify setup
python -m pytest tests/ -v
```

### **Development Workflow**
1. **Create a branch** for your feature/fix: `git checkout -b feature/your-feature-name`
2. **Make your changes** following the coding standards below
3. **Add tests** for new functionality
4. **Run tests** to ensure everything works: `python -m pytest tests/ -v`
5. **Update documentation** if needed
6. **Commit your changes** with descriptive messages
7. **Push to your fork** and create a pull request

## 📋 Coding Standards

### **Python Style**
- **PEP 8**: Follow Python style guidelines
- **Type Hints**: All functions must have type annotations
- **Docstrings**: Use Google-style docstrings for all public functions
- **Async/Await**: Use async programming patterns where appropriate

### **Code Structure**
```python
"""
Module docstring explaining purpose
"""
from typing import List, Optional, Dict, Any
import asyncio

class ExampleClass:
    """Class docstring explaining purpose and usage."""
    
    def __init__(self, config: Dict[str, Any]) -> None:
        """Initialize with configuration."""
        self.config = config
    
    async def example_method(self, input_data: str) -> Optional[str]:
        """
        Method docstring explaining purpose, parameters, and return value.
        
        Args:
            input_data: Description of the parameter
            
        Returns:
            Description of return value or None if not found
            
        Raises:
            ValueError: When input_data is invalid
        """
        if not input_data:
            raise ValueError("input_data cannot be empty")
        
        # Implementation here
        return processed_data
```

### **Testing Requirements**
- **Unit Tests**: All new functions must have unit tests
- **Integration Tests**: Test component interactions
- **Mock External Dependencies**: Use mocks for Ollama, file system, etc.
- **Test Coverage**: Aim for 90%+ coverage on new code

```python
import pytest
from unittest.mock import Mock, AsyncMock

class TestExampleClass:
    """Test cases for ExampleClass."""
    
    @pytest.fixture
    def example_instance(self):
        """Create test instance."""
        return ExampleClass({"test": "config"})
    
    @pytest.mark.asyncio
    async def test_example_method_success(self, example_instance):
        """Test successful method execution."""
        result = await example_instance.example_method("test input")
        assert result == "expected output"
    
    @pytest.mark.asyncio 
    async def test_example_method_invalid_input(self, example_instance):
        """Test method with invalid input."""
        with pytest.raises(ValueError):
            await example_instance.example_method("")
```

## 🏗️ Architecture Guidelines

### **Core Principles**
1. **Modularity**: Keep components loosely coupled
2. **Extensibility**: Design for easy addition of new features
3. **Type Safety**: Use type hints and validate at runtime
4. **Error Handling**: Comprehensive error handling with user-friendly messages
5. **Performance**: Async programming and efficient algorithms

### **Adding New Tools**
```python
from .base import BaseTool, ToolResult

class MyNewTool(BaseTool):
    """Tool for specific functionality."""
    
    def __init__(self):
        self.name = "my_new_tool"
        self.description = "Describes what this tool does"
    
    async def execute(self, **kwargs) -> ToolResult:
        """Execute the tool operation."""
        try:
            # Tool implementation
            result = perform_operation(**kwargs)
            return ToolResult(success=True, content=result)
        except Exception as e:
            return ToolResult(success=False, error=str(e))
    
    def to_llm_function_schema(self) -> Dict[str, Any]:
        """Return JSON schema for LLM function calling."""
        return {
            "name": self.name,
            "description": self.description,
            "parameters": {
                "type": "object",
                "properties": {
                    "param1": {"type": "string", "description": "Parameter description"}
                },
                "required": ["param1"]
            }
        }
```

### **Adding New Providers**
```python
from .base import BaseLLMProvider, ChatMessage, ModelConfig, ProviderResponse

class MyNewProvider(BaseLLMProvider):
    """Provider for new AI service."""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
    
    def validate_config(self) -> bool:
        """Validate provider configuration."""
        return "api_key" in self.config
    
    def list_models(self) -> List[str]:
        """List available models."""
        # Implementation to fetch available models
        return ["model1", "model2"]
    
    async def chat_completion(self, messages: List[ChatMessage], config: ModelConfig) -> ProviderResponse:
        """Generate chat completion."""
        # Implementation for API call
        response_content = await self._make_api_call(messages, config)
        return ProviderResponse(
            content=response_content,
            model=config.model_name,
            usage={"tokens": 100}
        )
```

## 🧪 Testing Guidelines

### **Test Categories**
- **Unit Tests**: Test individual functions and classes
- **Integration Tests**: Test component interactions
- **End-to-End Tests**: Test complete workflows
- **Performance Tests**: Test response times and resource usage

### **Running Tests**
```bash
# Run all tests
python -m pytest tests/ -v

# Run specific test file
python -m pytest tests/test_orchestrator.py -v

# Run with coverage
python -m pytest tests/ --cov=src/core --cov-report=html

# Run performance tests
python -m pytest tests/ -m "not slow"  # Skip slow tests
python -m pytest tests/ -m "slow"      # Run only slow tests
```

### **Test Data**
- Use the `conftest.py` fixtures for consistent test data
- Mock external dependencies (Ollama, file system, network)
- Create realistic but minimal test cases

## 📚 Documentation Standards

### **Code Documentation**
- **Docstrings**: All public functions, classes, and modules
- **Inline Comments**: Complex logic and algorithms
- **Type Hints**: All function signatures
- **Examples**: Include usage examples in docstrings

### **User Documentation**
- **README**: Keep up-to-date with new features
- **Setup Guide**: Clear installation and configuration steps
- **API Docs**: Comprehensive API reference
- **Examples**: Practical usage examples and tutorials

## 🐛 Bug Reports

### **Before Reporting**
1. **Search existing issues** to avoid duplicates
2. **Try the latest version** to see if it's already fixed
3. **Reproduce the issue** with minimal steps
4. **Check logs** for error messages and stack traces

### **Bug Report Template**
```markdown
## Bug Description
Brief description of the issue

## Steps to Reproduce
1. Step one
2. Step two
3. Step three

## Expected Behavior
What should happen

## Actual Behavior
What actually happens

## Environment
- OS: [e.g., macOS 13.0]
- Python version: [e.g., 3.11.5]
- Ollama version: [e.g., 0.1.25]
- Agent version: [e.g., commit hash or release]

## Additional Context
- Error messages
- Log files
- Screenshots (if applicable)
```

## 💡 Feature Requests

### **Feature Request Template**
```markdown
## Feature Description
Clear description of the proposed feature

## Use Case
Why is this feature needed? What problem does it solve?

## Proposed Solution
How should this feature work?

## Alternatives Considered
Other approaches you've considered

## Additional Context
Any other context, mockups, or examples
```

## 🔍 Pull Request Guidelines

### **Before Submitting**
- [ ] Code follows style guidelines
- [ ] All tests pass
- [ ] New tests added for new functionality
- [ ] Documentation updated
- [ ] Commit messages are descriptive
- [ ] No unnecessary changes or files

### **Pull Request Template**
```markdown
## Description
Brief description of changes

## Type of Change
- [ ] Bug fix
- [ ] New feature
- [ ] Breaking change
- [ ] Documentation update

## Testing
- [ ] Unit tests added/updated
- [ ] Integration tests added/updated
- [ ] Manual testing completed

## Checklist
- [ ] Code follows style guidelines
- [ ] Self-review completed
- [ ] Documentation updated
- [ ] No breaking changes (or documented)
```

## 🏷️ Issue Labels

- **bug**: Something isn't working
- **enhancement**: New feature or request
- **documentation**: Improvements or additions to documentation
- **good first issue**: Good for newcomers
- **help wanted**: Extra attention is needed
- **question**: Further information is requested
- **wontfix**: This will not be worked on

## 🎯 Priority Areas

Current areas where contributions are especially welcome:

1. **Language Support**: Add parsers for JavaScript, Go, Rust, Java
2. **Tool Development**: Create specialized tools for specific domains
3. **Provider Integration**: Add support for new AI providers
4. **Performance**: Optimize model routing and response times
5. **Documentation**: Improve guides, examples, and API docs
6. **Testing**: Expand test coverage and add integration tests
7. **UI/UX**: Web interface and IDE plugins

## 🌟 Recognition

Contributors will be:
- **Listed in CONTRIBUTORS.md** with their contributions
- **Mentioned in release notes** for significant contributions
- **Given credit** in documentation and examples they create

## 📞 Getting Help

- **GitHub Discussions**: Ask questions and share ideas
- **GitHub Issues**: Report bugs and request features  
- **Documentation**: Check SETUP.md and README.md first

## 📄 License

By contributing, you agree that your contributions will be licensed under the MIT License.

---

**Thank you for contributing to making AI-assisted development better for everyone!** 🚀
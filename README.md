# 🤖 Open Source Coding Agent with Enhanced Small Model Support

A powerful, privacy-first AI coding assistant that runs entirely on your local machine. Built with intelligent model routing, robust parameter validation, and optimized support for small local models like qwen3:30b.

## 🌟 Why This Coding Agent?

- **🔒 Privacy-First**: All AI processing happens locally with Ollama - no data leaves your machine
- **🧠 Small Model Optimized**: Enhanced interpretation layer works brilliantly with local models (qwen3:30b, phi, gemma)
- **⚡ Intelligent Model Routing**: Automatically selects the best model for each task with configuration priority
- **🛡️ Robust Parameter Handling**: Automatically fixes invalid tool parameters from model outputs
- **🎯 Context-Aware**: Deep project understanding with enhanced JSON parsing and execution planning
- **🔧 Production-Ready**: Full test suite, type safety, and enterprise-grade architecture

## 🎯 Complete Feature Set

### ✅ **All 10 Core Goals Implemented**

1. **🔍 Context Awareness** - Deep project understanding with file indexing, AST analysis, and dependency mapping
2. **🧭 Codebase Navigation & Modification** - Advanced search, file operations, and code modifications
3. **💬 Intent Alignment** - Clarifying questions, alternatives, and user preference learning
4. **🔧 Error Diagnosis & Recovery** - Comprehensive debugging, syntax checking, and error analysis
5. **📚 Git Integration** - Complete version control operations with safety checks
6. **🧠 Learning & Adaptation** - Personalized behavior adaptation and continuous improvement
7. **🎛️ Intelligent Model Routing** - Optimal model selection and chaining for complex tasks
8. **🛡️ Safety & Responsibility** - Path validation, command filtering, and violation tracking
9. **📋 Task Planning & Decomposition** - Complex task breakdown and execution planning
10. **🤝 Collaboration & Handoff** - Session management, handoff packages, and team integration

### 🚀 **Advanced Capabilities**

- **Enhanced Interpretation Layer**: Converts unpredictable small model outputs into reliable structured actions
- **Automatic Parameter Validation**: Fixes common parameter mistakes (`pattern→query`, `command→action`, `filename→text`)
- **Robust JSON Parsing**: Handles truncated responses, thinking tags, and various model output formats
- **Intelligent Fallback System**: Creates execution plans when JSON parsing completely fails
- **Analysis-Driven Planning**: Models provide detailed execution_steps that directly convert to TaskStep objects
- **Small Model Support**: Optimized prompts and parsing specifically for local models (qwen3:30b, phi, gemma)

## 🏃 Quick Start

### Prerequisites
- **Python 3.11+** - Modern async features and type hints
- **8GB+ RAM** - For running local AI models
- **Git** - Version control operations
- **Ollama** - Local AI model inference

### 1-Minute Setup

```bash
# Install Ollama
curl -fsSL https://ollama.com/install.sh | sh
ollama serve

# Pull recommended models
ollama pull qwen3:30b           # Optimized for this system
ollama pull qwen2.5-coder:7b    # Alternative balanced performance
ollama pull qwen2.5-coder:32b   # Best quality (if you have 16GB+ RAM)

# Clone and setup
git clone <repository-url>
cd coding-agent
pip install -r requirements.txt

# Start coding!
python src/main.py
```

### Interactive Commands

```bash
💬 You: help
📋 Available Commands:
  • help - Show available commands
  • config - Show configuration and model preferences  
  • models - Show available models and capabilities
  • learning - Show learning progress and preferences
  • feedback <text> - Provide feedback for continuous improvement
  • suggest <task> - Get model recommendations
  • tasks - Show active task plans
  • safety - Show safety status
  • session - Show session information

💬 You: Show me the project structure
🤖 Agent: [Analyzes project with context awareness]

💬 You: Create a Python module for data processing with type hints
🤖 Agent: [Creates well-structured module with proper typing]

💬 You: feedback That was perfect, I prefer detailed type annotations
💡 Thank you! I've learned your preference for detailed type annotations.

💬 You: learning
🧠 Learning Status: 15 patterns learned, 3 preferences recorded
```

## 🎮 Real-World Examples

### Project Analysis & Navigation
```bash
"Analyze the project architecture and show me the main components"
"Find all database-related functions across the codebase"
"Show me files that haven't been modified in the last 30 days"
"Search for TODO comments and create a task list"
```

### Smart Code Operations
```bash
"Refactor the User class to use dataclasses with proper type hints"
"Extract the authentication logic into a separate module"
"Add comprehensive docstrings to all public methods in auth.py"
"Rename the variable 'data' to 'user_profile' throughout the project"
```

### Git Workflow Integration
```bash
"Check git status and show me what files have changed"
"Create a feature branch for user authentication"
"Commit my changes with a descriptive message"
"Show me the diff between my branch and main"
```

### Intelligent Debugging
```bash
"Analyze this error: 'AttributeError: 'NoneType' object has no attribute 'name'"
"Check for potential memory leaks in the caching module"
"Find and fix common Python anti-patterns in my code"
"Suggest performance optimizations for the data processing pipeline"
```

## 🏗️ Enhanced Architecture for Small Models

### **Small Model Optimization Layer**
- **Enhanced JSON Format**: Includes detailed `execution_steps` for direct planner integration
- **Parameter Validation**: Automatically fixes common mistakes like `pattern→query`, `command→action`
- **Search Type Validation**: Converts invalid types like `filename→text` with smart file patterns
- **Intelligent Fallback**: Creates execution plans from keyword analysis when JSON parsing fails
- **Robust Parsing**: Handles truncated responses, thinking tags, and mixed content formats

### **Request Processing Flow**
1. **Analysis Phase**: Models receive directive format with tool parameter hints
2. **Validation Phase**: Automatic parameter correction and search type validation  
3. **Planning Phase**: Direct conversion of execution_steps to TaskStep objects
4. **Execution Phase**: Tools receive validated parameters matching their schemas

### **Intelligent Model Management**
- **Configuration Priority**: Respects user model preferences over heuristic scoring
- **Task Complexity Analysis**: Automatically determines optimal approach
- **Enhanced Prompting**: Optimized directive format for small model understanding
- **Adaptive Parsing**: Multiple parsing strategies for various model output formats

### **Enterprise-Grade Features**
- **Type Safety**: Full type annotations and mypy compatibility
- **Test Coverage**: Comprehensive test suite with 90%+ coverage
- **Error Handling**: Robust error recovery and user feedback
- **Configuration Management**: Flexible YAML-based configuration
- **Session Persistence**: Automatic session saving and recovery

## 🧪 Testing & Quality Assurance

```bash
# Run comprehensive test suite
python -m pytest tests/ -v

# Test specific components
python -m pytest tests/test_learning.py -v
python -m pytest tests/test_model_router.py -v

# Run with coverage
python -m pytest tests/ --cov=src/core --cov-report=html

# Type checking
mypy src/

# Linting
ruff check src/
```

## 📊 Performance & Requirements

### **Recommended Hardware**
- **16GB+ RAM**: For best model performance (qwen2.5-coder:32b)
- **8GB RAM**: Good performance (qwen2.5-coder:7b)
- **4GB RAM**: Basic functionality (qwen2.5-coder:1.5b)
- **SSD Storage**: Faster model loading and file operations

### **Model Recommendations**
- **Primary Choice**: `qwen3:30b` - Optimized with enhanced parameter validation and parsing
- **Alternative**: `qwen2.5-coder:7b` - Good performance with parameter fixes
- **High Quality**: `qwen2.5-coder:32b` - Maximum reasoning (requires 16GB+ RAM)
- **Quick Tasks**: `phi3:14b` - Fast responses with intelligent fallback support
- **Analysis**: `deepseek-coder:33b` - Superior for complex code analysis

## 🔧 Advanced Configuration

### **Custom Model Setup**
```yaml
# config.yaml
models:
  high_reasoning:
    - "qwen3:30b"           # Optimized primary choice
    - "qwen2.5-coder:32b"
    - "deepseek-coder:33b"
  fast_completion:
    - "qwen3:30b"           # Works excellently for fast tasks too
    - "phi3:14b"
    - "qwen2.5-coder:7b" 
  analysis:
    - "qwen3:30b"           # Enhanced analysis format support
    - "qwen2.5-coder:14b"

agent:
  max_iterations: 10
  context_window: 8192
  auto_save_session: true

safety:
  enable_path_validation: true
  max_file_size_mb: 10
  restricted_paths: ["/etc", "/sys"]
```

### **Learning Customization**
The agent learns and adapts to:
- **Response Style**: Concise vs detailed explanations
- **Tool Preferences**: Preferred tools for specific tasks
- **Model Preferences**: Which models work best for your use cases
- **Code Patterns**: Your coding style and conventions

## 🤝 Contributing & Development

We welcome contributions! The codebase is designed for extensibility:

### **Priority Areas**
1. **Language Support**: Add parsers for new programming languages
2. **Tool Development**: Create specialized tools for specific domains
3. **Provider Integration**: Add support for new AI providers
4. **Learning Algorithms**: Improve the adaptation mechanisms
5. **Performance**: Optimize model routing and caching

### **Development Setup**
```bash
# Clone repository
git clone <repository-url>
cd coding-agent

# Setup development environment
python -m venv venv
source venv/bin/activate  # or venv\Scripts\activate on Windows
pip install -r requirements.txt
pip install pytest

# Run tests
python -m pytest tests/ -v

# Install pre-commit hooks
pre-commit install
```

## 🐛 Troubleshooting

### **Common Issues & Solutions**

**"Cannot connect to Ollama"**
```bash
# Check if Ollama is running
ps aux | grep ollama
ollama serve

# Test connection
curl http://localhost:11434/api/tags
```

**"No suitable model found"**
```bash
# List available models
ollama list

# Pull recommended model
ollama pull qwen2.5-coder:7b

# Check model status
ollama show qwen2.5-coder:7b
```

**"Learning system not working"**
```bash
# Check learning directory permissions
ls -la learning_data/

# Reset learning data (if needed)
rm -rf learning_data/
mkdir learning_data/
```

## 📈 Roadmap & Future Plans

- **🌐 Web Interface**: Browser-based UI for non-terminal users
- **🔌 IDE Plugins**: VS Code, PyCharm, and Vim integrations
- **📱 Mobile Support**: Remote access via mobile applications
- **☁️ Cloud Sync**: Optional cloud synchronization for learning data
- **🤖 Multi-Agent**: Collaborative multi-agent workflows
- **📊 Analytics**: Advanced usage analytics and insights

## 📄 License & Acknowledgments

**MIT License** - Free for commercial and personal use.

### **Built With**
- **[Ollama](https://ollama.com)** - Local AI model inference
- **[Python](https://python.org)** - Core implementation language  
- **[asyncio](https://docs.python.org/3/library/asyncio.html)** - Asynchronous programming
- **[pytest](https://pytest.org)** - Testing framework
- **[pydantic](https://pydantic.dev)** - Data validation

### **Special Thanks**
- Open-source AI community for advancing local AI
- Contributors and early adopters providing feedback
- Ollama team for making local AI accessible

---

## 🚀 **Ready to Transform Your Coding Workflow?**

```bash
# Get started in under 2 minutes
curl -fsSL https://ollama.com/install.sh | sh
ollama serve && ollama pull qwen2.5-coder:7b
git clone <repository-url> && cd coding-agent
pip install -r requirements.txt && python src/main.py
```

**Experience the future of AI-assisted development - private, adaptive, and powerful!** 🌟
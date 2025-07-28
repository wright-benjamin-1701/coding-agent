# Setup Instructions

Complete setup guide for the Coding Agent with Ollama integration.

## Prerequisites

- **Python 3.11+**: Required for modern async features and type hints
- **Git**: For version control operations
- **Ollama**: For local AI model inference
- **8GB+ RAM**: Recommended for running larger models

## Step 1: Install Ollama

### macOS/Linux
```bash
curl -fsSL https://ollama.com/install.sh | sh
```

### Windows
Download and install from: https://ollama.com/download

### Start Ollama Service
```bash
ollama serve
```

## Step 2: Pull Recommended Models

The agent automatically selects models based on your hardware and task complexity. Pull the models you want to use:

### Recommended Models (in order of preference)

#### For Systems with 16GB+ RAM:
```bash
# Best performance for coding
ollama pull qwen2.5-coder:32b

# Alternative high-performance models
ollama pull deepseek-coder:33b
ollama pull codestral:22b
```

#### For Systems with 8-16GB RAM:
```bash
# Balanced performance and speed
ollama pull qwen2.5-coder:14b
ollama pull qwen2.5-coder:7b

# Alternative efficient models
ollama pull deepseek-coder:6.7b
ollama pull codegemma:7b
```

#### For Systems with 4-8GB RAM:
```bash
# Lightweight but capable
ollama pull qwen2.5-coder:1.5b
ollama pull phi3:mini
```

### Verify Installation
```bash
# Check running models
ollama list

# Test a model
ollama run qwen2.5-coder:7b "Write a Python hello world function"
```

## Step 3: Install Coding Agent

### Clone Repository
```bash
git clone <repository-url>
cd coding-agent
```

### Create Virtual Environment
```bash
# Create virtual environment
python -m venv venv

# Activate it
# On macOS/Linux:
source venv/bin/activate
# On Windows:
venv\Scripts\activate
```

### Install Dependencies
```bash
pip install -r requirements.txt
```

### Optional: Install Development and Testing Dependencies
```bash
# For development
pip install -e ".[dev]"

# For running tests
pip install pytest
```

## Step 4: Configuration

### Create Configuration File
```bash
cp config.example.yaml config.yaml
```

### Edit Configuration
Open `config.yaml` and customize:

```yaml
# Ollama Configuration
ollama:
  base_url: "http://localhost:11434"
  timeout: 300

# Model Preferences (in order of preference)
models:
  high_reasoning:
    - "qwen2.5-coder:32b"
    - "deepseek-coder:33b"
    - "qwen2.5-coder:14b"
    - "qwen2.5-coder:7b"
  
  fast_completion:
    - "qwen2.5-coder:7b"
    - "qwen2.5-coder:1.5b"
    - "phi3:mini"
  
  analysis:
    - "qwen2.5-coder:14b"
    - "qwen2.5-coder:7b"

# Safety Settings
safety:
  max_file_size_mb: 10
  restricted_paths:
    - "/etc"
    - "/sys" 
    - "/proc"
  dangerous_commands:
    - "rm -rf"
    - "sudo"
    - "format"

# Agent Behavior
agent:
  max_iterations: 10
  context_window: 8192
  memory_limit_mb: 500
  auto_save_session: true
```

### Environment Variables (Optional)
Create `.env` file for sensitive settings:

```bash
# .env file
OLLAMA_URL=http://localhost:11434
OPENAI_API_KEY=your_openai_key_here  # For future OpenAI integration
ANTHROPIC_API_KEY=your_anthropic_key_here  # For future Claude integration
```

## Step 5: First Run

### Test Installation
```bash
python src/main.py --help
```

### Interactive Mode
```bash
python src/main.py
```

### Test with Sample Commands
```bash
# Check if everything works
python src/main.py --batch "Show me the project structure" "What models are available?"
```

### Available Commands
Once running in interactive mode, you can use these commands:

- `help` - Show available commands
- `config` - Show current configuration and model preferences
- `session` - Show session information and duration
- `tasks` - Show active task plans and progress
- `safety` - Show safety status and recent violations
- `models` - Show available models and their capabilities
- `suggest <task>` - Get model recommendations for a specific task
- `learning` - Show learning progress and user preferences
- `feedback <text>` - Provide feedback on the last response for learning

### Example Interactions
```bash
💬 You: Show me the project structure
🤖 Agent: I'll analyze your project structure...

💬 You: Create a new Python module for data processing
🤖 Agent: I'll create a data processing module with proper structure...

💬 You: feedback That was helpful, but please include type hints
💡 Thank you for the feedback! I've recorded this to improve future responses.

💬 You: learning
🧠 Learning & Adaptation Status:
   Patterns learned: 15
   User preferences: 3
   Recent interactions: 47
```

## Step 6: Testing (Optional)

### Run Test Suite
```bash
# Run all tests
python -m pytest tests/ -v

# Run specific test categories
python -m pytest tests/test_orchestrator.py -v
python -m pytest tests/test_learning.py -v
python -m pytest tests/test_model_router.py -v

# Run tests with coverage (if installed)
python -m pytest tests/ --cov=src/core --cov-report=html
```

### Test Individual Components
```bash
# Test model routing
python -c "
from src.core.model_router import ModelRouter
from src.core.providers.ollama_provider import OllamaProvider
provider = OllamaProvider({'base_url': 'http://localhost:11434'})
router = ModelRouter(provider)
print('✅ Model router working')
"

# Test learning system
python -c "
from src.core.learning import get_learning_system
learning = get_learning_system()
summary = learning.get_learning_summary()
print(f'✅ Learning system working: {summary}')
"
```

## Step 7: Verification

### Run System Check
```bash
python -c "
import sys
print(f'Python version: {sys.version}')

try:
    import aiohttp, aiofiles, requests
    print('✅ All dependencies installed')
except ImportError as e:
    print(f'❌ Missing dependency: {e}')

import subprocess
try:
    result = subprocess.run(['ollama', 'list'], capture_output=True, text=True)
    if result.returncode == 0:
        print('✅ Ollama is working')
        print('Available models:')
        print(result.stdout)
    else:
        print('❌ Ollama not responding')
except FileNotFoundError:
    print('❌ Ollama not installed')
"
```

## Troubleshooting

### Common Issues

#### 1. "Cannot connect to Ollama"
```bash
# Check if Ollama is running
ps aux | grep ollama

# Start Ollama if not running
ollama serve

# Test connection
curl http://localhost:11434/api/tags
```

#### 2. "No models found"
```bash
# List available models
ollama list

# Pull a model if none available
ollama pull qwen2.5-coder:7b

# Check model status
ollama show qwen2.5-coder:7b
```

#### 3. "Memory/Performance Issues"
```bash
# Check system resources
free -h  # Linux
vm_stat  # macOS

# Use smaller models
ollama pull qwen2.5-coder:1.5b

# Adjust config.yaml memory limits
```

#### 4. "Import Errors"
```bash
# Ensure virtual environment is activated
which python

# Reinstall dependencies
pip install --force-reinstall -r requirements.txt

# Check Python version
python --version  # Should be 3.11+
```

#### 5. "Permission Errors"
```bash
# For file operations
chmod +x src/main.py

# For Ollama installation
sudo ollama serve  # If needed
```

### Performance Optimization

#### Model Selection Tips
- **Development**: Use `qwen2.5-coder:7b` for good balance
- **Analysis**: Use `qwen2.5-coder:14b` for complex reasoning
- **Quick Tasks**: Use `qwen2.5-coder:1.5b` for fast responses
- **Production**: Use `qwen2.5-coder:32b` for best results

#### System Optimization
```bash
# For better performance, consider:
# 1. SSD storage for model files
# 2. Sufficient RAM (models load into memory)
# 3. GPU acceleration (if supported)

# Check Ollama GPU usage
ollama run qwen2.5-coder:7b --verbose
```

## Advanced Setup

### Learning & Adaptation Features

The agent includes a sophisticated learning system that adapts to your preferences:

#### Learning Data Storage
- **Location**: `./learning_data/` directory
- **Patterns**: `patterns.json` - Successful interaction patterns
- **Preferences**: `preferences.json` - Your personalized preferences
- **Events**: `recent_events.json` - Recent interaction history

#### What the Agent Learns
- **User Preferences**: Response style (concise vs detailed), preferred tools, preferred models
- **Successful Patterns**: What approaches work well for different tasks
- **Common Corrections**: Learns from your feedback to avoid repeated mistakes
- **Performance Metrics**: Tracks success rates and improvements over time

#### Providing Feedback
```bash
# After any response, provide feedback:
feedback That was helpful, but please be more concise
feedback Good approach, I prefer this tool for git operations
feedback Actually, that's incorrect - it should use the file tool instead
```

#### Monitoring Learning Progress
```bash
# Check learning status
learning

# View performance trends
models  # Shows model performance with learned data
```

### Custom Model Integration
```bash
# Import custom models
ollama create my-custom-model -f Modelfile

# Add to config.yaml
# models:
#   custom:
#     - "my-custom-model"
```

### IDE Integration
The agent works well with:
- **VS Code**: Use terminal integration
- **PyCharm**: Use built-in terminal
- **Vim/Neovim**: Use terminal mode
- **Emacs**: Use shell integration

### Docker Setup (Optional)
```bash
# Build container
docker build -t coding-agent .

# Run with Ollama access
docker run -it --network host coding-agent
```

## Next Steps

1. **Try Example Commands**: See README.md for usage examples
2. **Customize Configuration**: Adjust models and behavior in config.yaml
3. **Explore Tools**: Learn about available tools and capabilities
4. **Contribute**: Help improve the agent with new features

## Support

- **Documentation**: See README.md and ARCHITECTURE.md
- **Issues**: Report bugs on GitHub
- **Community**: Join discussions and share improvements

---

*Happy coding with your new AI assistant! 🚀*
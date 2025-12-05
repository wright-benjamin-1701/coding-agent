# Coding Agent

A thin, extensible coding agent with RAG (Retrieval-Augmented Generation) and tool execution capabilities. Designed for small models with clean separation of concerns and low cyclomatic complexity.

## Features

### Core Capabilities
- **Interactive Text Interface**: Conversational Python program (no complex CLI)
- **Model Provider Abstraction**: LLM-agnostic with built-in Ollama support
- **RAG Database**: Context storage with SQLite for session history and file caching
- **Tool Registry**: Extensible tool system with JSON schema validation
- **Plan Orchestrator**: Hybrid hardcoded + LLM plan generation
- **Plan Executor**: Tool execution loop with confirmation for destructive actions
- **File Indexing**: Automatic codebase indexing with change watching
- **Configuration Management**: Environment variables, config files, and interactive setup

### Advanced Development Features
- **Comprehensive Code Generation**: Templates for classes, functions, APIs, React components
- **Intelligent Refactoring**: AST-based code transformation and structure improvement
- **Security Vulnerability Scanning**: Detection of secrets, injection risks, crypto issues
- **Architecture Analysis**: Dependency mapping, circular dependency detection, complexity metrics
- **Permanent Directive System**: Persistent behavior rules and coding standards
- **Smart Code Writing**: Analyzes codebase structure and intelligently places new code
- **Web Interface**: Browser-based prompt submission and session viewing
- **Enhanced Result Summarization**: Meaningful feedback instead of generic completion messages
- **Improved User Experience**: Fixed confirmation loops and better error handling
- **Intelligent Prompt Enhancement**: Automatically enhances prompts with business context, extensibility guidance, and RAG-based architecture considerations

## Installation

```bash
pip install -e .
```

## Prerequisites

- Python 3.9+
- [Ollama](https://ollama.ai/) running locally (default: http://localhost:11434)
- Git repository for full functionality

## Quick Start

### Option 1: Install and Run from Anywhere

Install the coding agent globally to run from any terminal folder:

```bash
# Install in development mode (from the project directory)
pip install -e .

# Now you can run from any directory
cd /path/to/your/project
coding-agent
```

### Option 2: Run from Project Directory

Run directly from the coding-agent project folder:

```bash
# Using the launcher script (works from project directory)
python run.py

# Or using the global launcher script
python coding-agent
```

### First-Time Setup

1. First run will guide you through configuration setup

2. Then interact naturally:

```
🤖 > add error handling to the main function
🤖 > find all TODO comments  
🤖 > run the tests
🤖 > generate a React component for user login
🤖 > scan for security vulnerabilities
🤖 > refactor the database connection code
🤖 > analyze the architecture dependencies
🤖 > generate tests for my_module.py
🤖 > create comprehensive tests for the User class
🤖 > move user_service.py to services/user_service.py
🤖 > relocate all auth files to the auth/ directory
```

## Architecture

The system is designed with clear separation of concerns:

- **Model Provider** (`providers/`): Handles LLM communication
- **Prompt Manager** (`prompt_manager.py`): Single template with context injection
- **Tool Registry** (`tools/`): Manages available tools and schemas
- **Plan Orchestrator** (`orchestrator.py`): Generates execution plans
- **Plan Executor** (`executor.py`): Executes tools with confirmations
- **RAG Database** (`database/`): Stores context and summaries
- **File Indexer** (`indexer/`): Maintains codebase index

## Available Tools

### Core Tools
- **File Operations**: `read_file`, `write_file`, `search_files`, `smart_write_file`, `move_file`
- **Directory Operations**: `create_directory`, `remove_directory`, `list_directory`
- **Git Operations**: `git_status`, `git_diff`, `git_commit_hash`
- **Testing**: `run_tests`, `lint_code`
- **Analysis**: `brainstorm_search_terms`, `summarize_code`, `analyze_code`
- **Web Interface**: `web_viewer` - Launch browser-based interface with prompt submission

### Advanced Development Tools
- **Code Generation**: `generate_code` - Create boilerplate, templates, and scaffolding
- **Test Generation**: `generate_tests` - Auto-generate comprehensive tests from existing code
- **Refactoring**: `refactor_code` - Extract functions, rename variables, move code blocks
- **Security Scanning**: `security_scan` - Detect vulnerabilities, secrets, injection risks
- **Architecture Analysis**: `analyze_architecture` - Dependency visualization, complexity metrics
- **Directive Management**: `manage_directives` - Permanent rules and behavior guidelines
- **Smart Writing**: `smart_write_file` - Intelligently places code by analyzing existing structure
- **File Movement**: `move_file` - Move files and automatically update all imports and references
- **Task Evaluation**: `evaluate_task` - Execute complex tasks and analyze the agent's performance for continuous improvement
- **Prompt Enhancement**: `manage_prompt_enhancement` - Configure automatic prompt enhancements for business and extensibility context

## Configuration

The agent supports flexible configuration through config files, environment variables, and CLI options.

### Configuration Methods (in order of precedence):

1. **CLI Options**: `--model`, `--provider`, `--base-url`, `--debug`
2. **Environment Variables**: `CODING_AGENT_MODEL`, `CODING_AGENT_PROVIDER`, etc.
3. **Config File**: JSON configuration file
4. **Defaults**: Built-in defaults

### Configuration File

Create a configuration file:

```bash
coding-agent config --model codellama:7b
```

Or copy the example:

```bash
cp example_config.json .coding_agent_config.json
```

### Environment Variables

All configuration options can be set via environment variables:

```bash
# Model settings
export CODING_AGENT_PROVIDER="ollama"
export CODING_AGENT_MODEL="codellama:7b"
export CODING_AGENT_BASE_URL="http://localhost:11434"
export CODING_AGENT_TEMPERATURE="0.7"
export CODING_AGENT_MAX_TOKENS="2048"

# Database settings
export CODING_AGENT_DB_PATH=".coding_agent.db"
export CODING_AGENT_MAX_SUMMARIES="10"
export CODING_AGENT_CACHE_ENABLED="true"

# Indexer settings
export CODING_AGENT_INDEX_FILE=".coding_agent_index.json"
export CODING_AGENT_WATCH_ENABLED="true"

# General settings
export CODING_AGENT_DEBUG="true"
```

## Interactive Commands

Once running, you can use these commands:

```
🤖 > help     - Show available commands
🤖 > status   - Show agent status and recent sessions  
🤖 > config   - Show current configuration
🤖 > tools    - List available tools
🤖 > clear    - Clear screen
🤖 > quit     - Exit program
```

**Or just type your coding requests naturally:**

```
🤖 > add error handling to main.py
🤖 > find functions that use the database
🤖 > refactor the User class
🤖 > run the unit tests
🤖 > create a README for this project
🤖 > extract this function into a separate method
🤖 > scan this directory for hardcoded secrets
🤖 > generate a Python class for data processing
🤖 > add a permanent directive: "Always use type hints"
```

## User Experience

The agent provides a clean, conversational interface:

1. **First Time Setup**: Guided configuration with smart defaults
2. **Natural Language**: No complex command syntax - just describe what you need
3. **Visual Feedback**: Clear status indicators and formatted output
4. **Context Awareness**: Remembers recent actions and modified files
5. **Safety First**: Asks for confirmation before destructive operations
6. **Extensible**: Easy to add new tools and capabilities

Example session:
```
🤖 > status
✅ Provider: ollama (codellama:7b)  
📚 Recent: Fixed error handling in main.py

🤖 > find all functions that handle file uploads
🔄 Processing request...
📋 Plan: Search for upload-related functions → Read relevant files
✅ Found 3 functions: upload_file(), process_upload(), validate_file()

🤖 > add logging to those functions
⚠️  This will modify 2 files. Continue? (y/N): y
✅ Added logging to upload functions
```

## Design Principles

1. **Single System Prompt**: Minimizes template complexity
2. **No Keyword Behavior**: Avoids response-dependent logic
3. **Hybrid Planning**: Combines hardcoded patterns with LLM flexibility
4. **Clean Separation**: Each component has a single responsibility
5. **Extensible Tools**: Easy to add new capabilities
6. **Confirmation Gates**: Safety for destructive operations

## Recent Updates (Latest Version)

### Enhanced Tools & Capabilities
- **Code Generation Tool**: Create boilerplate code for classes, functions, API endpoints, React components, and test files across multiple languages (Python, JavaScript/TypeScript, Java)
- **Test Generator Tool**: Automatically generate comprehensive tests by analyzing existing code, including unit tests, edge cases, error handling, and mock generation for Python (pytest/unittest) and JavaScript (Jest/Vitest/Mocha)
- **File Movement Tool**: Move files and automatically update all import statements across the codebase, supporting Python (absolute/relative imports) and JavaScript/TypeScript (ES6/CommonJS imports) with backup and dry-run capabilities
- **Refactoring Tool**: Extract functions with intelligent parameter detection, rename variables with scope awareness, move code blocks between files
- **Security Scanner**: Comprehensive vulnerability detection including hardcoded secrets (API keys, passwords, tokens), SQL injection risks, XSS vulnerabilities, cryptographic weaknesses, and unsafe operations
- **Architecture Analyzer**: Dependency mapping, circular dependency detection, complexity metrics, design pattern recognition, and code smell identification
- **Directive Management**: Persistent behavior rules that inject into all prompts for consistent coding standards

### User Experience Improvements
- **Better Result Summaries**: Replaced vague "X/Y actions complete" messages with detailed, meaningful summaries of what was accomplished
- **Fixed Confirmation Loops**: Eliminated repetitive confirmation requests that blocked workflow
- **Improved Search Results**: Better formatting and display of search results with context
- **Enhanced Error Handling**: Cleaner error messages and graceful handling of edge cases

### Technical Enhancements
- **Permanent Directive System**: Configuration-based rules that persist across sessions
- **Cache Service Integration**: Smart caching of file content and analysis results
- **AST-Based Analysis**: Proper Python code parsing for refactoring and complexity analysis
- **Multi-Language Support**: Code generation and analysis for Python, JavaScript, TypeScript, Java, and more
- **Intelligent Prompt Enhancement**: Automatic enhancement of user requests with business context and extensibility guidance

### Prompt Enhancement System

The agent automatically enhances user prompts with additional context to improve output quality:

**Business Context Enhancements:**
- Stakeholder-friendly outputs and executive summaries
- Enterprise coding standards and best practices  
- Security implications and compliance considerations
- Maintainability and team collaboration patterns

**Extensibility Context Enhancements:**
- Modular, loosely-coupled component design
- Plugin/extension points for future needs
- SOLID principles and design patterns
- Configuration and customization options

**RAG-Based Architecture Considerations:**
- Language-specific conventions and best practices
- Framework-specific patterns and guidelines
- Project history and architectural decisions
- Existing codebase patterns and structure consistency
- Dependency-aware recommendations

**Example Enhancement in Action:**

Original request:
```
🤖 > create a new API endpoint for user authentication
```

Enhanced with RAG-based context:
```
create a new API endpoint for user authentication

Consider business requirements:
- Follow enterprise coding standards and best practices
- Include comprehensive error handling and logging
- Design for maintainability and team collaboration
- Consider security implications and data protection

Consider architecture requirements based on your codebase:
- Language stack: Python
- Follow Python conventions: PEP 8, type hints, docstrings
- Flask patterns: blueprint organization, factory pattern, configuration management
- Existing architectural patterns: Layered Architecture, Configuration-Based Design
- Recent architectural decisions:
  • Added JWT token authentication system...
  • Implemented database connection pooling...
- API considerations: versioning, authentication, rate limiting, documentation
- Security considerations: input validation, authentication, authorization, encryption
```

**Configuration:**
```bash
🤖 > manage_prompt_enhancement show              # View current settings
🤖 > manage_prompt_enhancement enable            # Enable enhancements  
🤖 > manage_prompt_enhancement configure --business_context=true --show_enhancements=true
```

## Extension Points

- Add new tools by implementing the `Tool` interface
- Add new model providers by implementing `ModelProvider`
- Extend the plan orchestrator for custom pre-actions
- Enhance the file indexer for better symbol extraction
- Create custom security rules in the SecurityScanTool
- Add new code templates in the CodeGeneratorTool

## Database Schema

The agent maintains:

- **Sessions**: User prompts, summaries, and execution logs
- **File Cache**: Content and summaries by commit hash

Files are automatically cached and indexed for fast retrieval.

## Development

The codebase prioritizes:

- Low cyclomatic complexity
- Clear interfaces
- Testable components
- Minimal dependencies
- Type safety with Pydantic

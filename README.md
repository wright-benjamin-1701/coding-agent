# Coding Agent

A thin, extensible coding agent with RAG (Retrieval-Augmented Generation) and tool execution capabilities. Designed for small models with clean separation of concerns and low cyclomatic complexity.

## Features

- **Interactive Text Interface**: Conversational Python program (no complex CLI)
- **Model Provider Abstraction**: LLM-agnostic with built-in Ollama support
- **RAG Database**: Context storage with SQLite for session history and file caching
- **Tool Registry**: Extensible tool system with JSON schema validation
- **Plan Orchestrator**: Hybrid hardcoded + LLM plan generation
- **Plan Executor**: Tool execution loop with confirmation for destructive actions
- **File Indexing**: Automatic codebase indexing with change watching
- **Configuration Management**: Environment variables, config files, and interactive setup
- **Low Complexity**: Clean architecture with separated concerns

## Installation

```bash
pip install -e .
```

## Prerequisites

- Python 3.9+
- [Ollama](https://ollama.ai/) running locally (default: http://localhost:11434)
- Git repository for full functionality

## Quick Start

1. Run the agent:

```bash
python run.py
```

Or if installed:

```bash
coding-agent
```

2. First run will guide you through configuration setup

3. Then interact naturally:

```
🤖 > add error handling to the main function
🤖 > find all TODO comments  
🤖 > run the tests
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

- **File Operations**: `read_file`, `write_file`, `search_files`
- **Git Operations**: `git_status`, `git_diff`, `git_commit_hash`
- **Testing**: `run_tests`, `lint_code`
- **Analysis**: `brainstorm_search_terms`

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

## Extension Points

- Add new tools by implementing the `Tool` interface
- Add new model providers by implementing `ModelProvider`
- Extend the plan orchestrator for custom pre-actions
- Enhance the file indexer for better symbol extraction

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

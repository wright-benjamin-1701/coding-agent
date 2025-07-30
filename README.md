# Coding Agent

A thin, extensible coding agent with RAG (Retrieval-Augmented Generation) and tool execution capabilities. Designed for small models with clean separation of concerns and low cyclomatic complexity.

## Features

- **Model Provider Abstraction**: LLM-agnostic with built-in Ollama support
- **RAG Database**: Context storage with SQLite for session history and file caching
- **Tool Registry**: Extensible tool system with JSON schema validation
- **Plan Orchestrator**: Hybrid hardcoded + LLM plan generation
- **Plan Executor**: Tool execution loop with confirmation for destructive actions
- **File Indexing**: Automatic codebase indexing with change watching
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

1. Initialize the agent:
```bash
coding-agent init
```

2. Run interactively:
```bash
coding-agent run
```

3. Run with a single prompt:
```bash
coding-agent run "add error handling to the main function"
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

### CLI Usage

```bash
# Use different model
coding-agent --model codellama:7b run

# Use custom Ollama instance
coding-agent --base-url http://192.168.1.100:11434 run

# Use custom config file
coding-agent --config my-config.json run

# Enable debug mode
coding-agent --debug run
```

## CLI Commands

- `coding-agent init` - Initialize agent and build file index
- `coding-agent run [PROMPT]` - Run agent (interactive if no prompt)
- `coding-agent status` - Show agent status and recent sessions
- `coding-agent tools` - List available tools and descriptions
- `coding-agent config` - Create or update configuration
- `coding-agent config-show` - Show current configuration
- `coding-agent config-reset` - Reset configuration to defaults

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
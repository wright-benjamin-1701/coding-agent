# Coding Agent Architecture

## Core Design Principles

1. **Provider Agnostic**: Abstract LLM layer supporting Ollama, OpenAI, Anthropic, etc.
2. **Tool-First Architecture**: Extensible tool system with unified interfaces
3. **Context Awareness**: Project-wide understanding with memory management
4. **Event-Driven**: Asynchronous agent communication and coordination
5. **Small Model Optimized**: Enhanced interpretation layer for local models (qwen3:30b, phi, etc.)
6. **Robust Parameter Handling**: Automatic validation and correction of tool parameters

## System Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         Agent Orchestrator                      │
│  ┌─────────────────┐  ┌──────────────────┐  ┌─────────────────┐ │
│  │  Request        │  │   Task Planner   │  │   Model Router  │ │
│  │  Analysis       │  │                  │  │                 │ │
│  └─────────────────┘  └──────────────────┘  └─────────────────┘ │
├─────────────────────────────────────────────────────────────────┤
│                    Interpretation Layer                         │
│  ┌─────────────────┐  ┌──────────────────┐  ┌─────────────────┐ │
│  │  Request        │  │   Parameter      │  │   Response      │ │
│  │  Interpreter    │  │   Validator      │  │   Interpreter   │ │
│  └─────────────────┘  └──────────────────┘  └─────────────────┘ │
├─────────────────────────────────────────────────────────────────┤
│                      Provider Abstraction                       │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐             │
│  │   Ollama    │  │   OpenAI    │  │  Anthropic  │   ...       │
│  │  (qwen3:30b)│  │    (GPT)    │  │  (Claude)   │             │
│  └─────────────┘  └─────────────┘  └─────────────┘             │
├─────────────────────────────────────────────────────────────────┤
│                        Tool Layer                               │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐             │
│  │   Search    │  │    File     │  │     Git     │   ...       │
│  │   Tool      │  │   System    │  │  Operations │             │
│  └─────────────┘  └─────────────┘  └─────────────┘             │
├─────────────────────────────────────────────────────────────────┤
│                     Context System                              │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐             │
│  │  Project    │  │ Conversation│  │   Learning  │             │
│  │   Context   │  │   History   │  │   System    │             │
│  └─────────────┘  └─────────────┘  └─────────────┘             │
└─────────────────────────────────────────────────────────────────┘
```

## Key Components

### 1. Agent Orchestrator
- **Request Analysis**: Comprehensive analysis using enhanced JSON format with execution_steps
- **Task Planning**: Creates executable TaskPlan objects from model analysis
- **Model Router**: Intelligent routing based on task complexity and configuration
- **Execution Management**: Coordinates tool execution with proper dependency handling

### 2. Interpretation Layer (NEW)
- **Request Interpreter**: Converts user requests into structured actions for small models
- **Parameter Validator**: Automatically fixes invalid tool parameters (e.g., `pattern→query`, `command→action`)
- **Response Interpreter**: Handles various model output formats including thinking tags and truncated JSON
- **Intelligent Fallback**: Creates execution plans when JSON parsing fails

### 3. Enhanced Task Planner
- **Analysis-Driven Planning**: Creates TaskPlan directly from model execution_steps
- **Dynamic Step Generation**: Converts JSON execution steps to TaskStep objects
- **Dependency Management**: Maintains proper execution order with step dependencies
- **Parameter Validation**: All tool parameters validated before execution

### 4. Provider Abstraction
- **Unified Interface**: Common API across all LLM providers
- **Small Model Support**: Optimized for local models (qwen3:30b, phi, gemma)
- **Configuration Priority**: Respects user model preferences over heuristics
- **Adaptive Behavior**: Adjusts prompts and parsing for different model capabilities

### 5. Enhanced Tool System
- **Search Tool**: Text, regex, function, class, and import search with parameter validation
- **File Tool**: Read, write, list operations with action validation
- **Git Tool**: Status, commit, diff, branch operations with command mapping
- **Parameter Mapping**: Automatic correction of common parameter mismatches
- **Schema Validation**: Ensures all parameters match tool expectations

### 6. Context System
- **Project Understanding**: AST parsing, dependency analysis
- **Memory Management**: Conversation history and learning
- **Knowledge Base**: Documentation and code pattern storage
- **Adaptive Learning**: Learns from user feedback and interaction patterns

## Request Processing Flow

```
User Input
    ↓
┌─────────────────────────┐
│   Request Analysis      │ ← Enhanced JSON format with execution_steps
│  (Directive Format)     │
└─────────────────────────┘
    ↓
┌─────────────────────────┐
│  Parameter Validation   │ ← Auto-fix invalid parameters
│   & Correction         │   (pattern→query, command→action)
└─────────────────────────┘
    ↓
┌─────────────────────────┐
│   TaskPlan Creation     │ ← Convert execution_steps to TaskStep objects
│  (from execution_steps) │
└─────────────────────────┘
    ↓
┌─────────────────────────┐
│   Tool Execution       │ ← Execute with validated parameters
│  (Dependency Order)     │
└─────────────────────────┘
    ↓
Final Result
```

## Small Model Optimization

### Analysis Format
```json
{
    "requires_tools": true/false,
    "tools_needed": ["search", "file"],
    "execution_steps": [
        {
            "step": "Search for main function definitions",
            "tool": "search",
            "parameters": {"query": "def main", "search_type": "text"},
            "dependencies": []
        }
    ],
    "complexity": "medium",
    "priority": 3
}
```

### Parameter Validation Examples
```python
# Search tool parameter fixes
"pattern" → "query"              # Common model mistake
"filename" → "text" + file_pattern  # Invalid search_type
"search_term" → "query"          # Alternative naming

# Git tool parameter fixes  
"command" → "action"             # Common model mistake
"operation" → "action"           # Alternative naming

# File tool parameter fixes
"list_structure" → "list"        # Invalid action
"filename" → "path"              # Parameter mapping
```

## Implementation Strategy

### ✅ Phase 1: Core Foundation (COMPLETED)
1. Provider abstraction layer with Ollama support
2. Enhanced tool system with parameter validation
3. Advanced orchestrator with interpretation layer
4. Small model optimization and robust parsing

### 🚧 Phase 2: Enhanced Capabilities (IN PROGRESS)
1. Advanced context awareness and memory
2. Error diagnosis and recovery
3. Safety and security features
4. Performance optimization

### 📋 Phase 3: Advanced Features (PLANNED)
1. Multi-agent collaboration
2. Advanced learning and adaptation
3. IDE integrations
4. Plugin ecosystem

## Technology Stack
- **Language**: Python 3.11+
- **LLM Integration**: LiteLLM (provider abstraction)
- **Local Models**: Ollama
- **Database**: SQLite (context/memory)
- **Configuration**: YAML/JSON
- **CLI**: Click/Rich for user interface
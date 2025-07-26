# Enhanced Planner Integration with Execution Steps

## Overview

Successfully enhanced the JSON format to include detailed execution steps that the planner can directly execute. This allows small models like qwen3:30b to provide actionable execution information rather than just general task analysis.

## Key Changes Made

### 1. Enhanced JSON Format (`src/core/prompt_utils.py`)

Added `execution_steps` array to the analysis format:

```json
{
    "requires_tools": true/false,
    "needs_clarification": false,
    "tools_needed": ["tool1", "tool2"],
    "action_sequence": ["step1", "step2"],
    "execution_steps": [
        {
            "step": "step description",
            "tool": "tool_name", 
            "parameters": {"param1": "value1"},
            "dependencies": ["step_1"]
        }
    ],
    "priority": 1-5,
    "complexity": "low",
    "estimated_steps": 2,
    "clarification_questions": [],
    "alternatives": ["alt1"]
}
```

### 2. Planner Integration (`src/core/orchestrator.py`)

#### New Method: `_create_plan_from_execution_steps()`
- Converts `execution_steps` from analysis JSON into `TaskStep` objects
- Creates proper `TaskPlan` with specific tool names and parameters
- Maintains dependency chains for correct execution order
- Registers plan with task planner for execution

#### Enhanced Intelligent Fallback
- Updated `_create_intelligent_fallback()` to generate execution steps
- Added `_generate_tool_parameters()` for context-aware parameter generation
- Added `_get_tool_action_description()` for step descriptions

### 3. Tool Parameter Generation

Smart parameter generation based on user input:

```python
# Search tool
{"query": "extracted_search_term", "search_type": "text"}

# File tool  
{"action": "read", "path": "determined_at_runtime"}

# Git tool
{"action": "status"} # or "commit", "branch" based on input
```

## Benefits

### For Small Models (qwen3:30b)
- ✅ Clear directive format with execution step structure
- ✅ Models can provide specific tool parameters instead of vague actions
- ✅ Dependency information ensures proper execution order
- ✅ Fallback system generates executable steps even when JSON parsing fails

### For the Planner System
- ✅ Direct conversion from analysis to executable `TaskStep` objects
- ✅ No need for "determined_at_runtime" placeholders
- ✅ Specific tool parameters ready for immediate execution
- ✅ Proper dependency management from model analysis

### For Overall System
- ✅ Seamless integration between analysis and execution phases
- ✅ Reduced ambiguity in task planning
- ✅ Better utilization of small model capabilities
- ✅ Maintains backward compatibility with existing planner

## Testing Results

### Format Testing
- ✅ Enhanced JSON format includes all required fields
- ✅ execution_steps properly structured with tool/parameters/dependencies
- ✅ Compatible with existing validation logic

### Integration Testing  
- ✅ Successfully converts execution_steps to TaskStep objects
- ✅ TaskPlan creation with proper metadata and source tracking
- ✅ Dependencies preserved in task execution order
- ✅ Tool parameters passed correctly to execution engine

### Fallback Testing
- ✅ Intelligent fallback generates appropriate execution steps
- ✅ Context-aware parameter generation works correctly
- ✅ Tool action descriptions provide clear step information

## Example Flow

1. **User Input**: "find all main functions and show me the first one"

2. **Model Analysis** (qwen3:30b responds with):
```json
{
    "requires_tools": true,
    "tools_needed": ["search", "file"],
    "execution_steps": [
        {
            "step": "Search for main function definitions",
            "tool": "search",
            "parameters": {"query": "def main", "search_type": "text"},
            "dependencies": []
        },
        {
            "step": "Read the first main function file",
            "tool": "file", 
            "parameters": {"action": "read", "path": "main.py"},
            "dependencies": ["step_1"]
        }
    ],
    "complexity": "medium"
}
```

3. **Planner Conversion**: Creates TaskStep objects with specific parameters

4. **Execution**: Planner executes steps in dependency order with exact parameters

## Impact

This enhancement bridges the gap between small model capabilities and the execution requirements of the planner system. Small models can now provide detailed, actionable execution plans rather than just high-level analysis, making the system much more effective with local models like qwen3:30b.

The system maintains full backward compatibility while adding powerful new capabilities for detailed task planning and execution.
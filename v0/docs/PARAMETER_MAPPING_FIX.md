# Parameter Mapping Fix for Tool Execution

## Problem Identified

The user reported that execution plans were failing due to invalid parameters:

```json
{
  "execution_steps": [
    {
      "tool": "search",
      "parameters": {"pattern": "def main()|if __name__ == \"__main__\":|import"}
    },
    {
      "tool": "git", 
      "parameters": {"command": "status"}
    },
    {
      "tool": "file",
      "parameters": {"action": "list_structure"}
    }
  ]
}
```

**Issue**: Models were generating parameters that didn't match actual tool schemas:
- Search tool expects `query`, not `pattern`
- Git tool expects `action`, not `command`  
- File tool expects valid actions like `list`, not `list_structure`

## Solution Implemented

### 1. Parameter Validation and Fixing (`src/core/orchestrator.py`)

Added `_validate_and_fix_tool_parameters()` method that:

#### Search Tool Fixes:
```python
# Handles: pattern → query, search_term → query, type → search_type
if "query" in parameters:
    fixed_params["query"] = parameters["query"]
elif "pattern" in parameters:
    fixed_params["query"] = parameters["pattern"]  
elif "search_term" in parameters:
    fixed_params["query"] = parameters["search_term"]
```

#### Git Tool Fixes:
```python
# Handles: command → action
if "action" in parameters:
    fixed_params["action"] = parameters["action"]
elif "command" in parameters:
    fixed_params["action"] = parameters["command"]
```

#### File Tool Fixes:
```python
# Handles: list_structure → list, operation → action, filename → path
if "action" in parameters:
    action = parameters["action"]
    if action == "list_structure":
        fixed_params["action"] = "list"
    else:
        fixed_params["action"] = action
```

### 2. Enhanced Tool Descriptions (`src/core/prompt_utils.py`)

Added parameter hints to tool descriptions:
```python
if tool_name == "search":
    param_hints = " (params: query, search_type)"
elif tool_name == "git":
    param_hints = " (params: action, files, message)" 
elif tool_name == "file":
    param_hints = " (params: action, path, content)"
```

### 3. Integration with Plan Creation

Updated `_create_plan_from_execution_steps()` to automatically fix parameters:
```python
raw_parameters = exec_step.get("parameters", {})
validated_parameters = self._validate_and_fix_tool_parameters(tool, raw_parameters)
```

## Results

### Before Fix:
```
❌ search: {'pattern': 'def main()...'} → Tool execution fails
❌ git: {'command': 'status'} → Tool execution fails  
❌ file: {'action': 'list_structure'} → Tool execution fails
```

### After Fix:
```
✅ search: {'pattern': '...'} → {'query': '...', 'search_type': 'text', 'file_pattern': '*'}
✅ git: {'command': 'status'} → {'action': 'status'}
✅ file: {'action': 'list_structure'} → {'action': 'list', 'path': '.'}
```

## Testing Results

- ✅ **User's failing case**: All 3 invalid parameter sets now work correctly
- ✅ **Edge cases**: 5/5 parameter mapping edge cases handled properly
- ✅ **End-to-end**: TaskPlan creation successful with executable steps
- ✅ **Tool execution**: All parameters now match actual tool schemas

## Benefits

### For Small Models:
- Models can use intuitive parameter names (e.g., `pattern`, `command`)
- Parameter validation happens automatically
- No need to memorize exact tool schemas

### For the System:
- Robust parameter handling prevents execution failures
- Backward compatibility with various parameter naming conventions
- Clear debugging output showing parameter fixes

### For Users:
- Plans no longer fail due to parameter mismatches
- Execution proceeds smoothly with corrected parameters
- Better reliability with small models like qwen3:30b

## Impact

This fix resolves the core issue where model-generated execution steps failed due to parameter schema mismatches. The system now automatically corrects common parameter naming variations, making it much more robust and user-friendly when working with small local models that may not perfectly adhere to tool schemas.

The parameter mapping fix ensures that the enhanced planner integration works reliably in practice, not just in theory.
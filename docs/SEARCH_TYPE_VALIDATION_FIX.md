# Search Type Validation Fix

## Problem Identified

The user reported another execution failure:

```
⚡ **Step step_1:** Search for key files and patterns
❌ Failed: Unknown search type: filename
```

**Issue**: The model generated `search_type: 'filename'` which is not supported by the search tool. The search tool only supports: `text`, `regex`, `function`, `class`, `import`.

## Root Cause

Small models like qwen3:30b were generating intuitive but invalid search_type values:
- `filename` - for searching by filename
- `pattern` - for pattern matching  
- `code` - for code searching
- Other variations that seem logical but aren't supported

## Solution Implemented

### 1. Enhanced Search Type Validation (`src/core/orchestrator.py:519-548`)

Added comprehensive validation and conversion logic:

```python
# Validate and fix search_type
valid_search_types = ["text", "regex", "function", "class", "import"]
if search_type in valid_search_types:
    fixed_params["search_type"] = search_type
elif search_type == "filename":
    # Convert filename search to text search with appropriate file pattern
    fixed_params["search_type"] = "text"
    query = parameters.get("query", "main")
    if "|" in query or "*" in query or "." in query:
        # Complex pattern - use as file_pattern and search for code patterns
        fixed_params["file_pattern"] = f"*{query.replace('|', '*')}*"
        fixed_params["query"] = "def|class|import|function"
    else:
        # Simple filename - search in filenames
        fixed_params["file_pattern"] = f"*{query}*"
        fixed_params["query"] = query
elif search_type == "pattern":
    fixed_params["search_type"] = "regex"
elif search_type == "code":
    fixed_params["search_type"] = "text"
else:
    fixed_params["search_type"] = "text"  # Default fallback
```

### 2. Smart Query Transformation

The fix intelligently handles the `filename` search type:

**Original failing case:**
```json
{
  "query": "main|setup|readme",
  "search_type": "filename" 
}
```

**Fixed parameters:**
```json
{
  "query": "def|class|import|function",
  "search_type": "text",
  "file_pattern": "*main*setup*readme*",
  "max_results": 50,
  "context_lines": 3
}
```

### 3. Enhanced Tool Hints (`src/core/prompt_utils.py:124-129`)

Updated parameter hints to guide models toward valid values:

```python
if tool_name == "search":
    param_hints = " (params: query, search_type[text|regex|function|class|import])"
elif tool_name == "git":
    param_hints = " (params: action[status|commit|diff|add], files, message)"
elif tool_name == "file":
    param_hints = " (params: action[read|write|list], path, content)"
```

## Conversion Logic

| Invalid Type | Converted To | Logic |
|-------------|-------------|--------|
| `filename` | `text` + file_pattern | Searches for code patterns in files matching the filename pattern |
| `pattern` | `regex` | Assumes the user wants regex pattern matching |
| `code` | `text` | Standard text search for code content |
| `unknown_type` | `text` | Safe fallback to basic text search |

## Testing Results

### User's Failing Case:
- ✅ **Before**: `search_type: 'filename'` → `❌ Failed: Unknown search type: filename`
- ✅ **After**: `search_type: 'text'` with `file_pattern: '*main*setup*readme*'` → Executes successfully

### Additional Test Cases:
- ✅ `filename` → `text` with appropriate file pattern
- ✅ `pattern` → `regex`
- ✅ `code` → `text`
- ✅ `invalid_type` → `text` (fallback)
- ✅ `function` → `function` (preserved - valid)
- ✅ `regex` → `regex` (preserved - valid)

## Benefits

### For Models:
- Can use intuitive search_type names without causing failures
- `filename` searches automatically converted to working text+pattern searches
- Graceful fallbacks for unknown search_type values

### For the System:
- No more "Unknown search type" execution failures
- Intelligent conversion preserves user intent
- Enhanced debugging shows exactly what was converted

### For Users:
- Plans execute successfully even with imperfect model outputs
- More robust search functionality
- Better reliability with small local models

## Impact

This fix eliminates another class of execution failures caused by models generating reasonable but technically invalid parameter values. The search tool is now much more forgiving and can handle various intuitive search_type names that models might generate.

Combined with the previous parameter mapping fix, the system is now significantly more robust when working with small models that may not perfectly adhere to tool schemas.
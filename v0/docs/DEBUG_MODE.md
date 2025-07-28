# Debug Mode

The coding agent now supports a debug mode that controls the visibility of debug print statements throughout the application.

## Configuration

Debug mode can be enabled in three ways (in order of precedence):

### 1. Environment Variable (Highest Priority)
```bash
DEBUG_MODE=true python main.py
```

Accepted values: `true`, `1`, `yes`, `on` (case insensitive)

### 2. Configuration File
In `config.yaml`:
```yaml
agent:
  debug_mode: true
```

### 3. Programmatic Control
```python
from core.debug import set_debug_mode
set_debug_mode(True)
```

## Usage

When debug mode is enabled, you'll see detailed debug output like:
- `🔍 DEBUG: Processing request: ...`
- `🔧 DEBUG: Generated content for file.py: 150 characters`
- JSON parsing details and fallback strategies
- Tool execution parameters and results
- Model selection and response analysis

When debug mode is disabled, these messages are hidden for cleaner output.

## Benefits

- **Development**: Enable debug mode during development to see detailed execution flow
- **Production**: Disable debug mode in production for cleaner logs
- **Debugging**: Quickly toggle debug output when investigating issues
- **Performance**: Avoid string formatting overhead when debug is disabled

## Implementation

The debug system uses a global cache that checks configuration once and reuses the result. The cache can be reset with `reset_debug_cache()` if needed.

All debug output goes through the `debug_print()` function which respects the debug mode setting.
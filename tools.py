import os, json, glob

# Global context for change tracking
_current_session_id = None
_current_user_query = None

def set_session_context(session_id, user_query):
    """Set the current session context for change tracking."""
    global _current_session_id, _current_user_query
    _current_session_id = session_id
    _current_user_query = user_query

def _track_change(file_path, tool_name, tool_args):
    """Capture file state before modification."""
    if _current_session_id is None:
        return None  # No session, don't track

    try:
        content_before = open(file_path).read() if os.path.exists(file_path) else None
        return content_before
    except:
        return None

def _save_change(file_path, content_before, tool_name, tool_args):
    """Save the change after modification."""
    if _current_session_id is None:
        return

    try:
        from index import save_change
        content_after = open(file_path).read() if os.path.exists(file_path) else None
        save_change(_current_session_id, file_path, content_before, content_after,
                   tool_name, tool_args, _current_user_query or "")
    except Exception as e:
        print(f"Warning: Could not save change history: {e}")

def explain_steps(explanation): print(f"\n{explanation}\n"); return {"status": "explained"}

def summarize_and_suggest(summary=None, suggestion=None, suggestions=None):
    """Summarize and suggest next steps. Flexible parameter handling."""
    final_summary = summary or "Task completed."
    final_suggestion = suggestion or suggestions or "Continue with the next task."
    print(f"\n=== Summary ===\n{final_summary}\n\n=== Suggestion ===\n{final_suggestion}\n")
    return {"status": "complete"}
def read_file(path): return {"content": open(path).read()} if os.path.exists(path) else {"error": "not found"}

def _normalize_file_content(path, content):
    """Normalize indentation for code files that may have been mangled by JSON parsing."""
    # Detect language from file extension
    is_python = path.endswith('.py')
    is_c_style = path.endswith(('.js', '.ts', '.java', '.go', '.c', '.cpp', '.cs', '.jsx', '.tsx'))

    if not (is_python or is_c_style):
        return content  # Not a code file we need to fix

    # If content is all on one line (from JSON normalization), it's nearly impossible
    # to perfectly reconstruct. Just do basic line breaking and let the indentation
    # logic handle it.
    if '\n' not in content:
        if is_python:
            import re
            # Add line breaks at obvious boundaries
            # After colons (but this will be imperfect)
            content = re.sub(r':\s+', ':\n', content)
            # Before top-level keywords (very rough heuristic)
            content = re.sub(r'\s+(class |def |import |from )', r'\n\1', content)
        elif is_c_style:
            import re
            content = re.sub(r'\{\s*', '{\n', content)
            content = re.sub(r'\}\s*', '}\n', content)
            content = re.sub(r';\s*', ';\n', content)

    lines = content.split('\n')
    if not lines:
        return content

    # Find the minimum indentation (excluding empty lines)
    min_indent = float('inf')
    indents = []
    for line in lines:
        if not line.strip():
            continue
        indent = len(line) - len(line.lstrip())
        indents.append(indent)
        if indent < min_indent:
            min_indent = indent

    if min_indent == float('inf'):
        min_indent = 0

    # Check if all lines are unindented (all at column 0)
    all_unindented = all(ind == 0 for ind in indents) if indents else True

    # Apply language-specific normalization (no base indent for files)
    if is_python:
        return _normalize_python_indent(lines, '', min_indent, all_unindented)
    elif is_c_style:
        return _normalize_c_style_indent(lines, '', min_indent, all_unindented)

    return content

def create_file(path, content):
    content_before = _track_change(path, "create_file", {"path": path, "content": content})
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)

    # Normalize indentation for code files (fixes JSON whitespace mangling)
    normalized_content = _normalize_file_content(path, content)

    open(path, "w").write(normalized_content)
    _save_change(path, content_before, "create_file", {"path": path, "content": content})
    return {"status": "written"}

def _normalize_python_indent(new_lines, base_indent, min_indent, all_unindented):
    """Normalize indentation for Python code (functions or whole files)."""
    normalized_lines = []
    is_function = bool(base_indent)  # If base_indent exists, we're in a function
    current_level = 1 if is_function else 0  # Functions start at level 1

    for i, line in enumerate(new_lines):
        if not line.strip():  # Empty line
            normalized_lines.append('')
        elif i == 0 and is_function:  # First line of function (def statement)
            normalized_lines.append(base_indent + line.lstrip())
        else:  # Body lines (or all lines for files)
            stripped = line.lstrip()

            if all_unindented:
                # AI gave us unindented code - detect structure from Python syntax
                indent_spaces = '    ' * current_level
                normalized_lines.append(base_indent + indent_spaces + stripped)

                # Adjust level for next line based on this line
                if stripped.endswith(':'):
                    current_level += 1
                # Detect dedent keywords (else, elif, except, finally, etc.)
                elif stripped.startswith(('else:', 'elif ', 'except:', 'except ', 'finally:', 'case ')):
                    # These should be at previous level
                    min_level = 1 if is_function else 0
                    current_level = max(min_level, current_level - 1)
                    # Rewrite this line with corrected indent
                    indent_spaces = '    ' * current_level
                    normalized_lines[-1] = base_indent + indent_spaces + stripped
                    current_level += 1  # Next line goes back in
                # Simple heuristic: if line doesn't end with ':' and previous didn't,
                # we might be dedenting
                elif i > 1 and not new_lines[i-1].strip().endswith(':') and current_level > (1 if is_function else 0):
                    # Check if this looks like a new statement at base level
                    if stripped.startswith(('return ', 'break', 'continue', 'pass', 'raise ', 'class ', 'def ', 'import ', 'from ')):
                        min_level = 1 if is_function else 0
                        current_level = max(min_level, current_level - 1)
                        normalized_lines[-1] = base_indent + '    ' * current_level + stripped
            else:
                # AI gave us properly indented code - preserve relative structure
                current_indent = len(line) - len(line.lstrip())
                relative_indent = current_indent - min_indent
                extra_indent = '    ' if is_function else ''
                normalized_lines.append(base_indent + extra_indent + ' ' * relative_indent + stripped)

    return '\n'.join(normalized_lines)

def _normalize_c_style_indent(new_lines, base_indent, min_indent, all_unindented):
    """Normalize indentation for C-style languages (functions or whole files)."""
    normalized_lines = []
    is_function = bool(base_indent)  # If base_indent exists, we're in a function
    current_level = 0  # Track nesting level for unindented code

    for i, line in enumerate(new_lines):
        if not line.strip():  # Empty line
            normalized_lines.append('')
        elif i == 0 and is_function:  # First line of function (function signature)
            normalized_lines.append(base_indent + line.lstrip())
            # Check if opening brace is on same line
            if '{' in line:
                current_level = 1
        else:  # Body lines (or all lines for files)
            stripped = line.lstrip()

            if all_unindented:
                # AI gave us unindented code - detect structure from braces
                # Decrease indent if line starts with closing brace
                if stripped.startswith('}'):
                    current_level = max(0, current_level - 1)

                indent_spaces = '    ' * current_level
                normalized_lines.append(base_indent + indent_spaces + stripped)

                # Increase indent if line ends with opening brace
                if stripped.endswith('{'):
                    current_level += 1
                # Handle closing brace that's already been written (decrease for next line)
                # (already handled above)
            else:
                # AI gave us properly indented code - preserve relative structure
                current_indent = len(line) - len(line.lstrip())
                relative_indent = current_indent - min_indent
                extra_indent = '    ' if is_function else ''
                normalized_lines.append(base_indent + extra_indent + ' ' * relative_indent + stripped)

    return '\n'.join(normalized_lines)

def replace_function(path, function_name, new_code):
    """Replace entire function by name, preserving proper language-specific indentation"""
    import re

    content_before = _track_change(path, "replace_function",
                                   {"path": path, "function_name": function_name, "new_code": new_code})
    if not os.path.exists(path):
        return {"error": "file not found"}
    current = open(path).read()

    # Detect language from file extension
    is_python = path.endswith('.py')
    is_c_style = path.endswith(('.js', '.ts', '.java', '.go', '.c', '.cpp', '.cs', '.jsx', '.tsx'))

    # Language-specific function patterns and matching
    if is_python:
        # For Python: find def line, then capture all indented lines that follow
        def_pattern = rf'^([ \t]*)def {re.escape(function_name)}\([^)]*\):[^\n]*$'
        match = re.search(def_pattern, current, re.MULTILINE)

        if not match:
            return {"error": f"function '{function_name}' not found"}

        # Get the indentation level of the def statement
        base_indent = match.group(1)
        def_start = match.start()
        def_end = match.end()

        # Find all lines that belong to this function (more indented than def)
        lines = current[def_end:].split('\n')
        function_lines = [current[def_start:def_end]]

        if lines:
            # Determine expected body indent (should be base + 4 spaces or base + 1 tab)
            min_body_indent = len(base_indent) + 1

            for line in lines:
                # Empty lines are part of function
                if not line.strip():
                    function_lines.append(line)
                    continue

                # Count leading whitespace
                line_indent = len(line) - len(line.lstrip())

                # If line is indented more than the def, it's part of the function
                if line_indent >= min_body_indent:
                    function_lines.append(line)
                else:
                    # Found a line at same or less indentation - function ends here
                    break

        full_match = '\n'.join(function_lines)
        match_start = def_start
        match_end = def_start + len(full_match)

    elif is_c_style:
        # For C-style: find function signature, then match braces
        sig_pattern = rf'^([ \t]*)(?:[\w<>[\],\s]+\s+)?{re.escape(function_name)}\([^)]*\)\s*\{{'
        match = re.search(sig_pattern, current, re.MULTILINE)

        if not match:
            return {"error": f"function '{function_name}' not found"}

        base_indent = match.group(1)
        match_start = match.start()

        # Find matching closing brace by counting braces
        brace_count = 1
        pos = match.end()

        while pos < len(current) and brace_count > 0:
            if current[pos] == '{':
                brace_count += 1
            elif current[pos] == '}':
                brace_count -= 1
            pos += 1

        if brace_count != 0:
            return {"error": f"unmatched braces in function '{function_name}'"}

        match_end = pos
        full_match = current[match_start:match_end]

    else:
        return {"error": "unsupported file type"}

    # Parse the new implementation and apply proper indentation
    new_lines = new_code.split('\n')

    # Find the minimum indentation in the new implementation (excluding empty lines and first line)
    min_indent = float('inf')
    indents = []  # Track all indentation levels
    for i, line in enumerate(new_lines):
        if i == 0 or not line.strip():  # Skip first line and empty lines
            continue
        indent = len(line) - len(line.lstrip())
        indents.append(indent)
        if indent < min_indent:
            min_indent = indent

    # If no body lines found, use 0 as minimum
    if min_indent == float('inf'):
        min_indent = 0

    # Check if AI gave us unindented code (all lines at column 0)
    all_unindented = all(ind == 0 for ind in indents) if indents else True

    # Rebuild with proper indentation based on language
    if is_python:
        normalized_impl = _normalize_python_indent(new_lines, base_indent, min_indent, all_unindented)
    elif is_c_style:
        normalized_impl = _normalize_c_style_indent(new_lines, base_indent, min_indent, all_unindented)
    else:
        normalized_impl = new_code

    # Replace the entire function using position-based replacement (safer than string replace)
    updated = current[:match_start] + normalized_impl + '\n' + current[match_end:]
    open(path, "w").write(updated)
    _save_change(path, content_before, "replace_function",
                {"path": path, "function_name": function_name, "new_code": new_code})
    return {"status": "edited", "function": function_name}

def insert_after_line(path, search_line, new_content):
    """Insert content after a line containing search text"""
    content_before = _track_change(path, "insert_after_line",
                                   {"path": path, "search_line": search_line, "new_content": new_content})
    if not os.path.exists(path):
        return {"error": "file not found"}
    lines = open(path).read().split('\n')

    for i, line in enumerate(lines):
        if search_line.strip() in line:
            lines.insert(i + 1, new_content)
            open(path, "w").write('\n'.join(lines))
            _save_change(path, content_before, "insert_after_line",
                        {"path": path, "search_line": search_line, "new_content": new_content})
            return {"status": "inserted", "after_line": i + 1}

    return {"error": f"line containing '{search_line}' not found"}

def replace_between_markers(path, start_marker, end_marker, new_content):
    """Replace content between two marker lines"""
    content_before = _track_change(path, "replace_between_markers",
                                   {"path": path, "start_marker": start_marker, "end_marker": end_marker, "new_content": new_content})
    if not os.path.exists(path):
        return {"error": "file not found"}
    current = open(path).read()

    start_pos = current.find(start_marker)
    if start_pos == -1:
        return {"error": f"start marker '{start_marker}' not found"}

    end_pos = current.find(end_marker, start_pos + len(start_marker))
    if end_pos == -1:
        return {"error": f"end marker '{end_marker}' not found"}

    updated = current[:start_pos + len(start_marker)] + '\n' + new_content + '\n' + current[end_pos:]
    open(path, "w").write(updated)
    _save_change(path, content_before, "replace_between_markers",
                {"path": path, "start_marker": start_marker, "end_marker": end_marker, "new_content": new_content})
    return {"status": "edited", "between_markers": True}
def search_code(query): from index import search; return {"results": search(query)}
def respond_to_user(message): print(f"\n{message}\n"); return {"message": message}

def list_files(pattern="**/*.py"):
    """List files matching a glob pattern."""
    import subprocess
    try:
        # Get git-tracked files
        result = subprocess.run(['git', 'ls-files'], capture_output=True, text=True, check=True)
        all_files = result.stdout.strip().split('\n')

        # Filter by pattern
        from fnmatch import fnmatch
        matching_files = [f for f in all_files if fnmatch(f, pattern)]

        output = f"Found {len(matching_files)} files matching '{pattern}':\n"
        for f in matching_files[:50]:  # Limit to 50 files
            output += f"  {f}\n"
        if len(matching_files) > 50:
            output += f"  ... and {len(matching_files) - 50} more\n"

        print(output)
        return {"files": matching_files, "count": len(matching_files), "message": output}
    except Exception as e:
        error_msg = f"Error listing files: {e}"
        print(error_msg)
        return {"error": str(e), "message": error_msg}

def show_history(limit=10):
    """Show recent change history."""
    from index import get_change_history
    import time
    history = get_change_history(limit=limit)
    if not history:
        return {"message": "No changes in history"}

    output = "Recent changes:\n"
    for change in history:
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(change["timestamp"]))
        output += f"  [{change['id']}] {timestamp} - {change['tool_name']} on {change['file_path']}\n"

    print(output)
    return {"history": history, "message": output}

def undo(change_id=None):
    """Undo the most recent change or a specific change by ID."""
    from index import undo_change
    result = undo_change(change_id)
    if "error" in result:
        msg = f"Cannot undo: {result['error']}"
        print(msg)
        return {"error": result["error"], "message": msg}
    else:
        msg = f"Undone change {result['change_id']} to {result['file']}"
        print(msg)
        return {"status": "undone", "message": msg, "file": result["file"]}

def redo(change_id=None):
    """Redo a previously undone change."""
    from index import redo_change
    result = redo_change(change_id)
    if "error" in result:
        msg = f"Cannot redo: {result['error']}"
        print(msg)
        return {"error": result["error"], "message": msg}
    else:
        msg = f"Redone change {result['change_id']} to {result['file']}"
        print(msg)
        return {"status": "redone", "message": msg, "file": result["file"]}

TOOLS = {f.__name__: f for f in [explain_steps, summarize_and_suggest, read_file, create_file, replace_function, insert_after_line, replace_between_markers, search_code, respond_to_user, list_files, show_history, undo, redo]}

def execute(tool_name, params):
    if tool_name in TOOLS:
        # Fix common LLM parameter name errors
        if tool_name == "replace_function":
            # Map incorrect parameter names to correct ones
            corrections = {
                'file_path': 'path',
                'new_implementation': 'new_code',
                'new_content': 'new_code',
                'docstring': 'new_code',
                'function': 'function_name'
            }
            for wrong_name, correct_name in corrections.items():
                if wrong_name in params and correct_name not in params:
                    params[correct_name] = params.pop(wrong_name)

        return TOOLS[tool_name](**params)
    else:
        return {"error": "unknown tool"}

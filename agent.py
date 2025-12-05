import json, requests, os, uuid, sys
from tools import execute, set_session_context
from index import save_query,init_db, watch, set_db, index_file, create_session
from vectorize import rebuild_tfidf_model

# Global debug flag
DEBUG = False

def debug_print(*args, **kwargs):
    """Print only if debug mode is enabled."""
    if DEBUG:
        print("[DEBUG]", *args, **kwargs)

def load_tools():
    return json.load(open("tools.json"))

def load_config():
    """Load configuration from config.json with individual defaults."""
    config_path = "config.json"
    config = {}

    if os.path.exists(config_path):
        with open(config_path) as f:
            config = json.load(f)

    # Apply individual defaults for missing keys
    config.setdefault("model", "qwen3:14b")
    config.setdefault("base_url", "http://localhost:11434")
    config.setdefault("db_name", "index.db")
    config.setdefault("temperature", 0.1)
    config.setdefault("debounce_seconds", 30)
    config.setdefault("max_keywords", 10)
    config.setdefault("debug", False)
    config.setdefault("intelligent_context", True)  # Use two-stage AI context retrieval

    return config

class LLMProvider:
    def generate(self, prompt): raise NotImplementedError

class OllamaProvider(LLMProvider):
    def __init__(self, model="qwen3:14b", base_url="http://localhost:11434"):
        self.model = model; self.base_url = base_url
    def ensure_loaded(self):
        try:
            resp = requests.post(f"{self.base_url}/api/generate", json={"model": self.model, "prompt": "test", "stream": False}, timeout=5)
            return resp.status_code == 200
        except:
            print(f"Loading model {self.model}..."); import subprocess
            subprocess.run(["ollama", "run", self.model, "hello"], capture_output=True, timeout=60)
            return True
    def generate(self, prompt, temperature=0.1):
        try:
            payload = {
                "model": self.model,
                "prompt": prompt,
                "stream": True,
                "options": {
                    "temperature": temperature,
                }
            }
            resp = requests.post(f"{self.base_url}/api/generate", json=payload, timeout=120, stream=True)
            full_response = ""
            for line in resp.iter_lines():
                if line:
                    chunk = json.loads(line)
                    if "response" in chunk:
                        full_response += chunk["response"]
            return full_response
        except Exception as e: print(f"LLM error: {e}"); return ""

def create_prompt(user_input, context, tools):
    """Create prompt for main execution stage."""
    def format_tool(t):
        import json
        params = ', '.join([f"{k} ({v.get('description', '')})" for k, v in t.get('params', {}).items()])
        return f"{t['name']}: {t['description']}\n  Parameters: {params}"


    tool_desc = "\n".join([format_tool(t) for t in tools])

    # Use refined prompt if available
    actual_prompt = context.get('refined_prompt', user_input)
    clarifications = context.get('clarifications', [])
    clarifications_text = "\n".join([f"- {c}" for c in clarifications]) if clarifications else ""

    context_text = f"""Context files: {context['files']}
Recent queries: {context['recent_queries']}"""

    if clarifications_text:
        context_text += f"\n\nClarifications made during analysis:\n{clarifications_text}"

    return f"""You are a coding assistant. Generate a plan as JSON array of tool calls.

Available tools:
{tool_desc}

{context_text}

User: {user_input}
{f"Refined interpretation: {actual_prompt}" if actual_prompt != user_input else ""}

Example JSON format:
[
  {{"tool": "explain_steps", "params": {{"explanation": "I will..."}}}},
  {{"tool": "read_file", "params": {{"path": "example.py"}}}},
  {{"tool": "summarize_and_suggest", "params": {{"summary": "...", "suggestion": "..."}}}}
]

CRITICAL: You MUST use the EXACT parameter names shown above and in the tool descriptions. Do NOT rename, modify, or invent parameter names.

Respond ONLY with JSON array. Your plan MUST begin with "explain_steps" and end with "summarize_and_suggest".
"""


def create_search_prompt(user_input, recent_queries, search_tools):
    """Create prompt for Stage 1: Search strategy generation."""
    def format_tool(t):
        params = ', '.join([f"{k} ({v.get('description', '')})" for k, v in t.get('params', {}).items()])
        return f"{t['name']}: {t['description']}\n  Parameters: {params}"

    tool_desc = "\n".join([format_tool(t) for t in search_tools])

    return f"""You are a search strategist. Analyze the user's request and generate strategic search patterns to find relevant files.

Available tools:
{tool_desc}

Recent queries (for context): {recent_queries}

User request: {user_input}

Think about:
- What file names might be relevant? (use regex patterns)
- What code patterns should we search for in contents? (class definitions, function names, imports)
- What keywords describe the domain?

Respond ONLY with JSON array like: [{{"tool": "generate_search_terms", "params": {{"reasoning": "...", "file_patterns": [...], "content_patterns": [...], "keywords": [...]}}}}]
"""


def create_refinement_prompt(user_input, files_summary, recent_queries, refinement_tools):
    """Create prompt for Stage 2: Prompt refinement."""
    def format_tool(t):
        params = ', '.join([f"{k} ({v.get('description', '')})" for k, v in t.get('params', {}).items()])
        return f"{t['name']}: {t['description']}\n  Parameters: {params}"

    tool_desc = "\n".join([format_tool(t) for t in refinement_tools])

    files_text = "\n".join([
        f"File: {f['path']}\nReasons: {', '.join(f['match_reasons'])}\nPreview: {f['content_preview'][:200]}..."
        for f in files_summary[:3]  # Show top 3 files
    ])

    return f"""You are a requirements analyst. Refine the user's request to be more specific and actionable based on discovered files.

Available tools:
{tool_desc}

Discovered relevant files:
{files_text}

Recent queries (for context): {recent_queries}

Original user request: {user_input}

Based on the files found, refine the request to be:
- More specific and technical
- Include relevant file/function names if appropriate
- Make any necessary assumptions explicit

Respond ONLY with JSON array like: [{{"tool": "refine_prompt", "params": {{"refined_prompt": "...", "clarifications": [...]}}}}]
"""

def parse_plan_json(plan_json):
    """Parse and clean JSON response from LLM."""
    import re

    debug_print(f"Raw LLM response length: {len(plan_json)} chars")

    # Clean and extract JSON
    json_match = re.search(r'```(?:json)?\s*(\[.*?\])\s*```', plan_json, re.DOTALL)
    if json_match:
        plan_json = json_match.group(1)
    elif plan_json.strip().startswith('[') and not plan_json.strip().endswith(']'):
        bracket_match = re.search(r'\[.*\]', plan_json, re.DOTALL)
        if bracket_match:
            plan_json = bracket_match.group(0)

    # Try to parse JSON as-is first (LLM usually outputs valid JSON)
    try:
        plan = json.loads(plan_json)
        debug_print(f"Parsed plan with {len(plan)} steps")
        return plan
    except Exception as e:
        debug_print(f"First parse attempt failed: {e}")

        # Fix common LLM JSON mistakes
        plan_json_fixed = plan_json

        # Fix trailing commas
        plan_json_fixed = re.sub(r',\s*([}\]])', r'\1', plan_json_fixed)

        # Fix invalid escape sequences: \' is not valid in JSON
        # Replace \' with just ' (inside double-quoted strings, single quotes don't need escaping)
        plan_json_fixed = plan_json_fixed.replace("\\'", "'")

        try:
            plan = json.loads(plan_json_fixed)
            debug_print(f"Parsed plan after fixing with {len(plan)} steps")
            return plan
        except Exception as e2:
            # Show more context in error
            error_msg = str(e)
            # Extract position from error if available
            import re as re_module
            pos_match = re_module.search(r'char (\d+)', error_msg)
            if pos_match:
                pos = int(pos_match.group(1))
                context_start = max(0, pos - 100)
                context_end = min(len(plan_json_fixed), pos + 100)
                context = plan_json_fixed[context_start:context_end]
                print(f"Parse error: {error_msg}")
                print(f"Context around position {pos}:")
                print(f"...{repr(context)}...")
                print(f"\nFirst 200 chars of JSON: {repr(plan_json_fixed[:200])}")
            else:
                print(f"Parse error: {error_msg}\n{plan_json_fixed[:300]}...")
            return None

def execute_plan(plan, tools, user_input):
    """Execute a plan with user approval for destructive operations."""
    if not isinstance(plan, list):
        print("Plan must be array")
        return []

    # Ensure explain_steps is always first
    if not plan or plan[0].get('tool') != 'explain_steps':
        plan.insert(0, {"tool": "explain_steps", "params": {"explanation": f"Processing: {user_input}"}})

    has_destructive = any(next((t for t in tools if t['name'] == step.get('tool')), {}).get('destructive') for step in plan)
    plan_approved = not has_destructive

    response_parts = []
    for step in plan:
        try:
            tool_name = step.get('tool')
            params = step.get('params', {})
            if not tool_name:
                continue

            debug_print(f"Executing tool: {tool_name} with params: {params}")

            if tool_name == 'explain_steps':
                result = execute(tool_name, params)
                print(f"[{tool_name}] {result}")
                if has_destructive:
                    if input(f"Plan has destructive steps. Execute plan? (y/n): ").lower() == 'y':
                        plan_approved = True

            elif plan_approved:
                result = execute(tool_name, params)
                if tool_name != 'read_file':
                    print(f"[{tool_name}] {result}")
                # Collect response values for params marked as string type in tool config
                if isinstance(result, dict) and tool_name != "create_file":
                    tool_config = next((t for t in tools if t['name'] == tool_name), None)
                    if tool_config and 'params' in tool_config:
                        for param_name, param_config in tool_config['params'].items():
                            if param_config.get('type') == 'string' and param_name in result:
                                value = result[param_name]
                                if isinstance(value, str) and value:
                                    response_parts.append(value)

        except Exception as e:
            print(f"Tool error ({tool_name}): {e}")
            debug_print(f"Full step data: {step}")

    return response_parts

def run(user_input, llm_provider=None, config=None):
    """Main execution function for processing user input."""
    try:
        import time
        from database import get_db

        if config is None:
            config = load_config()

        # Create a new session for this interaction
        session_id = str(uuid.uuid4())
        debug_print(f"Session ID: {session_id}")
        create_session(session_id, user_input[:100])
        set_session_context(session_id, user_input)

        # Benchmark: Start
        db = get_db()
        db.log_benchmark(session_id, 'start', time.time())

        # Get context and generate plan
        llm = llm_provider or OllamaProvider()
        tools = load_tools()

        # Choose context retrieval strategy
        if config.get("intelligent_context", True):
            print("🔍 Analyzing request and searching codebase...")
            db.log_benchmark(session_id, 'context_start', time.time())
            from intelligent_context import intelligent_get_context_with_progress
            context = intelligent_get_context_with_progress(user_input, llm, config, session_id, limit_files=5)
            db.log_benchmark(session_id, 'context_end', time.time())

            if context.get('clarifications'):
                print(f"✓ Found {len(context['files'])} relevant files")
                if config.get("debug", False):
                    print(f"   Refined: {context.get('refined_prompt', user_input)[:100]}...")
        else:
            from context import get_context
            debug_print("Using simple keyword-based context retrieval")
            context = get_context(user_input)

        debug_print(f"Context files: {len(context['files'])} files")
        debug_print(f"Recent queries: {len(context['recent_queries'])} queries")

        prompt = create_prompt(user_input, context, tools)
        debug_print(f"Prompt length: {len(prompt)} chars")

        print("🤖 Generating execution plan...")
        db.log_benchmark(session_id, 'plan_generation_start', time.time())
        plan_json = llm.generate(prompt, temperature=config.get("temperature", 0.1))
        db.log_benchmark(session_id, 'plan_generation_end', time.time())
        if not plan_json:
            print("No response from LLM")
            return

        # Parse plan
        plan = parse_plan_json(plan_json)
        if plan is None:
            return

        print(f"✓ Plan ready ({len(plan)} steps)\n")

        # Execute plan
        response_parts = execute_plan(plan, tools, user_input)

        # Save query and response
        if response_parts:
            response_text = " | ".join(response_parts)
        else:
            executed_tools = [step.get('tool') for step in plan if step.get('tool')]
            response_text = f"Executed: {', '.join(executed_tools)}" if executed_tools else "No response"
        save_query(user_input, response_text)

        # Clear session context
        set_session_context(None, None)

    except Exception as e:
        print(f"Agent error: {e}")
        set_session_context(None, None)

def ensure_files_indexed():
    """Ensure all git-tracked files are indexed, even if TF-IDF model is cached."""
    import subprocess
    from index import _last_index_time
    try:
        result = subprocess.run(['git', 'ls-files'], capture_output=True, text=True, check=True)
        files = [f for f in result.stdout.strip().split('\n') if f.endswith(('.py', '.js', '.ts', '.java', '.go'))]
        # Clear debounce to allow batch indexing
        _last_index_time.clear()
        for fpath in files:
            if os.path.exists(fpath):
                index_file(fpath)
    except:
        pass

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="AI Coding Agent")
    parser.add_argument("--debug", action="store_true", help="Enable debug output")
    args = parser.parse_args()

    config = load_config()

    # Command-line flag overrides config file
    if args.debug:
        config["debug"] = True

    # Set global debug flag
    DEBUG = config["debug"] == "True"

    set_db(config["db_name"])

    # Apply config settings
    from index import set_debounce, set_max_keywords
    set_debounce(config["debounce_seconds"])
    set_max_keywords(config["max_keywords"])

    init_db()

    if DEBUG:
        print(f"Debug mode enabled. Config: {config}")

    # Smart rebuild: only if model doesn't exist or is stale
    # Pass index_file as callback to avoid circular dependency
    rebuild_tfidf_model(force=False, reindex_callback=index_file)
    # Ensure files are indexed even if model was cached
    ensure_files_indexed()
    observer = watch()
    llm = OllamaProvider(model=config["model"], base_url=config["base_url"])

    print("Checking model availability...")
    llm.ensure_loaded()
    print("Ready!")
    try:
        while True: run(input("\n> "), llm, config)
    except KeyboardInterrupt: observer.stop()

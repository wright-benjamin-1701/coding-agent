"""
Intelligent two-stage context retrieval system.

Stage 1: AI generates search strategies (regex patterns, search terms)
Stage 2: AI refines prompt based on found files
Result: Highly relevant context for the main agent
"""

import json
import re
import os
from database import get_db
from vectorize import extract_top_keywords


# ===== Stage 1: Search Strategy Tools =====

def generate_search_terms(reasoning, file_patterns=None, content_patterns=None, keywords=None):
    """
    Generate search strategy for finding relevant files.

    Args:
        reasoning: Explanation of search strategy
        file_patterns: List of regex patterns to match filenames (e.g., [".*test.*\\.py", "config\\..*"])
        content_patterns: List of regex patterns to search file contents
        keywords: List of keywords for database lookup

    Returns:
        Search strategy dict
    """
    return {
        "reasoning": reasoning,
        "file_patterns": file_patterns or [],
        "content_patterns": content_patterns or [],
        "keywords": keywords or []
    }


SEARCH_TOOLS = {
    "generate_search_terms": generate_search_terms
}


def load_search_tools():
    """Load tool definitions for search stage."""
    return [
        {
            "name": "generate_search_terms",
            "description": "Generate strategic search patterns to find relevant files for the user's request",
            "destructive": False,
            "params": {
                "reasoning": {
                    "type": "string",
                    "description": "Explain your search strategy and why these patterns will find relevant files"
                },
                "file_patterns": {
                    "type": "array",
                    "description": "Regex patterns to match filenames (e.g., ['.*test.*\\\\.py', 'config\\\\..*'])"
                },
                "content_patterns": {
                    "type": "array",
                    "description": "Regex patterns to search within file contents (e.g., ['class\\\\s+\\\\w+Auth', 'def\\\\s+authenticate'])"
                },
                "keywords": {
                    "type": "array",
                    "description": "Keywords for database lookup (e.g., ['authentication', 'login', 'user'])"
                }
            }
        }
    ]


# ===== Stage 2: Prompt Refinement Tools =====

def refine_prompt(refined_prompt, clarifications=None):
    """
    Refine and clarify the original user prompt.

    Args:
        refined_prompt: Clearer, more specific version of the user's request
        clarifications: List of assumptions or clarifications made

    Returns:
        Refinement dict
    """
    return {
        "refined_prompt": refined_prompt,
        "clarifications": clarifications or []
    }


REFINEMENT_TOOLS = {
    "refine_prompt": refine_prompt
}


def load_refinement_tools():
    """Load tool definitions for refinement stage."""
    return [
        {
            "name": "refine_prompt",
            "description": "Refine and clarify the user's request based on discovered files",
            "destructive": False,
            "params": {
                "refined_prompt": {
                    "type": "string",
                    "description": "Clearer, more specific version of the user's request with technical details"
                },
                "clarifications": {
                    "type": "array",
                    "description": "List of assumptions or clarifications you made (e.g., ['Assuming Python 3.x', 'Will modify authentication flow'])"
                }
            }
        }
    ]


# ===== Search Execution =====

def execute_regex_search(file_patterns, content_patterns, keywords):
    """
    Execute searches based on AI-generated patterns.

    Returns:
        List of (file_path, match_score, match_reason) tuples
    """
    import subprocess
    from fnmatch import fnmatch

    results = {}  # file_path -> (score, reasons)

    # Get all git-tracked files
    try:
        result = subprocess.run(['git', 'ls-files'], capture_output=True, text=True, check=True)
        all_files = result.stdout.strip().split('\n')
    except:
        all_files = []

    # Filter code files
    code_files = [f for f in all_files if f.endswith(('.py', '.js', '.ts', '.java', '.go', '.json', '.md'))]

    # Search by filename patterns
    for pattern in file_patterns:
        try:
            regex = re.compile(pattern)
            for fpath in code_files:
                if regex.search(fpath):
                    if fpath not in results:
                        results[fpath] = [0, []]
                    results[fpath][0] += 10  # Filename match is strong signal
                    results[fpath][1].append(f"Filename matches: {pattern}")
        except re.error:
            pass  # Skip invalid regex

    # Search by content patterns
    for pattern in content_patterns:
        try:
            regex = re.compile(pattern)
            for fpath in code_files:
                if not os.path.exists(fpath):
                    continue
                try:
                    with open(fpath, 'r', encoding='utf-8', errors='ignore') as f:
                        content = f.read()
                        matches = regex.findall(content)
                        if matches:
                            if fpath not in results:
                                results[fpath] = [0, []]
                            results[fpath][0] += len(matches)
                            results[fpath][1].append(f"Content matches ({len(matches)}): {pattern}")
                except:
                    pass
        except re.error:
            pass

    # Search by keywords in database
    if keywords:
        db = get_db()
        for keyword in keywords:
            keyword_files = db.search_keywords(keyword, limit=20)
            for fpath in keyword_files:
                if fpath not in results:
                    results[fpath] = [0, []]
                results[fpath][0] += 5  # Keyword match is moderate signal
                results[fpath][1].append(f"Keyword match: {keyword}")

    # Convert to list and sort by score
    result_list = [(fpath, score, reasons) for fpath, (score, reasons) in results.items()]
    result_list.sort(key=lambda x: x[1], reverse=True)

    return result_list


def filter_with_tfidf(files_with_scores, user_prompt, limit=10):
    """
    Filter and rank files using TF-IDF relevance to the user prompt.

    Args:
        files_with_scores: List of (file_path, score, reasons) from regex search
        user_prompt: Original user prompt
        limit: Maximum files to return

    Returns:
        List of (file_path, final_score, reasons) tuples
    """
    # Extract prompt keywords
    prompt_keywords = extract_top_keywords(user_prompt, context='prompt')
    prompt_keywords_set = set(kw.lower() for kw in prompt_keywords)

    # Re-score files based on TF-IDF relevance
    final_results = []

    for fpath, regex_score, reasons in files_with_scores[:limit * 3]:  # Consider more candidates
        try:
            with open(fpath, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()

            # Extract file keywords
            file_keywords = extract_top_keywords(content, n=20, context='file')
            file_keywords_set = set(kw.lower() for kw in file_keywords)

            # Calculate TF-IDF overlap
            overlap = len(prompt_keywords_set & file_keywords_set)
            tfidf_score = overlap * 10

            # Combine scores
            final_score = regex_score + tfidf_score

            if tfidf_score > 0:
                reasons.append(f"TF-IDF relevance: {overlap} keyword matches")

            final_results.append((fpath, final_score, reasons))
        except:
            # If can't read file, use regex score only
            final_results.append((fpath, regex_score, reasons))

    # Sort by final score
    final_results.sort(key=lambda x: x[1], reverse=True)

    return final_results[:limit]


# ===== Two-Stage Context Retrieval =====

def intelligent_get_context_with_progress(user_prompt, llm_provider, config, session_id, limit_files=5):
    """
    Two-stage intelligent context retrieval with user-friendly progress output.
    """
    import sys
    import time
    from database import get_db

    db = get_db()

    # Stage 1: Generate search strategy
    print("  → Stage 1: Generating search strategy...", end='', flush=True)
    db.log_benchmark(session_id, 'stage1_start', time.time())
    context_stage1 = _stage1_search_strategy(user_prompt, llm_provider, config, session_id)
    db.log_benchmark(session_id, 'stage1_end', time.time())

    if not context_stage1['search_strategy']:
        print(" ⚠ fallback to keyword search")
        from context import get_context
        return get_context(user_prompt, limit=3)

    print(f" ✓")
    print(f"     Patterns: {len(context_stage1['search_strategy']['file_patterns'])} file, "
          f"{len(context_stage1['search_strategy']['content_patterns'])} content, "
          f"{len(context_stage1['search_strategy']['keywords'])} keywords")

    # Execute searches
    print("  → Searching files...", end='', flush=True)
    search_results = execute_regex_search(
        context_stage1['search_strategy']['file_patterns'],
        context_stage1['search_strategy']['content_patterns'],
        context_stage1['search_strategy']['keywords']
    )
    print(f" found {len(search_results)} matches")

    # Filter with TF-IDF
    print("  → Ranking by relevance...", end='', flush=True)
    relevant_files = filter_with_tfidf(search_results, user_prompt, limit=limit_files * 2)
    print(f" ✓")

    # Stage 2: Refine prompt
    print("  → Stage 2: Refining prompt...", end='', flush=True)
    db.log_benchmark(session_id, 'stage2_start', time.time())
    context = _stage2_refine_prompt(
        user_prompt,
        relevant_files[:limit_files],
        context_stage1['recent_queries'],
        llm_provider,
        config,
        session_id
    )
    db.log_benchmark(session_id, 'stage2_end', time.time())
    print(" ✓")

    return context


def _stage1_search_strategy(user_prompt, llm_provider, config, session_id):
    """Stage 1: Generate search strategy using AI."""
    from agent import create_search_prompt, parse_plan_json
    import time

    db = get_db()
    recent_queries = db.get_recent_queries(limit=3)

    search_tools = load_search_tools()
    search_prompt = create_search_prompt(user_prompt, recent_queries, search_tools)

    db.log_benchmark(session_id, 'stage1_llm_start', time.time())
    search_response = llm_provider.generate(search_prompt, temperature=config.get("temperature", 0.1))
    db.log_benchmark(session_id, 'stage1_llm_end', time.time())
    search_plan = parse_plan_json(search_response)

    search_strategy = None
    if search_plan:
        for step in search_plan:
            if step.get('tool') == 'generate_search_terms':
                params = step.get('params', {})
                search_strategy = generate_search_terms(**params)
                break

    return {
        "search_strategy": search_strategy,
        "recent_queries": recent_queries
    }


def _stage2_refine_prompt(user_prompt, relevant_files, recent_queries, llm_provider, config, session_id):
    """Stage 2: Refine prompt based on found files."""
    from agent import create_refinement_prompt, parse_plan_json
    import time

    db = get_db()

    # Prepare file context
    files_summary = []
    for fpath, score, reasons in relevant_files:
        try:
            with open(fpath, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
            files_summary.append({
                "path": fpath,
                "content_preview": content[:500],
                "match_reasons": reasons
            })
        except:
            pass

    refinement_tools = load_refinement_tools()
    refinement_prompt = create_refinement_prompt(
        user_prompt, files_summary, recent_queries, refinement_tools
    )

    db.log_benchmark(session_id, 'stage2_llm_start', time.time())
    refinement_response = llm_provider.generate(refinement_prompt, temperature=config.get("temperature", 0.1))
    db.log_benchmark(session_id, 'stage2_llm_end', time.time())
    refinement_plan = parse_plan_json(refinement_response)

    refined_prompt = user_prompt
    clarifications = []

    if refinement_plan:
        for step in refinement_plan:
            if step.get('tool') == 'refine_prompt':
                params = step.get('params', {})
                refined = refine_prompt(**params)
                refined_prompt = refined['refined_prompt']
                clarifications = refined['clarifications']
                break

    # Build final context with full file contents
    files_with_content = []
    for fpath, score, reasons in relevant_files:
        try:
            with open(fpath, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
            files_with_content.append(f"FILE: {fpath} | CONTENTS: {content}")
        except:
            pass

    return {
        "files": files_with_content,
        "recent_queries": recent_queries,
        "refined_prompt": refined_prompt,
        "clarifications": clarifications
    }


def intelligent_get_context(user_prompt, llm_provider, config, limit_files=5):
    """
    Two-stage intelligent context retrieval (silent version).

    Stage 1: AI generates search strategy
    Stage 2: AI refines prompt based on found files

    Returns:
        {
            "files": [...],  # Top relevant files with content
            "recent_queries": [...],
            "refined_prompt": str,  # AI-refined version of user prompt
            "clarifications": [...]  # AI assumptions/clarifications
        }
    """
    # Stage 1
    context_stage1 = _stage1_search_strategy(user_prompt, llm_provider, config)

    if not context_stage1['search_strategy']:
        from context import get_context
        return get_context(user_prompt, limit=3)

    # Execute searches
    search_results = execute_regex_search(
        context_stage1['search_strategy']['file_patterns'],
        context_stage1['search_strategy']['content_patterns'],
        context_stage1['search_strategy']['keywords']
    )

    # Filter with TF-IDF
    relevant_files = filter_with_tfidf(search_results, user_prompt, limit=limit_files * 2)

    # Stage 2
    context = _stage2_refine_prompt(
        user_prompt,
        relevant_files[:limit_files],
        context_stage1['recent_queries'],
        llm_provider,
        config
    )

    return context

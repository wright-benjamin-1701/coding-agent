from database import get_db
from vectorize import extract_top_keywords

def get_context(prompt, limit=3):
    """Get context for a prompt by finding relevant files and recent queries."""
    db = get_db()

    # Use TF-IDF to extract the most important keywords from the prompt
    words = extract_top_keywords(prompt, context='prompt')

    # Get files matching keywords
    file_paths = db.get_files_for_keywords(words, limit_per_keyword=5)

    # Read file contents
    files = set()
    for file_path in file_paths:
        try:
            with open(file_path, 'r') as f:
                contents = f.read()
                files.add(f"FILE: {file_path} | CONTENTS: {contents}")
        except:
            pass  # Skip files that can't be read

    # Get recent queries
    recent = db.get_recent_queries(limit)

    context = {"files": list(files)[:5], "recent_queries": recent}
    return context

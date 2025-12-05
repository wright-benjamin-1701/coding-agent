import os, re, time
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

from vectorize import extract_top_keywords, maybe_rebuild_tfidf
from database import get_db, set_db as set_database

_last_index_time = {}  # Track last index time per file for debouncing
_debounce_seconds = 30  # Don't reindex same file within this interval
_max_keywords = 10  # Max keywords to extract per file

def set_db(db_name):
    """Set the database name to use."""
    set_database(db_name)

def set_debounce(seconds):
    """Set the debounce interval in seconds."""
    global _debounce_seconds
    _debounce_seconds = seconds

def set_max_keywords(n):
    """Set the maximum number of keywords to extract per file."""
    global _max_keywords
    _max_keywords = n

# Backward compatibility - these are now just wrappers
def get_db_connection():
    """Get a database connection (deprecated - use get_db() instead)."""
    return get_db().get_connection()

class db_context:
    """Context manager for database connections (deprecated - use get_db().context() instead)."""
    def __enter__(self):
        self.conn = get_db().get_connection()
        return self.conn

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is None:
            self.conn.commit()
        self.conn.close()
        return False

def init_db():
    """Initialize database schema."""
    get_db().init_schema()

def index_file(path):
    import os  # Need os for path operations throughout this function
    if not path.endswith(('.py', '.js', '.ts', '.java', '.go')): return

    db = get_db()

    # Check if file is already up-to-date in the database
    try:
        mtime = os.path.getmtime(path)
        file_data = db.get_file(path)
        if file_data and abs(file_data['mtime'] - mtime) < 0.1:  # File hasn't changed
            # Still update debounce time to prevent re-checking
            now = time.time()
            if path in _last_index_time and (now - _last_index_time[path]) < _debounce_seconds:
                return
            _last_index_time[path] = now
            return
    except:
        pass

    # Debounce: skip if this file was indexed very recently
    now = time.time()
    if path in _last_index_time and (now - _last_index_time[path]) < _debounce_seconds:
        return
    _last_index_time[path] = now

    try:
        content = open(path).read()
        # Re-get mtime after reading file (in case it was only retrieved in the check above)
        mtime = os.path.getmtime(path)
    except:
        return

    # Save file and clear old data
    db.save_file(path, content, mtime)
    db.delete_classes_for_file(path)
    db.delete_keywords_for_file(path)

    # Extract classes
    for match in re.finditer(r'class\s+(\w+)', content):
        db.save_class(match.group(1), path, content[:match.start()].count('\n') + 1)

    # Extract top keywords using TF-IDF (uses _max_keywords or smart default for 'file' context)
    keywords = extract_top_keywords(content, n=_max_keywords if _max_keywords != 10 else None, context='file')

    # Also add the filename (without extension) as a keyword for easy file matching
    filename = os.path.basename(path).rsplit('.', 1)[0]
    db.save_keywords(path, keywords + [filename])

def search(query):
    """Search for files by keyword."""
    return get_db().search_keywords(query, limit=10)

def save_query(query, response):
    """Save a query and its response to the database."""
    get_db().save_query(query, response)

class Handler(FileSystemEventHandler):
    def on_modified(self, event):
        if not event.is_directory:
            path = event.src_path
            # Ignore database files, hidden files, temp files, and model files
            if any(pattern in path for pattern in ['.db', '.db-', '__pycache__', '.git/', '.pkl', '.pyc']):
                return
            # Only index supported code files
            if path.endswith(('.py', '.js', '.ts', '.java', '.go')):
                index_file(path)
                maybe_rebuild_tfidf()

def watch(path="."):
    observer = Observer(); observer.schedule(Handler(), path, recursive=True); observer.start()
    return observer

# Change tracking functions
def create_session(session_id, query_summary=""):
    """Create a new session for tracking changes."""
    get_db().create_session(session_id, query_summary)

def save_change(session_id, file_path, content_before, content_after, tool_name, tool_args, user_query):
    """Save a change to the database."""
    get_db().save_change(session_id, file_path, content_before, content_after,
                        tool_name, tool_args, user_query)

def get_change_history(limit=10, session_id=None):
    """Get recent changes, optionally filtered by session."""
    return get_db().get_change_history(limit, session_id)

def undo_change(change_id=None):
    """Undo a specific change or the most recent change."""
    return get_db().undo_change(change_id)

def redo_change(change_id=None):
    """Redo a previously undone change."""
    return get_db().redo_change(change_id)

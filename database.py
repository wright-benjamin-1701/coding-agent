"""
Database operations for the coding agent.
Consolidates all database interactions into a single class.
"""
import sqlite3
import time
import json
import os


class Database:
    """Encapsulates all database operations."""

    def __init__(self, db_name="index.db"):
        """Initialize the database connection.

        Parameters:
        db_name (str): Name of the SQLite database file to use.

        Initializes:
        - Creates a connection to the SQLite database
        - Sets journal mode to WAL for better concurrency
        - Sets synchronous mode to NORMAL for performance
        """
        self.db_name = db_name
    def get_connection(self):
        """Get a database connection with optimal settings.

        Returns:
        sqlite3.Connection: A connection to the SQLite database with WAL journal mode and NORMAL synchronous mode set.
        """
        conn = sqlite3.connect(self.db_name, timeout=10)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        return conn
    def context(self):
        """Get a context manager for database operations.

        Returns:
        _DatabaseContext: A context manager that handles database connections.
        """
        return _DatabaseContext(self)
    def init_schema(self):
        """Initialize all database tables.

        Creates tables for files, classes, keywords, queries, sessions, change history, and benchmarks.
        """
        with self.context() as conn:
            # Core tables
            conn.execute("CREATE TABLE IF NOT EXISTS files (path TEXT PRIMARY KEY, content TEXT, mtime REAL)")
            conn.execute("CREATE TABLE IF NOT EXISTS classes (name TEXT, file TEXT, line INTEGER)")
            conn.execute("CREATE TABLE IF NOT EXISTS keywords (word TEXT, file TEXT, count INTEGER)")
            conn.execute("CREATE TABLE IF NOT EXISTS queries (query TEXT, response TEXT, timestamp REAL)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_keywords_word ON keywords(word)")

            # Change tracking tables
            conn.execute("""CREATE TABLE IF NOT EXISTS sessions (
                id TEXT PRIMARY KEY,
                started REAL,
                query_summary TEXT
            )""")
            conn.execute("""CREATE TABLE IF NOT EXISTS change_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp REAL,
                session_id TEXT,
                file_path TEXT,
                content_before TEXT,
                content_after TEXT,
                tool_name TEXT,
                tool_args TEXT,
                user_query TEXT,
                undone INTEGER DEFAULT 0,
                FOREIGN KEY (session_id) REFERENCES sessions(id)
            )""")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_change_history_session ON change_history(session_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_change_history_file ON change_history(file_path)")

            # Benchmarking table
            conn.execute("""CREATE TABLE IF NOT EXISTS benchmarks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT,
                event_name TEXT,
                timestamp REAL,
                FOREIGN KEY (session_id) REFERENCES sessions(id)
            )""")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_benchmarks_session ON benchmarks(session_id)")
    # ===== File Operations =====

    def get_file(self, path):
        """Get file content and mtime from database.

        Parameters:
        path (str): The file path to retrieve.

        Returns:
        dict: A dictionary with keys 'content' and 'mtime' if the file exists, otherwise None.
        """
        with self.context() as conn:
            result = conn.execute("SELECT content, mtime FROM files WHERE path=?", (path,)).fetchone()
            if result:
                return {"content": result[0], "mtime": result[1]}
            return None
    def save_file(self, path, content, mtime):
        """Save or update file in database.

        Parameters:
        path (str): The file path.
        content (str): The file content.
        mtime (float): The modification time of the file.
        """
        with self.context() as conn:
            conn.execute("INSERT OR REPLACE INTO files VALUES (?,?,?)", (path, content, mtime))
    def delete_file_data(self, path):
        """Delete all data associated with a file.

        Parameters:
        path (str): The file path to delete data for.
        """
        with self.context() as conn:
            conn.execute("DELETE FROM files WHERE path=?", (path,))
            conn.execute("DELETE FROM classes WHERE file=?", (path,))
            conn.execute("DELETE FROM keywords WHERE file=?", (path,))
    # ===== Class Operations =====

    def save_class(self, name, file, line):
        """Save a class definition.

        Parameters:
        name (str): The class name.
        file (str): The file path where the class is defined.
        line (int): The line number of the class definition.
        """
        with self.context() as conn:
            conn.execute("INSERT INTO classes VALUES (?,?,?)", (name, file, line))
    def delete_classes_for_file(self, file):
        """Delete all classes for a specific file.

        Parameters:
        file (str): The file path to delete classes for.
        """
        with self.context() as conn:
            conn.execute("DELETE FROM classes WHERE file=?", (file,))
    # ===== Keyword Operations =====

    def save_keywords(self, file, keywords):
        """Save keywords for a file.

        Parameters:
        file (str): The file path.
        keywords (list): A list of keywords to save.
        """
        with self.context() as conn:
            for word in keywords:
                conn.execute("INSERT INTO keywords VALUES (?,?,1)", (word.lower(), file))
    def delete_keywords_for_file(self, file):
        """Delete all keywords for a specific file.

        Parameters:
        file (str): The file path to delete keywords for.
        """
        with self.context() as conn:
            conn.execute("DELETE FROM keywords WHERE file=?", (file,))
    def search_keywords(self, query, limit=10):
        """Search for files by keyword.

        Parameters:
        query (str): The keyword to search for.
        limit (int): Maximum number of results to return.

        Returns:
        list: A list of file paths matching the keyword.
        """
        with self.context() as conn:
            results = [
                row[0] for row in conn.execute(
                    "SELECT DISTINCT file FROM keywords WHERE word LIKE ? LIMIT ?",
                    (f"%{query}%", limit)
                ).fetchall()
            ]
            return results
    def get_files_for_keywords(self, keywords, limit_per_keyword=5):
        """Get files matching any of the given keywords.

        Parameters:
        keywords (list): A list of keywords to search for.
        limit_per_keyword (int): Maximum number of results per keyword.

        Returns:
        list: A list of unique file paths matching any of the keywords.
        """
        files = set()
        with self.context() as conn:
            for word in keywords:
                for row in conn.execute(
                    "SELECT DISTINCT file FROM keywords WHERE word LIKE ? LIMIT ?",
                    (f"%{word}%", limit_per_keyword)
                ):
                    files.add(row[0])
        return list(files)
    # ===== Query History Operations =====

    def save_query(self, query, response):
        """Save a query and its response.

        Parameters:
        query (str): The query text.
        response (str): The response text.
        """
        with self.context() as conn:
            conn.execute("INSERT INTO queries VALUES (?,?,?)", (query, response, time.time()))
    def get_recent_queries(self, limit=3):
        """Get recent queries and responses.

        Parameters:
        limit (int): Maximum number of recent queries to return.

        Returns:
        list: A list of dictionaries with 'query' and 'response' keys.
        """
        with self.context() as conn:
            rows = conn.execute(
                "SELECT query, response FROM queries ORDER BY timestamp DESC LIMIT ?",
                (limit,)
            ).fetchall()
            return [{"query": row[0], "response": row[1]} for row in rows]
    # ===== Session Operations =====

    def create_session(self, session_id, query_summary=""):
        """Create a new session for tracking changes.

        Parameters:
        session_id (str): The session ID.
        query_summary (str): A summary of the query that initiated the session.
        """
        with self.context() as conn:
            conn.execute("INSERT OR IGNORE INTO sessions VALUES (?,?,?)",
                        (session_id, time.time(), query_summary))
    # ===== Change History Operations =====

    def save_change(self, session_id, file_path, content_before, content_after,
                   tool_name, tool_args, user_query):
        """Save a change to the database.

        Parameters:
        session_id (str): The session ID.
        file_path (str): The file path that was changed.
        content_before (str): The content of the file before the change.
        content_after (str): The content of the file after the change.
        tool_name (str): The name of the tool that made the change.
        tool_args (dict): The arguments passed to the tool.
        user_query (str): The user query that initiated the change.
        """
        with self.context() as conn:
            conn.execute("""INSERT INTO change_history
                            (timestamp, session_id, file_path, content_before, content_after,
                             tool_name, tool_args, user_query)
                            VALUES (?,?,?,?,?,?,?,?)""",
                        (time.time(), session_id, file_path, content_before, content_after,
                         tool_name, json.dumps(tool_args), user_query))
    def get_change_history(self, limit=10, session_id=None):
        """Get recent changes, optionally filtered by session.

        Parameters:
        limit (int): Maximum number of changes to return.
        session_id (str): Optional session ID to filter changes by.

        Returns:
        list: A list of change history entries.
        """
        with self.context() as conn:
            if session_id:
                rows = conn.execute("""SELECT id, timestamp, file_path, tool_name, undone
                                      FROM change_history
                                      WHERE session_id=? AND undone=0
                                      ORDER BY id DESC LIMIT ?""",
                                   (session_id, limit)).fetchall()
            else:
                rows = conn.execute("""SELECT id, timestamp, file_path, tool_name, undone
                                      FROM change_history
                                      WHERE undone=0
                                      ORDER BY id DESC LIMIT ?""",
                                   (limit,)).fetchall()
            return [{"id": r[0], "timestamp": r[1], "file_path": r[2], "tool_name": r[3]} for r in rows]
    def undo_change(self, change_id=None):
        """Undo a specific change or the most recent change.

        Parameters:
        change_id (int): Optional ID of the change to undo.

        Returns:
        dict: A dictionary with status, file, and change_id if successful, or an error message.
        """
        with self.context() as conn:
            if change_id is None:
                row = conn.execute("""SELECT id, file_path, content_before
                                     FROM change_history
                                     WHERE undone=0
                                     ORDER BY id DESC LIMIT 1""").fetchone()
            else:
                row = conn.execute("""SELECT id, file_path, content_before
                                     FROM change_history
                                     WHERE id=? AND undone=0""", (change_id,)).fetchone()

            if not row:
                return {"error": "no change to undo"}

            change_id, file_path, content_before = row

            # Restore the file
            try:
                if content_before is None:
                    if os.path.exists(file_path):
                        os.remove(file_path)
                else:
                    os.makedirs(os.path.dirname(file_path) or ".", exist_ok=True)
                    with open(file_path, "w") as f:
                        f.write(content_before)

                # Mark as undone
                conn.execute("UPDATE change_history SET undone=1 WHERE id=?", (change_id,))
                return {"status": "undone", "file": file_path, "change_id": change_id}
            except Exception as e:
                return {"error": str(e)}
    def redo_change(self, change_id=None):
        """Redo a previously undone change.

        Parameters:
        change_id (int): Optional ID of the change to redo.

        Returns:
        dict: A dictionary with status, file, and change_id if successful, or an error message.
        """
        with self.context() as conn:
            if change_id is None:
                row = conn.execute("""SELECT id, file_path, content_after
                                     FROM change_history
                                     WHERE undone=1
                                     ORDER BY id ASC LIMIT 1""").fetchone()
            else:
                row = conn.execute("""SELECT id, file_path, content_after
                                     FROM change_history
                                     WHERE id=? AND undone=1""", (change_id,)).fetchone()

            if not row:
                return {"error": "no change to redo"}

            change_id, file_path, content_after = row

            # Restore the file
            try:
                if content_after is None:
                    return {"error": "cannot redo: no content_after"}

                os.makedirs(os.path.dirname(file_path) or ".", exist_ok=True)
                with open(file_path, "w") as f:
                    f.write(content_after)

                # Mark as not undone
                conn.execute("UPDATE change_history SET undone=0 WHERE id=?", (change_id,))
                return {"status": "redone", "file": file_path, "change_id": change_id}
            except Exception as e:
                return {"error": str(e)}
    # ===== Benchmarking Operations =====

    def log_benchmark(self, session_id, event_name, timestamp):
        """Log a benchmark event for a session.

        Parameters:
        session_id (str): The session ID.
        event_name (str): The name of the benchmark event.
        timestamp (float): The timestamp of the event.
        """
        with self.context() as conn:
            conn.execute("""INSERT INTO benchmarks (session_id, event_name, timestamp)
                           VALUES (?, ?, ?)""", (session_id, event_name, timestamp))
    def get_benchmarks(self, session_id):
        """Get all benchmark events for a session, ordered by timestamp.

        Parameters:
        session_id (str): The session ID.

        Returns:
        list: A list of benchmark events with 'event' and 'timestamp' keys.
        """
        with self.context() as conn:
            rows = conn.execute("""SELECT event_name, timestamp
                                  FROM benchmarks
                                  WHERE session_id = ?
                                  ORDER BY timestamp""", (session_id,)).fetchall()
            return [{"event": row[0], "timestamp": row[1]} for row in rows]
class _DatabaseContext:
    """Context manager for database connections."""

    def __init__(self, database):
        self.database = database
        self.conn = None

    def __enter__(self):
        self.conn = self.database.get_connection()
        return self.conn

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is None:
            self.conn.commit()
        self.conn.close()
        return False


# Global database instance
_db_instance = None


def get_db():
    """Get the global database instance."""
    global _db_instance
    if _db_instance is None:
        _db_instance = Database()
    return _db_instance


def set_db(db_name):
    """Set the database name and reset the global instance."""
    global _db_instance
    _db_instance = Database(db_name)
    return _db_instance

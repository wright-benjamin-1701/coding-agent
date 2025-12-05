"""RAG database for storing context and summaries."""

import sqlite3
import json
from datetime import datetime
from typing import List, Dict, Any, Optional
from pathlib import Path


class RAGDatabase:
    """Database for storing RAG context, summaries, and execution history."""
    
    def __init__(self, db_path: str = ".coding_agent.db"):
        self.db_path = db_path
        self._init_database()
    
    def _init_database(self):
        """Initialize database schema."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS sessions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    user_prompt TEXT NOT NULL,
                    commit_hash TEXT NOT NULL,
                    modified_files TEXT NOT NULL,  -- JSON array
                    summary TEXT NOT NULL,
                    execution_log TEXT  -- JSON of execution results
                )
            """)
            
            conn.execute("""
                CREATE TABLE IF NOT EXISTS file_cache (
                    file_path TEXT PRIMARY KEY,
                    commit_hash TEXT NOT NULL,
                    content_hash TEXT NOT NULL,
                    content TEXT NOT NULL,
                    summary TEXT,
                    last_updated TEXT NOT NULL
                )
            """)
            
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_sessions_timestamp 
                ON sessions(timestamp)
            """)
            
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_file_cache_commit 
                ON file_cache(commit_hash)
            """)
            
            # Add model interactions table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS model_interactions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id INTEGER,
                    timestamp TEXT NOT NULL,
                    step_number INTEGER NOT NULL,
                    prompt TEXT NOT NULL,
                    response TEXT NOT NULL,
                    metadata TEXT,  -- JSON metadata
                    FOREIGN KEY (session_id) REFERENCES sessions(id)
                )
            """)
            
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_model_interactions_session 
                ON model_interactions(session_id)
            """)
    
    def store_session(self, user_prompt: str, commit_hash: str, 
                     modified_files: List[str], summary: str,
                     execution_log: Optional[Dict[str, Any]] = None):
        """Store a session record and return the session ID."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("""
                INSERT INTO sessions 
                (timestamp, user_prompt, commit_hash, modified_files, summary, execution_log)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                datetime.now().isoformat(),
                user_prompt,
                commit_hash,
                json.dumps(modified_files),
                summary,
                json.dumps(execution_log) if execution_log else None
            ))
            return cursor.lastrowid
    
    def store_model_interaction(self, session_id: int, step_number: int, 
                               prompt: str, response: str, 
                               metadata: Optional[Dict[str, Any]] = None):
        """Store a model interaction."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT INTO model_interactions
                (session_id, timestamp, step_number, prompt, response, metadata)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                session_id,
                datetime.now().isoformat(),
                step_number,
                prompt,
                response,
                json.dumps(metadata) if metadata else None
            ))
    
    def get_recent_summaries(self, limit: int = 5, current_prompt: str = None, 
                           use_relevance_filter: bool = True) -> List[str]:
        """Get recent session summaries, optionally filtered by relevance."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("""
                SELECT summary FROM sessions 
                ORDER BY timestamp DESC 
                LIMIT ?
            """, (limit * 2,))  # Get more to allow for filtering
            
            summaries = [row[0] for row in cursor.fetchall()]
            
            # Apply relevance filtering if requested and prompt provided
            if use_relevance_filter and current_prompt and summaries:
                from ..relevance_filter import RelevanceFilter
                
                filter_instance = RelevanceFilter(min_similarity_threshold=0.15)
                relevant_summaries = filter_instance.filter_relevant_summaries(
                    current_prompt, summaries, max_summaries=limit
                )
                
                # Return only the summaries (without scores)
                return [summary for summary, score in relevant_summaries]
            
            return summaries[:limit]
    
    def search_similar_prompts(self, query: str, limit: int = 3) -> List[Dict[str, Any]]:
        """Search for similar prompts using simple text matching."""
        # Simple implementation - could be enhanced with embedding similarity
        query_words = set(query.lower().split())
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("""
                SELECT user_prompt, summary, timestamp
                FROM sessions 
                ORDER BY timestamp DESC
            """)
            
            results = []
            for row in cursor.fetchall():
                prompt_words = set(row[0].lower().split())
                overlap = len(query_words.intersection(prompt_words))
                
                if overlap > 0:
                    results.append({
                        "prompt": row[0],
                        "summary": row[1],
                        "timestamp": row[2],
                        "similarity": overlap / len(query_words.union(prompt_words))
                    })
            
            # Sort by similarity and return top results
            results.sort(key=lambda x: x["similarity"], reverse=True)
            return results[:limit]
    
    def cache_file_content(self, file_path: str, commit_hash: str, 
                          content: str, summary: Optional[str] = None):
        """Cache file content and summary."""
        content_hash = str(hash(content))
        
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT OR REPLACE INTO file_cache
                (file_path, commit_hash, content_hash, content, summary, last_updated)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                file_path,
                commit_hash,
                content_hash,
                content,
                summary,
                datetime.now().isoformat()
            ))
    
    def get_cached_file(self, file_path: str, commit_hash: str) -> Optional[Dict[str, str]]:
        """Get cached file content if available."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("""
                SELECT content, summary FROM file_cache
                WHERE file_path = ? AND commit_hash = ?
            """, (file_path, commit_hash))
            
            row = cursor.fetchone()
            if row:
                return {"content": row[0], "summary": row[1]}
            return None
    
    def cleanup_old_cache(self, keep_commits: List[str]):
        """Clean up cached files not in the keep list."""
        with sqlite3.connect(self.db_path) as conn:
            placeholders = ",".join("?" * len(keep_commits))
            conn.execute(f"""
                DELETE FROM file_cache 
                WHERE commit_hash NOT IN ({placeholders})
            """, keep_commits)
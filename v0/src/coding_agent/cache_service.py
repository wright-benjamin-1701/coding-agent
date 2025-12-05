"""File cache service for commit-based caching."""

import hashlib
import subprocess
from pathlib import Path
from typing import Optional, Dict, Any
from .database.rag_db import RAGDatabase


class CacheService:
    """Service for caching file reads based on git commits."""
    
    def __init__(self, rag_db: RAGDatabase):
        self.rag_db = rag_db
    
    def get_current_commit(self) -> str:
        """Get current git commit hash."""
        try:
            result = subprocess.run(['git', 'rev-parse', 'HEAD'], 
                                  capture_output=True, text=True, check=True)
            return result.stdout.strip()
        except (subprocess.CalledProcessError, FileNotFoundError):
            return "no-git"
    
    def get_file_content_hash(self, file_path: str) -> str:
        """Get hash of file content."""
        try:
            with open(file_path, 'rb') as f:
                return hashlib.md5(f.read()).hexdigest()
        except (OSError, IOError):
            return ""
    
    def read_file_cached(self, file_path: str) -> Optional[Dict[str, str]]:
        """Read file with commit-based caching."""
        current_commit = self.get_current_commit()
        
        # Try to get from cache first
        cached = self.rag_db.get_cached_file(file_path, current_commit)
        if cached:
            return cached
        
        # File not in cache, read and cache it
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Cache the content (summary will be added later if needed)
            self.rag_db.cache_file_content(file_path, current_commit, content)
            
            return {"content": content, "summary": None}
            
        except (OSError, IOError, UnicodeDecodeError) as e:
            return None
    
    def cache_file_summary(self, file_path: str, summary: str):
        """Cache a summary for a file at the current commit."""
        current_commit = self.get_current_commit()
        
        # Get existing cached content
        cached = self.rag_db.get_cached_file(file_path, current_commit)
        if cached:
            # Update with summary
            self.rag_db.cache_file_content(
                file_path, current_commit, cached["content"], summary
            )
        else:
            # Read and cache with summary
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                self.rag_db.cache_file_content(file_path, current_commit, content, summary)
            except (OSError, IOError, UnicodeDecodeError):
                pass
    
    def cleanup_old_cache(self, keep_last_n_commits: int = 10):
        """Clean up cache entries for old commits."""
        try:
            # Get recent commits
            result = subprocess.run(
                ['git', 'log', f'-{keep_last_n_commits}', '--format=%H'], 
                capture_output=True, text=True, check=True
            )
            recent_commits = result.stdout.strip().split('\n')
            recent_commits.append("no-git")  # Keep non-git entries
            
            self.rag_db.cleanup_old_cache(recent_commits)
            
        except (subprocess.CalledProcessError, FileNotFoundError):
            # If git is not available, keep everything
            pass
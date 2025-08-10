"""File indexing system with change watching."""

import os
import json
import hashlib
from pathlib import Path
from typing import Dict, Set, List, Optional
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler


class IndexEntry:
    """Represents a file index entry."""
    
    def __init__(self, path: str, content_hash: str, symbols: List[str] = None):
        self.path = path
        self.content_hash = content_hash
        self.symbols = symbols or []
        try:
            self.last_updated = os.path.getmtime(path)
        except (OSError, TypeError):
            # Handle case where path doesn't exist or is invalid
            self.last_updated = 0


class FileIndexer:
    """Indexes codebase files for fast searching."""
    
    def __init__(self, root_path: str = ".", index_file: str = ".coding_agent_index.json"):
        self.root_path = Path(root_path).resolve()
        self.index_file = self.root_path / index_file
        self.index: Dict[str, IndexEntry] = {}
        self.ignore_patterns = {'.git', '__pycache__', 'node_modules', '.env'}
        
        self._load_index()
    
    def _load_index(self):
        """Load existing index from disk."""
        if self.index_file.exists():
            try:
                with open(self.index_file, 'r') as f:
                    data = json.load(f)
                    for path, entry_data in data.items():
                        self.index[path] = IndexEntry(
                            path=entry_data['path'],
                            content_hash=entry_data['content_hash'],
                            symbols=entry_data.get('symbols', [])
                        )
            except Exception as e:
                print(f"Warning: Could not load index: {e}")
    
    def _save_index(self):
        """Save index to disk."""
        data = {}
        for path, entry in self.index.items():
            data[path] = {
                'path': entry.path,
                'content_hash': entry.content_hash,
                'symbols': entry.symbols,
                'last_updated': entry.last_updated
            }
        
        with open(self.index_file, 'w') as f:
            json.dump(data, f, indent=2)
    
    def _should_ignore(self, path: Path) -> bool:
        """Check if path should be ignored."""
        parts = path.parts
        return any(pattern in parts for pattern in self.ignore_patterns)
    
    def _get_file_hash(self, file_path: Path) -> str:
        """Get content hash of a file."""
        try:
            with open(file_path, 'rb') as f:
                return hashlib.md5(f.read()).hexdigest()
        except:
            return ""
    
    def _extract_symbols(self, file_path: Path) -> List[str]:
        """Extract symbols (functions, classes) from a file."""
        symbols = []
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
                
                # Simple regex-based symbol extraction
                import re
                
                # Python functions and classes
                if file_path.suffix == '.py':
                    symbols.extend(re.findall(r'^(?:def|class)\s+(\w+)', content, re.MULTILINE))
                
                # JavaScript/TypeScript functions
                elif file_path.suffix in {'.js', '.ts', '.jsx', '.tsx'}:
                    symbols.extend(re.findall(r'(?:function\s+(\w+)|(\w+)\s*=\s*function|(\w+)\s*=\s*\([^)]*\)\s*=>)', content))
                    symbols = [s for sublist in symbols for s in sublist if s]
                
                # Go functions
                elif file_path.suffix == '.go':
                    symbols.extend(re.findall(r'^func\s+(\w+)', content, re.MULTILINE))
                
        except Exception:
            pass
        
        return symbols
    
    def index_file_path(self, file_path: Path) -> bool:
        """Index a single file. Returns True if file was updated."""
        if self._should_ignore(file_path) or not file_path.is_file():
            return False
        
        relative_path = str(file_path.relative_to(self.root_path))
        current_hash = self._get_file_hash(file_path)
        
        # Check if file needs updating
        if relative_path in self.index:
            if self.index[relative_path].content_hash == current_hash:
                return False  # No changes
        
        # Extract symbols and create index entry
        symbols = self._extract_symbols(file_path)
        self.index[relative_path] = IndexEntry(
            path=relative_path,
            content_hash=current_hash,
            symbols=symbols
        )
        
        return True
    
    def build_full_index(self):
        """Build complete index of the codebase."""
        updated_files = []
        
        for file_path in self.root_path.rglob('*'):
            if file_path.is_file() and self.index_file_path(file_path):
                updated_files.append(str(file_path.relative_to(self.root_path)))
        
        self._save_index()
        
        # Run anti-pattern analysis after indexing
        self._run_anti_pattern_analysis()
        
        return updated_files
    
    def update_file(self, file_path: str):
        """Update index for a specific file."""
        path = self.root_path / file_path
        if self.index_file_path(path):
            self._save_index()
    
    def remove_file(self, file_path: str):
        """Remove file from index."""
        relative_path = str(Path(file_path).relative_to(self.root_path))
        if relative_path in self.index:
            del self.index[relative_path]
            self._save_index()
    
    def search_symbols(self, query: str) -> List[str]:
        """Search for symbols matching query."""
        results = []
        query_lower = query.lower()
        
        for path, entry in self.index.items():
            for symbol in entry.symbols:
                if query_lower in symbol.lower():
                    results.append(f"{path}:{symbol}")
        
        return results
    
    def get_files_by_extension(self, extension: str) -> List[str]:
        """Get all files with given extension."""
        return [path for path in self.index.keys() if path.endswith(extension)]
    
    def _run_anti_pattern_analysis(self):
        """Run anti-pattern analysis on indexed files."""
        try:
            # Import here to avoid circular imports
            from ..tools.anti_pattern_parser import AntiPatternParser
            
            parser = AntiPatternParser()
            issues = parser._scan_path(str(self.root_path))
            
            if issues:
                print("\n🚨 Anti-pattern issues detected:")
                for issue in issues:
                    print(f"  📋 Rule: {issue['rule']}")
                    if issue['description']:
                        print(f"     Description: {issue['description']}")
                    print(f"     File: {issue['file']}")
                    for pattern_info in issue['patterns_found']:
                        lines_str = ", ".join(map(str, pattern_info['lines']))
                        print(f"     Pattern '{pattern_info['pattern']}' found at lines: {lines_str}")
                    print()
            else:
                print("✅ No anti-pattern issues detected")
        except Exception as e:
            print(f"Warning: Anti-pattern analysis failed: {e}")


class FileWatcher(FileSystemEventHandler):
    """Watches file system changes and updates index."""
    
    def __init__(self, indexer: FileIndexer):
        self.indexer = indexer
    
    def on_modified(self, event):
        if not event.is_directory:
            self.indexer.update_file(event.src_path)
    
    def on_created(self, event):
        if not event.is_directory:
            self.indexer.update_file(event.src_path)
    
    def on_deleted(self, event):
        if not event.is_directory:
            self.indexer.remove_file(event.src_path)
    
    def on_moved(self, event):
        if not event.is_directory:
            self.indexer.remove_file(event.src_path)
            self.indexer.update_file(event.dest_path)
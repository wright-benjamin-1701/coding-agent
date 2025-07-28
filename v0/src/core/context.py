"""
Context management for project understanding and awareness
"""
import os
import ast
import json
from pathlib import Path
from typing import Dict, List, Optional, Any, Set
from dataclasses import dataclass, asdict


@dataclass
class FileInfo:
    """Information about a project file"""
    path: str
    size: int
    language: str
    functions: List[str]
    classes: List[str]
    imports: List[str]
    last_modified: float


@dataclass
class ProjectContext:
    """Project-wide context information"""
    root_path: str
    files: Dict[str, FileInfo]
    languages: Set[str]
    dependencies: Dict[str, List[str]]
    structure: Dict[str, Any]
    git_info: Optional[Dict[str, Any]] = None


class ContextManager:
    """Manages project context and understanding"""
    
    def __init__(self, project_path: str):
        self.project_path = Path(project_path).resolve()
        self.context = ProjectContext(
            root_path=str(self.project_path),
            files={},
            languages=set(),
            dependencies={},
            structure={}
        )
        self._ignore_patterns = {
            "__pycache__", ".git", ".vscode", ".idea", "node_modules",
            ".pytest_cache", ".mypy_cache", "*.pyc", "*.pyo", "*.egg-info"
        }
    
    async def build_context(self) -> ProjectContext:
        """Build comprehensive project context"""
        
        # Analyze file structure
        await self._analyze_structure()
        
        # Index files and extract metadata
        await self._index_files()
        
        # Analyze dependencies
        await self._analyze_dependencies()
        
        # Get git information if available
        await self._analyze_git_info()
        
        return self.context
    
    async def _analyze_structure(self) -> None:
        """Analyze project directory structure"""
        structure = {}
        
        for root, dirs, files in os.walk(self.project_path):
            # Filter out ignored directories
            dirs[:] = [d for d in dirs if not self._should_ignore(d)]
            
            rel_root = os.path.relpath(root, self.project_path)
            if rel_root == ".":
                rel_root = ""
            
            structure[rel_root] = {
                "directories": dirs,
                "files": [f for f in files if not self._should_ignore(f)]
            }
        
        self.context.structure = structure
    
    async def _index_files(self) -> None:
        """Index all project files and extract metadata"""
        
        for root, dirs, files in os.walk(self.project_path):
            # Filter ignored directories
            dirs[:] = [d for d in dirs if not self._should_ignore(d)]
            
            for file in files:
                if self._should_ignore(file):
                    continue
                
                file_path = Path(root) / file
                rel_path = file_path.relative_to(self.project_path)
                
                try:
                    file_info = await self._analyze_file(file_path)
                    self.context.files[str(rel_path)] = file_info
                    self.context.languages.add(file_info.language)
                except Exception:
                    # Skip files that can't be analyzed
                    continue
    
    async def _analyze_file(self, file_path: Path) -> FileInfo:
        """Analyze individual file and extract metadata"""
        
        stat = file_path.stat()
        language = self._detect_language(file_path)
        
        functions = []
        classes = []
        imports = []
        
        # Extract code structure for supported languages
        if language == "python" and file_path.suffix == ".py":
            try:
                functions, classes, imports = await self._analyze_python_file(file_path)
            except Exception:
                pass
        elif language == "javascript" and file_path.suffix in [".js", ".ts"]:
            try:
                functions, classes, imports = await self._analyze_javascript_file(file_path)
            except Exception:
                pass
        
        return FileInfo(
            path=str(file_path.relative_to(self.project_path)),
            size=stat.st_size,
            language=language,
            functions=functions,
            classes=classes,
            imports=imports,
            last_modified=stat.st_mtime
        )
    
    async def _analyze_python_file(self, file_path: Path) -> tuple[List[str], List[str], List[str]]:
        """Analyze Python file using AST"""
        
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        try:
            tree = ast.parse(content)
        except SyntaxError:
            return [], [], []
        
        functions = []
        classes = []
        imports = []
        
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                functions.append(node.name)
            elif isinstance(node, ast.ClassDef):
                classes.append(node.name)
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    imports.append(alias.name)
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    imports.append(node.module)
        
        return functions, classes, imports
    
    async def _analyze_javascript_file(self, file_path: Path) -> tuple[List[str], List[str], List[str]]:
        """Basic JavaScript/TypeScript analysis"""
        
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        functions = []
        classes = []
        imports = []
        
        lines = content.split('\n')
        for line in lines:
            line = line.strip()
            
            # Function declarations
            if line.startswith('function ') or 'function(' in line:
                # Basic function name extraction
                if 'function ' in line:
                    try:
                        func_name = line.split('function ')[1].split('(')[0].strip()
                        if func_name:
                            functions.append(func_name)
                    except IndexError:
                        pass
            
            # Class declarations
            if line.startswith('class '):
                try:
                    class_name = line.split('class ')[1].split(' ')[0].split('{')[0].strip()
                    if class_name:
                        classes.append(class_name)
                except IndexError:
                    pass
            
            # Import statements
            if line.startswith('import ') or line.startswith('from '):
                imports.append(line)
        
        return functions, classes, imports
    
    def _detect_language(self, file_path: Path) -> str:
        """Detect programming language from file extension"""
        
        extension = file_path.suffix.lower()
        language_map = {
            '.py': 'python',
            '.js': 'javascript',
            '.ts': 'typescript',
            '.jsx': 'javascript',
            '.tsx': 'typescript',
            '.java': 'java',
            '.c': 'c',
            '.cpp': 'cpp',
            '.cc': 'cpp',
            '.cxx': 'cpp',
            '.h': 'c',
            '.hpp': 'cpp',
            '.go': 'go',
            '.rs': 'rust',
            '.php': 'php',
            '.rb': 'ruby',
            '.sh': 'shell',
            '.bash': 'shell',
            '.zsh': 'shell',
            '.sql': 'sql',
            '.html': 'html',
            '.css': 'css',
            '.scss': 'scss',
            '.sass': 'sass',
            '.json': 'json',
            '.yaml': 'yaml',
            '.yml': 'yaml',
            '.xml': 'xml',
            '.md': 'markdown',
            '.txt': 'text',
            '.toml': 'toml',
            '.ini': 'ini',
            '.cfg': 'config'
        }
        
        return language_map.get(extension, 'unknown')
    
    async def _analyze_dependencies(self) -> None:
        """Analyze project dependencies from various sources"""
        
        dependencies = {}
        
        # Python dependencies
        requirements_files = ['requirements.txt', 'pyproject.toml', 'setup.py', 'Pipfile']
        for req_file in requirements_files:
            req_path = self.project_path / req_file
            if req_path.exists():
                deps = await self._parse_python_dependencies(req_path)
                if deps:
                    dependencies['python'] = deps
                break
        
        # Node.js dependencies
        package_json = self.project_path / 'package.json'
        if package_json.exists():
            deps = await self._parse_node_dependencies(package_json)
            if deps:
                dependencies['node'] = deps
        
        # Cargo dependencies (Rust)
        cargo_toml = self.project_path / 'Cargo.toml'
        if cargo_toml.exists():
            deps = await self._parse_cargo_dependencies(cargo_toml)
            if deps:
                dependencies['rust'] = deps
        
        self.context.dependencies = dependencies
    
    async def _parse_python_dependencies(self, file_path: Path) -> List[str]:
        """Parse Python dependencies from requirements files"""
        
        if file_path.name == 'requirements.txt':
            with open(file_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()
            
            deps = []
            for line in lines:
                line = line.strip()
                if line and not line.startswith('#'):
                    # Extract package name (before version specifiers)
                    pkg_name = line.split('==')[0].split('>=')[0].split('<=')[0].split('>')[0].split('<')[0]
                    deps.append(pkg_name.strip())
            return deps
        
        elif file_path.name == 'pyproject.toml':
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                # Basic TOML parsing for dependencies
                deps = []
                in_deps_section = False
                for line in content.split('\n'):
                    line = line.strip()
                    if line == 'dependencies = [':
                        in_deps_section = True
                        continue
                    elif line == ']' and in_deps_section:
                        break
                    elif in_deps_section and line.startswith('"'):
                        # Extract package name from quoted dependency
                        dep = line.split('"')[1].split('>=')[0].split('==')[0]
                        deps.append(dep.strip())
                
                return deps
            except Exception:
                return []
        
        return []
    
    async def _parse_node_dependencies(self, file_path: Path) -> List[str]:
        """Parse Node.js dependencies from package.json"""
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                package_data = json.load(f)
            
            deps = []
            if 'dependencies' in package_data:
                deps.extend(package_data['dependencies'].keys())
            if 'devDependencies' in package_data:
                deps.extend(package_data['devDependencies'].keys())
            
            return deps
        except Exception:
            return []
    
    async def _parse_cargo_dependencies(self, file_path: Path) -> List[str]:
        """Parse Rust dependencies from Cargo.toml"""
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            deps = []
            in_deps_section = False
            for line in content.split('\n'):
                line = line.strip()
                if line == '[dependencies]':
                    in_deps_section = True
                    continue
                elif line.startswith('[') and in_deps_section:
                    break
                elif in_deps_section and '=' in line:
                    dep_name = line.split('=')[0].strip()
                    deps.append(dep_name)
            
            return deps
        except Exception:
            return []
    
    async def _analyze_git_info(self) -> None:
        """Analyze git repository information if available"""
        
        git_dir = self.project_path / '.git'
        if not git_dir.exists():
            return
        
        try:
            # Basic git info that can be extracted without running git commands
            git_info = {
                "is_git_repo": True,
                "git_dir": str(git_dir)
            }
            
            # Try to read current branch from HEAD
            head_file = git_dir / 'HEAD'
            if head_file.exists():
                with open(head_file, 'r', encoding='utf-8') as f:
                    head_content = f.read().strip()
                    if head_content.startswith('ref: refs/heads/'):
                        git_info["current_branch"] = head_content.split('/')[-1]
            
            self.context.git_info = git_info
        except Exception:
            # If we can't read git info, just mark as git repo
            self.context.git_info = {"is_git_repo": True}
    
    def _should_ignore(self, name: str) -> bool:
        """Check if file/directory should be ignored"""
        
        for pattern in self._ignore_patterns:
            if pattern.startswith('*'):
                if name.endswith(pattern[1:]):
                    return True
            else:
                if name == pattern:
                    return True
        
        return False
    
    def get_file_context(self, file_path: str) -> Optional[FileInfo]:
        """Get context for specific file"""
        return self.context.files.get(file_path)
    
    def get_similar_files(self, file_path: str, language: Optional[str] = None) -> List[str]:
        """Find files similar to the given file"""
        
        if file_path in self.context.files:
            target_file = self.context.files[file_path]
            target_lang = language or target_file.language
        else:
            target_lang = language or "unknown"
        
        similar = []
        for path, file_info in self.context.files.items():
            if file_info.language == target_lang and path != file_path:
                similar.append(path)
        
        return similar
    
    def get_project_summary(self) -> Dict[str, Any]:
        """Get high-level project summary"""
        
        total_files = len(self.context.files)
        total_size = sum(f.size for f in self.context.files.values())
        
        language_counts = {}
        for file_info in self.context.files.values():
            lang = file_info.language
            language_counts[lang] = language_counts.get(lang, 0) + 1
        
        return {
            "total_files": total_files,
            "total_size_bytes": total_size,
            "languages": dict(language_counts),
            "dependencies": {k: len(v) for k, v in self.context.dependencies.items()},
            "has_git": bool(self.context.git_info),
            "main_language": max(language_counts.items(), key=lambda x: x[1])[0] if language_counts else "unknown"
        }
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert context to dictionary for serialization"""
        return asdict(self.context)
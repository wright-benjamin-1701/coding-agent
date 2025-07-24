"""
Pytest configuration and shared fixtures
"""
import pytest
import tempfile
import shutil
from pathlib import Path


@pytest.fixture(scope="session")
def temp_project_dir():
    """Create a temporary project directory for testing"""
    temp_dir = tempfile.mkdtemp(prefix="coding_agent_test_")
    
    # Create some test files
    project_path = Path(temp_dir)
    
    # Create a simple Python project structure
    (project_path / "src").mkdir()
    (project_path / "tests").mkdir()
    (project_path / "docs").mkdir()
    
    # Create some test files
    (project_path / "src" / "__init__.py").write_text("")
    (project_path / "src" / "main.py").write_text("""
#!/usr/bin/env python3
def main():
    print("Hello, World!")

if __name__ == "__main__":
    main()
""")
    
    (project_path / "tests" / "__init__.py").write_text("")
    (project_path / "tests" / "test_main.py").write_text("""
import unittest
from src.main import main

class TestMain(unittest.TestCase):
    def test_main(self):
        # Test main function
        pass
""")
    
    (project_path / "README.md").write_text("""
# Test Project

This is a test project for the coding agent.
""")
    
    (project_path / "requirements.txt").write_text("""
pytest>=7.0.0
""")
    
    yield str(project_path)
    
    # Cleanup
    shutil.rmtree(temp_dir)


@pytest.fixture
def sample_code_file(temp_project_dir):
    """Create a sample Python file for testing"""
    file_path = Path(temp_project_dir) / "sample.py"
    content = '''
"""Sample Python module for testing"""

import os
import sys
from typing import List, Dict, Any

class SampleClass:
    """A sample class for testing"""
    
    def __init__(self, name: str):
        self.name = name
        self.data: List[str] = []
    
    def add_item(self, item: str) -> None:
        """Add an item to the data list"""
        self.data.append(item)
    
    def get_items(self) -> List[str]:
        """Get all items"""
        return self.data.copy()
    
    def process_data(self, processor_func=None):
        """Process data with optional function"""
        if processor_func:
            return [processor_func(item) for item in self.data]
        return self.data

def helper_function(value: str) -> str:
    """A helper function"""
    return value.upper()

def main():
    """Main function"""
    sample = SampleClass("test")
    sample.add_item("hello")
    sample.add_item("world")
    
    processed = sample.process_data(helper_function)
    print(processed)

if __name__ == "__main__":
    main()
'''
    
    file_path.write_text(content)
    return str(file_path)


@pytest.fixture
def sample_git_repo(temp_project_dir):
    """Initialize a git repository in the temp directory"""
    import subprocess
    import os
    
    project_path = Path(temp_project_dir)
    
    # Initialize git repo
    subprocess.run(["git", "init"], cwd=project_path, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=project_path, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=project_path, capture_output=True)
    
    # Add and commit files
    subprocess.run(["git", "add", "."], cwd=project_path, capture_output=True)
    subprocess.run(["git", "commit", "-m", "Initial commit"], cwd=project_path, capture_output=True)
    
    return str(project_path)


@pytest.fixture
def mock_ollama_models():
    """Mock Ollama model list"""
    return [
        "qwen2.5-coder:7b",
        "qwen2.5-coder:32b", 
        "deepseek-coder:1.3b",
        "llama3.1:8b",
        "llama3.1:70b"
    ]
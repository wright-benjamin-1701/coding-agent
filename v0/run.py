#!/usr/bin/env python3
"""Simple launcher for the coding agent."""

import sys
from pathlib import Path

# Add src to path so we can import the module
src_path = Path(__file__).parent / "src"
sys.path.insert(0, str(src_path))

from coding_agent.main import main

if __name__ == '__main__':
    main()
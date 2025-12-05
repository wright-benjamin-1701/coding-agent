"""Brainstorming tool for generating search terms."""

from typing import Dict, Any
from .base import Tool
from ..types import ToolResult


class BrainstormSearchTermsTool(Tool):
    """Tool for brainstorming relevant search terms."""
    
    @property
    def name(self) -> str:
        return "brainstorm_search_terms"
    
    @property
    def description(self) -> str:
        return "Generate relevant search terms for a query"
    
    @property
    def parameters_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "The original query to brainstorm terms for"}
            },
            "required": ["query"]
        }
    
    @property
    def is_destructive(self) -> bool:
        return False
    
    def execute(self, query: str) -> ToolResult:
        """Generate search terms based on the query."""
        # Simple keyword extraction and expansion
        words = query.lower().split()
        
        # Remove common words
        stop_words = {'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by'}
        keywords = [word for word in words if word not in stop_words]
        
        # Add programming-related synonyms
        synonyms = {
            'function': ['func', 'method', 'def'],
            'class': ['struct', 'type', 'interface'],
            'variable': ['var', 'let', 'const'],
            'error': ['exception', 'fail', 'bug'],
            'test': ['spec', 'unittest', 'pytest'],
            'config': ['configuration', 'settings', 'options'],
            'file': ['document', 'script', 'module']
        }
        
        search_terms = set(keywords)
        for keyword in keywords:
            if keyword in synonyms:
                search_terms.update(synonyms[keyword])
        
        return ToolResult(
            success=True, 
            output=f"Search terms: {', '.join(sorted(search_terms))}"
        )
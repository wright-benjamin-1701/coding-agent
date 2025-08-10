"""Relevance filtering for context information using semantic similarity."""

import re
from typing import List, Dict, Any, Tuple
from collections import Counter
import math


class RelevanceFilter:
    """Filter context information based on semantic relevance to the current query."""
    
    def __init__(self, min_similarity_threshold: float = 0.15):
        self.min_similarity_threshold = min_similarity_threshold
        self.stop_words = {
            'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 
            'by', 'from', 'up', 'about', 'into', 'through', 'during', 'before', 'after', 
            'above', 'below', 'between', 'among', 'is', 'are', 'was', 'were', 'be', 'been', 
            'being', 'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would', 'should', 
            'could', 'can', 'may', 'might', 'must', 'shall', 'this', 'that', 'these', 'those',
            'i', 'you', 'he', 'she', 'it', 'we', 'they', 'me', 'him', 'her', 'us', 'them'
        }
    
    def _extract_keywords(self, text: str) -> List[str]:
        """Extract meaningful keywords from text."""
        # Convert to lowercase and extract words
        words = re.findall(r'\b[a-zA-Z]{3,}\b', text.lower())
        
        # Remove stop words and common programming terms that aren't meaningful
        filtered_words = [
            word for word in words 
            if word not in self.stop_words and len(word) > 2
        ]
        
        # Count word frequencies
        word_counts = Counter(filtered_words)
        
        # Return words sorted by frequency (most important first)
        return [word for word, count in word_counts.most_common()]
    
    def _calculate_cosine_similarity(self, keywords1: List[str], keywords2: List[str]) -> float:
        """Calculate cosine similarity between two keyword lists."""
        if not keywords1 or not keywords2:
            return 0.0
        
        # Create vocabulary
        vocab = list(set(keywords1 + keywords2))
        if not vocab:
            return 0.0
        
        # Create vectors
        vec1 = [keywords1.count(word) for word in vocab]
        vec2 = [keywords2.count(word) for word in vocab]
        
        # Calculate cosine similarity
        dot_product = sum(a * b for a, b in zip(vec1, vec2))
        magnitude1 = math.sqrt(sum(a * a for a in vec1))
        magnitude2 = math.sqrt(sum(a * a for a in vec2))
        
        if magnitude1 == 0 or magnitude2 == 0:
            return 0.0
        
        return dot_product / (magnitude1 * magnitude2)
    
    def _calculate_jaccard_similarity(self, keywords1: List[str], keywords2: List[str]) -> float:
        """Calculate Jaccard similarity between two keyword sets."""
        set1 = set(keywords1)
        set2 = set(keywords2)
        
        if not set1 and not set2:
            return 0.0
        
        intersection = len(set1.intersection(set2))
        union = len(set1.union(set2))
        
        return intersection / union if union > 0 else 0.0
    
    def _get_domain_relevance_score(self, current_keywords: List[str], summary_keywords: List[str]) -> float:
        """Calculate domain-specific relevance score."""
        # Technical domains and their keywords
        domain_keywords = {
            'database': ['sql', 'database', 'table', 'query', 'schema', 'db', 'sqlite', 'mysql', 'postgres'],
            'web': ['web', 'html', 'css', 'javascript', 'http', 'api', 'server', 'client', 'browser'],
            'testing': ['test', 'testing', 'pytest', 'unittest', 'mock', 'fixture', 'assert'],
            'file_ops': ['file', 'directory', 'folder', 'path', 'read', 'write', 'create', 'delete'],
            'git': ['git', 'commit', 'branch', 'merge', 'pull', 'push', 'repository', 'clone'],
            'tools': ['tool', 'tools', 'utility', 'helper', 'function', 'method', 'class'],
            'analysis': ['analyze', 'analysis', 'metrics', 'quality', 'review', 'check', 'scan'],
            'refactoring': ['refactor', 'refactoring', 'improve', 'optimize', 'clean', 'restructure'],
            'debugging': ['debug', 'debugging', 'error', 'bug', 'fix', 'trace', 'stack', 'exception']
        }
        
        # Find domain matches
        current_domains = set()
        summary_domains = set()
        
        for domain, keywords in domain_keywords.items():
            if any(kw in current_keywords for kw in keywords):
                current_domains.add(domain)
            if any(kw in summary_keywords for kw in keywords):
                summary_domains.add(domain)
        
        if not current_domains:
            return 0.5  # Neutral if no clear domain in current request
        
        # Calculate domain overlap
        domain_overlap = len(current_domains.intersection(summary_domains))
        domain_union = len(current_domains.union(summary_domains))
        
        return domain_overlap / domain_union if domain_union > 0 else 0.0
    
    def calculate_relevance_score(self, current_prompt: str, summary: str) -> float:
        """Calculate overall relevance score between current prompt and summary."""
        current_keywords = self._extract_keywords(current_prompt)
        summary_keywords = self._extract_keywords(summary)
        
        if not current_keywords:
            return 0.0  # Can't determine relevance without current keywords
        
        # Calculate different similarity measures
        cosine_sim = self._calculate_cosine_similarity(current_keywords, summary_keywords)
        jaccard_sim = self._calculate_jaccard_similarity(current_keywords, summary_keywords)
        domain_sim = self._get_domain_relevance_score(current_keywords, summary_keywords)
        
        # Weighted combination of similarities
        overall_score = (
            0.4 * cosine_sim +      # Word frequency similarity
            0.3 * jaccard_sim +     # Keyword overlap
            0.3 * domain_sim        # Domain relevance
        )
        
        return overall_score
    
    def filter_relevant_summaries(self, current_prompt: str, summaries: List[str], 
                                max_summaries: int = 3) -> List[Tuple[str, float]]:
        """Filter summaries by relevance and return with scores."""
        if not summaries:
            return []
        
        # Calculate relevance scores for all summaries
        scored_summaries = []
        for summary in summaries:
            score = self.calculate_relevance_score(current_prompt, summary)
            if score >= self.min_similarity_threshold:
                scored_summaries.append((summary, score))
        
        # Sort by relevance score (highest first) and limit
        scored_summaries.sort(key=lambda x: x[1], reverse=True)
        return scored_summaries[:max_summaries]
    
    def should_include_context(self, current_prompt: str, context_item: str) -> bool:
        """Determine if a context item should be included."""
        score = self.calculate_relevance_score(current_prompt, context_item)
        return score >= self.min_similarity_threshold
    
    def get_debug_info(self, current_prompt: str, summary: str) -> Dict[str, Any]:
        """Get detailed debugging information about relevance calculation."""
        current_keywords = self._extract_keywords(current_prompt)
        summary_keywords = self._extract_keywords(summary)
        
        cosine_sim = self._calculate_cosine_similarity(current_keywords, summary_keywords)
        jaccard_sim = self._calculate_jaccard_similarity(current_keywords, summary_keywords)
        domain_sim = self._get_domain_relevance_score(current_keywords, summary_keywords)
        overall_score = self.calculate_relevance_score(current_prompt, summary)
        
        return {
            'current_keywords': current_keywords[:10],  # Top 10
            'summary_keywords': summary_keywords[:10],   # Top 10
            'cosine_similarity': cosine_sim,
            'jaccard_similarity': jaccard_sim,
            'domain_similarity': domain_sim,
            'overall_score': overall_score,
            'threshold': self.min_similarity_threshold,
            'include': overall_score >= self.min_similarity_threshold
        }
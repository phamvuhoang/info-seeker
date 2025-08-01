from typing import List, Dict, Any
from datetime import datetime, timezone
import hashlib
import re
from ..core.config import settings


class DocumentProcessor:
    """
    Document processor for cleaning and validating search results.

    Note: Document storage and chunking functionality has been moved to
    vector_embedding_service.py which uses agno library patterns.
    This class now focuses on search result processing and validation.
    """

    def __init__(self):
        self.min_content_length = 50
        self.max_content_length = 10000

    
    def process_search_results(self, results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Process and clean search results"""
        processed_results = []
        seen_urls = set()
        
        for result in results:
            # Skip duplicates
            url = result.get('url', '')
            if url in seen_urls:
                continue
            seen_urls.add(url)
            
            # Clean and validate content
            processed_result = self._clean_result(result)
            if self._is_valid_result(processed_result):
                processed_results.append(processed_result)
        
        return processed_results
    
    # NOTE: _clean_content() and _split_into_chunks() methods have been moved to
    # vector_embedding_service.py which provides more comprehensive functionality
    # using agno library patterns.
    
    def _clean_result(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """Clean individual search result"""
        cleaned = result.copy()
        
        # Clean title
        title = cleaned.get('title', '').strip()
        cleaned['title'] = title[:200] if title else 'Untitled'
        
        # Clean content (basic cleaning)
        content = cleaned.get('content', '').strip()
        # Remove excessive whitespace and null characters
        content = ' '.join(content.split()).replace('\x00', '')
        cleaned['content'] = content
        
        # Ensure URL is present
        if not cleaned.get('url'):
            cleaned['url'] = ''
        
        # Add relevance score if not present
        if 'relevance_score' not in cleaned:
            cleaned['relevance_score'] = 0.5
        
        return cleaned
    
    def _is_valid_result(self, result: Dict[str, Any]) -> bool:
        """Check if result is valid for processing"""
        content = result.get('content', '')
        title = result.get('title', '')
        
        # Must have some content
        if len(content) < self.min_content_length and len(title) < 10:
            return False
        
        # Content shouldn't be too long
        if len(content) > self.max_content_length:
            return False
        
        # Skip results that look like error pages
        error_indicators = ['404', 'not found', 'error', 'access denied']
        content_lower = content.lower()
        title_lower = title.lower()
        
        for indicator in error_indicators:
            if indicator in content_lower or indicator in title_lower:
                return False
        
        return True
    
    def calculate_relevance_score(self, result: Dict[str, Any], query: str) -> float:
        """Calculate relevance score for search result"""
        score = 0.0
        query_terms = query.lower().split()
        
        title = result.get('title', '').lower()
        content = result.get('content', '').lower()
        
        # Title relevance (higher weight)
        for term in query_terms:
            if term in title:
                score += 0.3
        
        # Content relevance
        for term in query_terms:
            if term in content:
                score += 0.1
        
        # Boost for exact phrase matches
        if query.lower() in title:
            score += 0.5
        if query.lower() in content:
            score += 0.2
        
        # Normalize score
        return min(score, 1.0)
    
    def extract_key_phrases(self, content: str, max_phrases: int = 5) -> List[str]:
        """Extract key phrases from content"""
        # Simple keyword extraction - in production you might use more sophisticated NLP
        words = re.findall(r'\b[a-zA-Z]{3,}\b', content.lower())
        
        # Count word frequency
        word_freq = {}
        for word in words:
            word_freq[word] = word_freq.get(word, 0) + 1
        
        # Get most frequent words
        sorted_words = sorted(word_freq.items(), key=lambda x: x[1], reverse=True)
        
        return [word for word, _ in sorted_words[:max_phrases]]


# Initialize document processor
# Note: Document storage functionality has been moved to vector_embedding_service
document_processor = DocumentProcessor()

from typing import List, Dict, Any, Optional
import re
import hashlib
from datetime import datetime
from urllib.parse import urlparse


class ContentProcessor:
    """Process and clean content from various sources"""
    
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
    
    def _clean_result(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """Clean individual search result"""
        cleaned = {
            'title': self._clean_text(result.get('title', '')),
            'url': result.get('url', ''),
            'content': self._clean_text(result.get('snippet', '')),
            'source': result.get('source', 'Unknown'),
            'timestamp': datetime.now(),
            'content_hash': None
        }
        
        # Generate content hash for deduplication
        content_for_hash = f"{cleaned['title']}{cleaned['content']}"
        cleaned['content_hash'] = hashlib.md5(content_for_hash.encode()).hexdigest()
        
        # Extract domain for source reliability
        if cleaned['url']:
            parsed_url = urlparse(cleaned['url'])
            cleaned['domain'] = parsed_url.netloc
        
        return cleaned
    
    def _clean_text(self, text: str) -> str:
        """Clean and normalize text content"""
        if not text:
            return ""
        
        # Remove excessive whitespace
        text = re.sub(r'\s+', ' ', text)
        
        # Remove special characters but keep basic punctuation
        text = re.sub(r'[^\w\s\.\,\!\?\-\:\;]', '', text)
        
        return text.strip()
    
    def _is_valid_result(self, result: Dict[str, Any]) -> bool:
        """Validate if result meets quality criteria"""
        # Check minimum content length
        content = result.get('content', '')
        if len(content) < self.min_content_length:
            return False
        
        # Check if URL is valid
        url = result.get('url', '')
        if not url or not self._is_valid_url(url):
            return False
        
        # Check if title exists
        title = result.get('title', '')
        if not title or len(title) < 5:
            return False
        
        return True
    
    def _is_valid_url(self, url: str) -> bool:
        """Check if URL is valid and not from blocked domains"""
        try:
            parsed = urlparse(url)
            if not parsed.scheme or not parsed.netloc:
                return False
            
            # Block certain domains (spam, adult content, etc.)
            blocked_domains = {
                'example.com',
                'localhost',
                '127.0.0.1'
            }
            
            return parsed.netloc.lower() not in blocked_domains
        except:
            return False
    
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
    
    def deduplicate_results(self, results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Remove duplicate results based on content hash"""
        seen_hashes = set()
        unique_results = []
        
        for result in results:
            content_hash = result.get('content_hash')
            if content_hash and content_hash not in seen_hashes:
                seen_hashes.add(content_hash)
                unique_results.append(result)
        
        return unique_results
from typing import List, Dict, Any
from datetime import datetime, timezone
import hashlib
import re
from ..core.vector_db import VectorDatabaseManager
from ..core.config import settings


class DocumentProcessor:
    def __init__(self, vector_db_manager: VectorDatabaseManager = None):
        from ..core.vector_db import vector_db_manager as default_manager
        self.vector_db = vector_db_manager or default_manager
        self.chunk_size = settings.max_chunk_size
        self.chunk_overlap = settings.chunk_overlap
        self.min_content_length = 50
        self.max_content_length = 10000
    
    async def process_and_index_content(self, content: str, source_metadata: Dict[str, Any]) -> List[str]:
        """Process content into chunks and index them"""
        
        # Clean and prepare content
        cleaned_content = self._clean_content(content)
        
        if len(cleaned_content) < self.min_content_length:
            return []
        
        # Split into chunks
        chunks = self._split_into_chunks(cleaned_content)
        
        # Index each chunk
        document_ids = []
        for i, chunk in enumerate(chunks):
            chunk_metadata = {
                **source_metadata,
                'chunk_index': i,
                'total_chunks': len(chunks),
                'content_hash': hashlib.md5(chunk.encode()).hexdigest(),
                'processed_at': datetime.now(timezone.utc).isoformat()
            }
            
            try:
                doc_id = await self.vector_db.index_document(chunk, chunk_metadata)
                document_ids.append(doc_id)
            except Exception as e:
                print(f"Error indexing chunk {i}: {e}")
                continue
        
        return document_ids
    
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
    
    def _clean_content(self, content: str) -> str:
        """Clean and normalize content"""
        if not content:
            return ""
            
        # Remove excessive whitespace
        content = ' '.join(content.split())
        
        # Remove special characters that might interfere with search
        content = content.replace('\x00', '')
        
        # Remove very long lines that might be code or data
        lines = content.split('\n')
        cleaned_lines = []
        for line in lines:
            if len(line) < 500:  # Skip very long lines
                cleaned_lines.append(line)
        
        content = '\n'.join(cleaned_lines)
        
        return content.strip()
    
    def _split_into_chunks(self, content: str) -> List[str]:
        """Split content into overlapping chunks"""
        if len(content) <= self.chunk_size:
            return [content]
        
        chunks = []
        start = 0
        
        while start < len(content):
            end = start + self.chunk_size
            
            # Try to break at sentence boundary
            if end < len(content):
                # Look for sentence endings
                for i in range(end, max(start + self.chunk_size - 200, start), -1):
                    if content[i] in '.!?':
                        end = i + 1
                        break
            
            chunk = content[start:end].strip()
            if chunk and len(chunk) >= self.min_content_length:
                chunks.append(chunk)
            
            start = end - self.chunk_overlap
            if start >= len(content):
                break
        
        return chunks
    
    def _clean_result(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """Clean individual search result"""
        cleaned = result.copy()
        
        # Clean title
        title = cleaned.get('title', '').strip()
        cleaned['title'] = title[:200] if title else 'Untitled'
        
        # Clean content
        content = cleaned.get('content', '').strip()
        cleaned['content'] = self._clean_content(content)
        
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
from ..core.vector_db import vector_db_manager
document_processor = DocumentProcessor(vector_db_manager)

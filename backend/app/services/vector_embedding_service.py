"""
Vector Embedding Service for InfoSeeker

This service provides vector embedding functionality using the agno library patterns.
It handles:
1. Creating embeddings from text content using OpenAI's text-embedding-3-large model
2. Storing embeddings in PgVector database
3. Performing similarity searches
4. Managing document chunks and metadata
"""

import asyncio
import hashlib
import logging
from datetime import datetime
from typing import Dict, List, Optional, Any, Tuple
import json

from agno.embedder.openai import OpenAIEmbedder
from agno.vectordb.pgvector import PgVector
from agno.vectordb.search import SearchType
from agno.document import Document

from ..core.config import settings

logger = logging.getLogger(__name__)


class VectorEmbeddingService:
    """
    Vector embedding service that provides comprehensive embedding functionality
    following agno library patterns and best practices.
    """
    
    def __init__(self):
        try:
            # Initialize OpenAI embedder with text-embedding-3-large model
            self.embedder = OpenAIEmbedder(
                id=settings.embedding_model,
                dimensions=settings.embedding_dimensions
            )

            # Initialize PgVector database
            # Convert database URL format for PgVector compatibility
            db_url = settings.database_url
            if db_url.startswith("postgresql+psycopg://"):
                db_url = db_url.replace("postgresql+psycopg://", "postgresql+psycopg2://")

            self.vector_db = PgVector(
                table_name=settings.vector_table_name,
                schema="public",  # Use public schema
                db_url=db_url,
                embedder=self.embedder,
                search_type=SearchType.hybrid  # Combines semantic and keyword search
            )

            # Configuration
            self.chunk_size = settings.max_chunk_size
            self.chunk_overlap = settings.chunk_overlap

            self._initialized = True
            logger.info("Vector embedding service initialized successfully")

        except Exception as e:
            logger.error(f"Failed to initialize vector embedding service: {e}")
            self._initialized = False
            # Set fallback values
            self.embedder = None
            self.vector_db = None
            self.chunk_size = 1000
            self.chunk_overlap = 200
        
    async def create_embedding(self, text: str) -> List[float]:
        """
        Create embedding for a single text string.

        Args:
            text: Text to embed

        Returns:
            List of floats representing the embedding vector
        """
        if not self._initialized or not self.embedder:
            raise RuntimeError("Vector embedding service not properly initialized")

        try:
            embedding = self.embedder.get_embedding(text)
            if not embedding:
                raise ValueError("Failed to generate embedding - empty result")

            logger.debug(f"Created embedding with {len(embedding)} dimensions")
            return embedding

        except Exception as e:
            logger.error(f"Failed to create embedding: {e}")
            raise
    
    async def create_embedding_with_usage(self, text: str) -> Tuple[List[float], Optional[Dict]]:
        """
        Create embedding and return usage information.
        
        Args:
            text: Text to embed
            
        Returns:
            Tuple of (embedding, usage_info)
        """
        try:
            embedding, usage = self.embedder.get_embedding_and_usage(text)
            if not embedding:
                raise ValueError("Failed to generate embedding - empty result")
            
            logger.debug(f"Created embedding with {len(embedding)} dimensions, usage: {usage}")
            return embedding, usage
            
        except Exception as e:
            logger.error(f"Failed to create embedding with usage: {e}")
            raise
    
    def split_text_into_chunks(self, text: str) -> List[str]:
        """
        Split text into overlapping chunks for better embedding coverage.
        
        Args:
            text: Text to split
            
        Returns:
            List of text chunks
        """
        if len(text) <= self.chunk_size:
            return [text]
        
        chunks = []
        start = 0
        
        while start < len(text):
            end = start + self.chunk_size
            
            # Try to break at sentence boundary
            if end < len(text):
                # Look for sentence endings within the last 200 characters
                for i in range(end, max(start + self.chunk_size - 200, start), -1):
                    if text[i] in '.!?':
                        end = i + 1
                        break
            
            chunk = text[start:end].strip()
            if chunk:
                chunks.append(chunk)
            
            # Move start position with overlap
            start = end - self.chunk_overlap
            if start >= len(text):
                break
        
        return chunks
    
    def calculate_content_hash(self, content: str) -> str:
        """Calculate MD5 hash of content for deduplication."""
        return hashlib.md5(content.encode('utf-8')).hexdigest()
    
    async def store_document(self, content: str, metadata: Dict[str, Any]) -> List[str]:
        """
        Store a document in the vector database with automatic chunking.

        Args:
            content: Document content to store
            metadata: Metadata associated with the document

        Returns:
            List of document IDs that were created
        """
        if not self._initialized or not self.vector_db:
            logger.warning("Vector embedding service not initialized, skipping document storage")
            return []

        try:
            # Clean and prepare content
            cleaned_content = ' '.join(content.split())
            
            # Split into chunks
            chunks = self.split_text_into_chunks(cleaned_content)
            
            # Create documents for each chunk
            documents = []
            document_ids = []
            
            for i, chunk in enumerate(chunks):
                # Create unique metadata for each chunk
                chunk_metadata = {
                    **metadata,
                    'chunk_index': i,
                    'total_chunks': len(chunks),
                    'content_hash': self.calculate_content_hash(chunk),
                    'indexed_at': datetime.utcnow().isoformat(),
                    'chunk_size': len(chunk)
                }
                
                # Create document
                doc = Document(
                    content=chunk,
                    meta_data=chunk_metadata
                )
                
                documents.append(doc)
                document_ids.append(doc.id)
            
            # Store documents in vector database
            await asyncio.to_thread(self.vector_db.insert, documents)
            
            logger.info(f"Stored document with {len(chunks)} chunks, IDs: {document_ids[:3]}...")
            return document_ids
            
        except Exception as e:
            logger.error(f"Failed to store document: {e}")
            raise
    
    async def store_search_results(self, search_results: List[Dict[str, Any]], 
                                 query: str) -> List[str]:
        """
        Store search results as documents in the vector database.
        
        Args:
            search_results: List of search result dictionaries
            query: Original search query for context
            
        Returns:
            List of document IDs that were created
        """
        try:
            all_document_ids = []
            
            for i, result in enumerate(search_results):
                content = result.get('content', '')
                if not content:
                    continue
                
                # Create metadata for the search result
                metadata = {
                    'source_type': 'search_result',
                    'title': result.get('title', ''),
                    'url': result.get('url', ''),
                    'source': result.get('source', 'unknown'),
                    'relevance_score': result.get('relevance_score', 0.0),
                    'original_query': query,
                    'result_index': i,
                    'timestamp': result.get('timestamp', datetime.utcnow().isoformat())
                }
                
                # Store the document
                document_ids = await self.store_document(content, metadata)
                all_document_ids.extend(document_ids)
            
            logger.info(f"Stored {len(search_results)} search results as {len(all_document_ids)} document chunks")
            return all_document_ids
            
        except Exception as e:
            logger.error(f"Failed to store search results: {e}")
            raise
    
    async def similarity_search(self, query: str, limit: int = 10,
                              filters: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """
        Perform similarity search in the vector database.

        Args:
            query: Search query
            limit: Maximum number of results
            filters: Optional filters to apply

        Returns:
            List of search results with content, metadata, and similarity scores
        """
        if not self._initialized or not self.vector_db:
            logger.warning("Vector embedding service not initialized, returning empty results")
            return []

        try:
            # Perform vector search
            results = await asyncio.to_thread(
                self.vector_db.search, 
                query, 
                limit=limit, 
                filters=filters
            )
            
            # Convert results to dictionary format
            search_results = []
            for result in results:
                # Handle different result structures from agno
                if hasattr(result, 'document'):
                    # Standard Document result
                    document = result.document
                    content = document.content
                    metadata = document.meta_data
                    doc_id = document.id
                elif hasattr(result, 'content'):
                    # Direct Document object
                    content = result.content
                    metadata = getattr(result, 'meta_data', {})
                    doc_id = getattr(result, 'id', None)
                else:
                    # Fallback - try to extract from result directly
                    content = str(result)
                    metadata = {}
                    doc_id = None

                search_result = {
                    'content': content,
                    'metadata': metadata,
                    'similarity_score': getattr(result, 'similarity', 0.0),
                    'document_id': doc_id
                }
                search_results.append(search_result)
            
            logger.info(f"Found {len(search_results)} similar documents for query: {query[:50]}...")
            return search_results
            
        except Exception as e:
            logger.error(f"Failed to perform similarity search: {e}")
            raise
    
    async def get_document_by_id(self, document_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve a specific document by ID.
        
        Args:
            document_id: Document ID to retrieve
            
        Returns:
            Document data or None if not found
        """
        try:
            # Use filters to find specific document
            results = await self.similarity_search(
                query="", 
                limit=1, 
                filters={"id": document_id}
            )
            
            return results[0] if results else None
            
        except Exception as e:
            logger.error(f"Failed to get document by ID {document_id}: {e}")
            return None
    
    async def delete_documents_by_filter(self, filters: Dict[str, Any]) -> int:
        """
        Delete documents matching the given filters.
        
        Args:
            filters: Filters to match documents for deletion
            
        Returns:
            Number of documents deleted
        """
        try:
            # This would need to be implemented based on agno's delete functionality
            # For now, we'll log the request
            logger.info(f"Delete request for documents with filters: {filters}")
            # TODO: Implement actual deletion when agno supports it
            return 0
            
        except Exception as e:
            logger.error(f"Failed to delete documents: {e}")
            raise
    
    async def get_database_stats(self) -> Dict[str, Any]:
        """
        Get statistics about the vector database.
        
        Returns:
            Dictionary with database statistics
        """
        try:
            # Get basic stats - this would need to be implemented based on agno's capabilities
            stats = {
                'table_name': settings.vector_table_name,
                'embedding_model': settings.embedding_model,
                'embedding_dimensions': settings.embedding_dimensions,
                'chunk_size': self.chunk_size,
                'chunk_overlap': self.chunk_overlap
            }
            
            return stats
            
        except Exception as e:
            logger.error(f"Failed to get database stats: {e}")
            return {}


# Global vector embedding service instance
vector_embedding_service = VectorEmbeddingService()

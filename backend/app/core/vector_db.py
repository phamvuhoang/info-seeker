from agno.vectordb.pgvector import PgVector, SearchType
from agno.embedder.openai import OpenAIEmbedder
from agno.document import Document

from typing import List, Dict, Any
import hashlib
from datetime import datetime, timezone
from .config import settings


class VectorDatabaseManager:
    def __init__(self, db_url: str = None, table_name: str = None):
        self.embedder = OpenAIEmbedder(
            id=settings.embedding_model,
            dimensions=settings.embedding_dimensions
        )

        self.vector_db = PgVector(
            table_name=table_name or settings.vector_table_name,
            schema="public",  # Use public schema instead of ai schema
            db_url=db_url or settings.database_url,
            embedder=self.embedder,
            search_type=SearchType.hybrid  # Combines semantic and keyword search
        )

        # Initialize the table to ensure it exists
        self._initialize_table()

    def _initialize_table(self):
        """Initialize the vector database table if it doesn't exist"""
        try:
            # Check if table exists by trying to count documents
            from agno.document import Document

            # Try to search - if table doesn't exist, this will fail
            try:
                # This will fail if table doesn't exist
                list(self.vector_db.search("test", limit=1))
                print("Table already exists")
            except Exception:
                print("Table doesn't exist, creating with dummy document...")
                # Create table by adding a dummy document
                dummy_doc = Document(
                    name="__init__",
                    content="Initialization document - can be ignored",
                    meta_data={"type": "initialization"}
                )
                self.vector_db.upsert([dummy_doc])
                print("Table created successfully")
        except Exception as e:
            print(f"Note: Table initialization error: {e}")
    
    async def index_document(self, content: str, metadata: Dict[str, Any]) -> str:
        """Index a single document"""
        # Add content hash for deduplication
        content_hash = hashlib.md5(content.encode()).hexdigest()
        metadata['content_hash'] = content_hash
        metadata['indexed_at'] = datetime.now(timezone.utc).isoformat()

        document = Document(
            content=content,
            metadata=metadata
        )

        # Use vector database directly
        await self.vector_db.aupsert([document])
        return content_hash
    
    async def index_web_results(self, search_results: List[Dict[str, Any]]) -> List[str]:
        """Index web search results for future retrieval"""
        documents = []

        for result in search_results:
            content = result.get('content', '')
            if not content or len(content.strip()) < 50:  # Skip very short content
                continue

            doc = Document(
                content=content,
                metadata={
                    'title': result.get('title', ''),
                    'url': result.get('url', ''),
                    'source_type': 'web_search',
                    'indexed_at': datetime.now(timezone.utc).isoformat(),
                    'relevance_score': result.get('relevance_score', 0.0),
                    'content_hash': hashlib.md5(content.encode()).hexdigest()
                }
            )
            documents.append(doc)

        if not documents:
            return []

        # Use vector database directly
        await self.vector_db.aupsert(documents)
        return [doc.metadata['content_hash'] for doc in documents]
    
    async def search_similar(self, query: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Search for similar documents"""
        try:
            # Use the correct async_search method from PgVector
            results = await self.vector_db.async_search(query, limit=limit)
            return [
                {
                    'content': result.content,
                    'metadata': result.meta_data,
                    'similarity_score': 1.0  # PgVector doesn't return similarity scores directly
                }
                for result in results
            ]
        except Exception as e:
            print(f"Error searching vector database: {e}")
            # If the table doesn't exist or is empty, return empty results gracefully
            return []
    
    async def get_document_count(self) -> int:
        """Get total number of indexed documents"""
        try:
            # This is a simple implementation - in production you might want to use a proper count query
            results = await self.vector_db.asearch("", limit=1)
            return len(results) if results else 0
        except Exception:
            return 0
    
    async def delete_documents_by_source(self, source_type: str) -> int:
        """Delete documents by source type"""
        try:
            # This would need to be implemented based on the specific vector DB capabilities
            # For now, we'll return 0 as a placeholder
            print(f"Delete operation for source type: {source_type} not yet implemented")
            return 0
        except Exception:
            return 0


# Initialize vector database manager
vector_db_manager = VectorDatabaseManager()

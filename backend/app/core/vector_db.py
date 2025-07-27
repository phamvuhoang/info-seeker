from agno.vectordb.pgvector import PgVector, SearchType
from agno.embedder.openai import OpenAIEmbedder
from agno.document import Document

from typing import List, Dict, Any
import hashlib
from datetime import datetime, timezone
from .config import settings


class VectorDatabaseManager:
    def __init__(self, db_url: str = None, table_name: str = None):
        self.db_url = db_url
        self.table_name = table_name
        self._vector_db = None
        self._embedder = None
        self._initialized = False

    def _ensure_initialized(self):
        """Lazy initialization of vector database components"""
        if self._initialized:
            return

        try:
            self._embedder = OpenAIEmbedder(
                id=settings.embedding_model,
                dimensions=settings.embedding_dimensions
            )

            # Fix database URL format for PgVector - use psycopg2 driver
            fixed_db_url = (self.db_url or settings.database_url).replace('postgresql+psycopg://', 'postgresql+psycopg2://')

            self._vector_db = PgVector(
                table_name=self.table_name or settings.vector_table_name,
                schema="public",  # Use public schema instead of ai schema
                db_url=fixed_db_url,
                embedder=self._embedder,
                search_type=SearchType.hybrid  # Combines semantic and keyword search
            )

            # Initialize the table to ensure it exists
            self._initialize_table()
            self._initialized = True
        except Exception as e:
            print(f"Warning: Failed to initialize vector database: {e}")
            self._initialized = False

    @property
    def vector_db(self):
        """Get vector database instance with lazy initialization"""
        self._ensure_initialized()
        return self._vector_db

    @property
    def embedder(self):
        """Get embedder instance with lazy initialization"""
        self._ensure_initialized()
        return self._embedder

    def _initialize_table(self):
        """Initialize the vector database table if it doesn't exist"""
        if not self._vector_db:
            return

        try:
            # Check if table exists by trying to count documents
            from agno.document import Document

            # Try to search - if table doesn't exist, this will fail
            try:
                # This will fail if table doesn't exist
                list(self._vector_db.search("test", limit=1))
                print("Table already exists")
            except Exception:
                print("Table doesn't exist, creating with dummy document...")
                # Create table by adding a dummy document
                dummy_doc = Document(
                    name="__init__",
                    content="Initialization document - can be ignored",
                    meta_data={"type": "initialization"}
                )
                self._vector_db.upsert([dummy_doc])
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
        if self.vector_db:
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
        if self.vector_db:
            await self.vector_db.aupsert(documents)
        return [doc.metadata['content_hash'] for doc in documents]
    
    async def search_similar(self, query: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Search for similar documents"""
        try:
            # First try vector search if embeddings exist
            if self.vector_db:
                try:
                    results = await self.vector_db.async_search(query, limit=limit)
                    if results:
                        return [
                            {
                                'content': result.content,
                                'metadata': result.meta_data,
                                'similarity_score': 0.9,  # High score for vector search
                                'title': result.name or result.meta_data.get('title', 'Untitled') if result.meta_data else 'Untitled'
                            }
                            for result in results
                        ]
                except Exception as e:
                    print(f"Vector search failed, falling back to text search: {e}")

            # Fallback to text search
            return await self._text_search(query, limit)
        except Exception as e:
            print(f"Error searching vector database: {e}")
            return []

    async def _text_search(self, query: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Text search using SQL LIKE queries"""
        try:
            import psycopg

            # Fix database URL format for psycopg
            db_url = (self.db_url or settings.database_url).replace('postgresql+psycopg://', 'postgresql://')

            conn = await psycopg.AsyncConnection.connect(db_url)

            async with conn.cursor() as cursor:
                # Simple text search using ILIKE for case-insensitive search
                await cursor.execute(f"""
                    SELECT content, meta_data, name
                    FROM {self.table_name or settings.vector_table_name}
                    WHERE content ILIKE %s OR name ILIKE %s
                    ORDER BY
                        CASE
                            WHEN name ILIKE %s THEN 1
                            WHEN content ILIKE %s THEN 2
                            ELSE 3
                        END
                    LIMIT %s
                """, (f'%{query}%', f'%{query}%', f'%{query}%', f'%{query}%', limit))

                results = await cursor.fetchall()

                formatted_results = []
                for content, meta_data, name in results:
                    formatted_results.append({
                        'content': content,
                        'metadata': meta_data,
                        'similarity_score': 0.8,  # Default score for text search
                        'title': name or meta_data.get('title', 'Untitled') if meta_data else 'Untitled'
                    })

                await conn.close()
                return formatted_results

        except Exception as e:
            print(f"Error in text search: {e}")
            return []
    
    async def get_document_count(self) -> int:
        """Get total number of indexed documents"""
        try:
            if not self.vector_db:
                return 0
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

from agno.models.openai import OpenAIChat
from agno.storage.redis import RedisStorage
from agno.knowledge import AgentKnowledge
from agno.vectordb.pgvector import PgVector
from agno.embedder.openai import OpenAIEmbedder
from agno.vectordb.search import SearchType
from typing import Dict, Any, List
import asyncio
from datetime import datetime
import logging
from ..core.config import settings
from ..services.vector_embedding_service import vector_embedding_service
from ..services.sse_manager import progress_manager
from .base_streaming_agent import BaseStreamingAgent
import json

logger = logging.getLogger(__name__)


class RAGAgent(BaseStreamingAgent):
    def __init__(self, session_id: str = None):
        # Configure storage if session_id provided
        storage = None
        if session_id:
            try:
                # Parse Redis URL more safely
                redis_parts = settings.redis_url.replace("redis://", "").split("/")
                host_port = redis_parts[0].split(":")
                host = host_port[0]
                port = int(host_port[1]) if len(host_port) > 1 else 6379
                db = int(redis_parts[1]) if len(redis_parts) > 1 else 0

                storage = RedisStorage(
                    prefix="infoseeker_rag",
                    host=host,
                    port=port,
                    db=db
                )
            except Exception as e:
                print(f"Warning: Failed to configure Redis storage: {e}")
                storage = None

        # Create agno knowledge base for proper RAG functionality
        try:
            # Use the database URL as-is since we have psycopg available
            db_url = settings.database_url
            logger.info(f"Initializing RAG agent knowledge base with URL: {db_url}")

            knowledge_base = AgentKnowledge(
                vector_db=PgVector(
                    table_name=settings.vector_table_name,
                    schema="public",
                    db_url=db_url,
                    embedder=OpenAIEmbedder(
                        id=settings.embedding_model,
                        dimensions=settings.embedding_dimensions
                    ),
                    search_type=SearchType.hybrid
                ),
                num_documents=min(settings.max_rag_results, 3),  # Limit to 3 documents to prevent domination
            )
            logger.info("Successfully initialized agno knowledge base for RAG agent")
        except Exception as e:
            logger.error(f"Failed to initialize agno knowledge base: {e}", exc_info=True)
            knowledge_base = None

        super().__init__(
            name="RAG Specialist",
            model=OpenAIChat(
                id="gpt-4o",
                api_key=settings.openai_api_key
            ),
            knowledge=knowledge_base,  # Use agno's knowledge base
            description="RAG specialist for stored knowledge retrieval",
            instructions=[
                "You are the RAG specialist for InfoSeeker.",
                "Search the knowledge base using the search_knowledge_base tool for relevant stored information.",
                "Focus on finding the MOST relevant documents rather than all possible matches.",
                "Only use documents that are highly relevant to the user's query - similarity threshold filtering is applied.",
                "If the search returns documents but they are not relevant enough (below similarity threshold), treat it as no results found.",
                "Provide concise, focused answers based on the best matching documents.",
                "If you find highly relevant information, prioritize quality over quantity.",
                "Include specific citations and source metadata when available.",
                "If no highly relevant information is found, clearly state: 'No relevant information found in the knowledge base for this query.'",
                "Do not force connections or provide answers based on weakly related documents.",
                "Remember that web search will complement your findings with fresh information.",
                "IMPORTANT: Always respond in the same language as the user's query.",
                "If you receive a language instruction at the beginning of the message, follow it strictly.",
                "Maintain the same language throughout your entire response."
            ],
            storage=storage,
            search_knowledge=True,  # Enable knowledge base search tool
            show_tool_calls=True,
            markdown=True
        )

        self.session_id = session_id
        self.vector_embedding_service = vector_embedding_service  # Keep for backward compatibility

    async def _filter_documents_by_similarity(self, query: str, documents: List[Dict]) -> List[Dict]:
        """Filter documents based on similarity threshold"""
        if not documents or settings.rag_similarity_threshold is None:
            return documents

        try:
            # Get query embedding
            from openai import AsyncOpenAI
            client = AsyncOpenAI(api_key=settings.openai_api_key)

            query_response = await client.embeddings.create(
                input=query,
                model=settings.embedding_model
            )
            query_embedding = query_response.data[0].embedding

            filtered_docs = []
            for doc in documents:
                # Get document embedding if available
                doc_embedding = doc.get('embedding')
                if not doc_embedding:
                    # If no embedding available, include the document (backward compatibility)
                    filtered_docs.append(doc)
                    continue

                # Calculate cosine similarity
                similarity_score = self._calculate_cosine_similarity(query_embedding, doc_embedding)

                # Add similarity score to metadata
                if 'meta_data' not in doc:
                    doc['meta_data'] = {}
                doc['meta_data']['similarity_score'] = round(similarity_score, 3)

                # Filter by threshold
                if similarity_score >= settings.rag_similarity_threshold:
                    filtered_docs.append(doc)
                else:
                    logger.debug(f"Filtered out document with similarity {similarity_score:.3f} below threshold {settings.rag_similarity_threshold}")

            return filtered_docs

        except Exception as e:
            logger.error(f"Error filtering documents by similarity: {e}")
            # Return original documents if filtering fails
            return documents

    def _calculate_cosine_similarity(self, vec1: List[float], vec2: List[float]) -> float:
        """Calculate cosine similarity between two vectors"""
        import numpy as np

        try:
            v1 = np.array(vec1)
            v2 = np.array(vec2)

            # Calculate cosine similarity
            dot_product = np.dot(v1, v2)
            norm_v1 = np.linalg.norm(v1)
            norm_v2 = np.linalg.norm(v2)

            if norm_v1 == 0 or norm_v2 == 0:
                return 0.0

            similarity = dot_product / (norm_v1 * norm_v2)
            return float(similarity)

        except Exception as e:
            logger.error(f"Error calculating cosine similarity: {e}")
            return 0.0

    async def _filter_by_relevance(self, query: str, documents: List[Dict]) -> List[Dict]:
        """Filter documents by relevance using keyword-based entity matching"""
        if not documents:
            return documents

        try:
            # Extract key entities/topics from the query
            query_entities = self._extract_entities(query.lower())
            logger.info(f"Query entities: {query_entities}")

            filtered_docs = []

            for doc in documents:
                content = doc.get('content', '')
                doc_title = doc.get('name', doc.get('meta_data', {}).get('title', 'Untitled'))

                # Skip empty documents
                if not content.strip():
                    logger.debug(f"Skipping empty document: {doc_title}")
                    continue

                # Extract entities from document content
                doc_text = f"{doc_title} {content}".lower()
                doc_entities = self._extract_entities(doc_text)

                # Check for entity overlap
                common_entities = query_entities.intersection(doc_entities)
                relevance_score = len(common_entities) / max(len(query_entities), 1)

                # Strict threshold: require significant entity overlap
                if relevance_score >= 0.5 and common_entities:  # At least 50% entity overlap
                    # Add relevance score to metadata
                    if 'meta_data' not in doc:
                        doc['meta_data'] = {}
                    doc['meta_data']['relevance_score'] = f'{relevance_score:.2f}'
                    doc['meta_data']['common_entities'] = list(common_entities)
                    filtered_docs.append(doc)
                    logger.info(f"RELEVANT: {doc_title[:50]}... (score: {relevance_score:.2f}, entities: {list(common_entities)})")
                else:
                    logger.info(f"NOT_RELEVANT: {doc_title[:50]}... (score: {relevance_score:.2f}, entities: {list(common_entities)})")

            logger.info(f"Relevance filtering: {len(documents)} -> {len(filtered_docs)} documents")
            return filtered_docs

        except Exception as e:
            logger.error(f"Error in relevance filtering: {e}")
            # Return original documents if filtering fails
            return documents

    def _extract_entities(self, text: str) -> set:
        """Extract key entities (places, topics) from text"""
        import re

        # Common location names and topics
        entities = set()

        # Extract potential place names (capitalized words)
        words = re.findall(r'\b[a-z]+\b', text)

        # Add all words as potential entities
        entities.update(words)

        # Remove common stop words
        stop_words = {
            'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by',
            'is', 'are', 'was', 'were', 'be', 'been', 'being', 'have', 'has', 'had', 'do', 'does', 'did',
            'will', 'would', 'could', 'should', 'may', 'might', 'can', 'this', 'that', 'these', 'those',
            'i', 'you', 'he', 'she', 'it', 'we', 'they', 'me', 'him', 'her', 'us', 'them', 'my', 'your',
            'his', 'her', 'its', 'our', 'their', 'best', 'top', 'good', 'great', 'most', 'some', 'many',
            'tourist', 'attractions', 'spots', 'places', 'city', 'area', 'location', 'destination'
        }

        entities = entities - stop_words

        # Keep only meaningful entities (length > 2)
        entities = {e for e in entities if len(e) > 2}

        return entities

    async def _custom_similarity_search(self, query: str) -> List[Dict]:
        """Perform custom similarity search with threshold filtering"""
        try:
            # Use the vector embedding service to search with similarity scores
            results = await self.vector_embedding_service.similarity_search(
                query,
                limit=settings.max_rag_results * 2  # Get more results to filter
            )

            if not results:
                logger.info("No results from vector similarity search")
                return []

            # Log all similarity scores for analysis
            all_scores = [result.get('similarity_score', 0.0) for result in results]
            logger.info(f"All similarity scores: {[round(score, 3) for score in all_scores]}")

            # Filter by similarity threshold
            filtered_results = []
            for result in results:
                similarity_score = result.get('similarity_score', 0.0)
                if similarity_score >= settings.rag_similarity_threshold:
                    # Convert to agno document format
                    doc = {
                        'name': result.get('title', 'Untitled'),
                        'content': result.get('content', ''),
                        'meta_data': {
                            **result.get('metadata', {}),
                            'similarity_score': round(similarity_score, 3)
                        }
                    }
                    filtered_results.append(doc)
                    logger.info(f"PASSED: Document with similarity {similarity_score:.3f} (>= {settings.rag_similarity_threshold})")
                else:
                    logger.info(f"FILTERED: Document with similarity {similarity_score:.3f} (< {settings.rag_similarity_threshold})")

            # Limit to max results
            filtered_results = filtered_results[:settings.max_rag_results]

            logger.info(f"Custom similarity search: {len(results)} -> {len(filtered_results)} documents after filtering")
            return filtered_results

        except Exception as e:
            logger.error(f"Error in custom similarity search: {e}")
            return []
    
    async def search_knowledge_base(self, query: str, max_results: int = None) -> Dict[str, Any]:
        """Search the vector database for relevant information with enhanced logging"""
        max_results = max_results or settings.max_rag_results
        search_start_time = datetime.now()

        try:
            logger.info(f"Starting knowledge base search for query: {query[:100]}... (max_results: {max_results})")

            # Broadcast detailed progress
            if self.session_id:
                await progress_manager.broadcast_progress(
                    self.session_id,
                    {
                        "agent": self.name,
                        "status": "started",
                        "message": f"Searching knowledge base for: {query[:50]}...",
                        "details": {
                            "query_length": len(query),
                            "max_results": max_results,
                            "search_method": "vector_embedding_service"
                        }
                    }
                )

            # Check if vector embedding service is initialized
            if not self.vector_embedding_service._initialized:
                logger.error("Vector embedding service is not initialized")
                raise RuntimeError("Vector embedding service is not initialized")

            # Search vector database using vector embedding service
            logger.info("Calling vector_embedding_service.similarity_search...")
            results = await self.vector_embedding_service.similarity_search(query, limit=max_results)

            search_time = (datetime.now() - search_start_time).total_seconds()
            logger.info(f"Vector search completed in {search_time:.2f}s, found {len(results)} results")

            if not results:
                logger.warning("No results found in knowledge base search")
                # Broadcast completion with no results
                if self.session_id:
                    await progress_manager.broadcast_progress(
                        self.session_id,
                        {
                            "agent": self.name,
                            "status": "completed",
                            "message": "No relevant documents found in knowledge base.",
                            "details": {
                                "search_time": f"{search_time:.2f}s",
                                "results_count": 0,
                                "database_status": "empty_or_no_matches"
                            }
                        }
                    )

                return {
                    "status": "no_results",
                    "message": "No relevant information found in knowledge base.",
                    "results": [],
                    "query": query,
                    "search_time": search_time
                }

            # Process and format results with detailed logging
            formatted_results = []
            for i, result in enumerate(results):
                try:
                    formatted_result = {
                        "content": result["content"],
                        "similarity_score": result["similarity_score"],
                        "metadata": result["metadata"],
                        "source_type": result["metadata"].get("source_type", "unknown"),
                        "title": result["metadata"].get("title", "Untitled"),
                        "url": result["metadata"].get("url", ""),
                        "indexed_at": result["metadata"].get("indexed_at", "")
                    }
                    formatted_results.append(formatted_result)
                    logger.debug(f"Formatted result {i+1}: {formatted_result['title'][:50]}... (similarity: {formatted_result['similarity_score']:.3f})")
                except Exception as e:
                    logger.error(f"Error formatting result {i+1}: {e}")
                    continue

            # Log detailed results summary
            if formatted_results:
                avg_similarity = sum(r["similarity_score"] for r in formatted_results) / len(formatted_results)
                logger.info(f"Successfully formatted {len(formatted_results)} results, avg similarity: {avg_similarity:.3f}")

                # Log top results
                for i, result in enumerate(formatted_results[:3]):
                    logger.info(f"Top result {i+1}: '{result['title'][:50]}...' (similarity: {result['similarity_score']:.3f})")

            # Broadcast detailed progress
            if self.session_id:
                await progress_manager.broadcast_progress(
                    self.session_id,
                    {
                        "agent": self.name,
                        "status": "completed",
                        "message": f"Found {len(formatted_results)} relevant documents in {search_time:.2f}s",
                        "details": {
                            "results_count": len(formatted_results),
                            "search_time": f"{search_time:.2f}s",
                            "avg_similarity": sum(r["similarity_score"] for r in formatted_results) / len(formatted_results) if formatted_results else 0,
                            "top_similarity": max(r["similarity_score"] for r in formatted_results) if formatted_results else 0
                        },
                        "result_preview": f"Top result: {formatted_results[0]['title'][:50]}... (similarity: {formatted_results[0]['similarity_score']:.3f})" if formatted_results else "No results"
                    }
                )

            return {
                "status": "success",
                "message": f"Found {len(formatted_results)} relevant documents",
                "results": formatted_results,
                "query": query,
                "total_results": len(formatted_results),
                "search_time": search_time,
                "avg_similarity": sum(r["similarity_score"] for r in formatted_results) / len(formatted_results) if formatted_results else 0
            }

        except Exception as e:
            search_time = (datetime.now() - search_start_time).total_seconds()
            error_msg = f"Error searching knowledge base after {search_time:.2f}s: {str(e)}"
            logger.error(error_msg, exc_info=True)

            if self.session_id:
                await progress_manager.broadcast_progress(
                    self.session_id,
                    {
                        "agent": self.name,
                        "status": "failed",
                        "message": error_msg,
                        "details": {
                            "search_time": f"{search_time:.2f}s",
                            "error_type": type(e).__name__,
                            "vector_service_initialized": self.vector_embedding_service._initialized if hasattr(self.vector_embedding_service, '_initialized') else "unknown"
                        }
                    }
                )

            return {
                "status": "error",
                "message": error_msg,
                "results": [],
                "query": query,
                "search_time": search_time
            }

    async def enhanced_similarity_search(self, query: str, filters: Dict[str, Any] = None,
                                       max_results: int = None) -> Dict[str, Any]:
        """Enhanced similarity search with filtering and context management"""
        max_results = max_results or settings.max_rag_results

        try:
            # Apply default filters for better results
            search_filters = filters or {}

            # Search with filters
            results = await self.vector_embedding_service.similarity_search(
                query,
                limit=max_results,
                filters=search_filters
            )

            if not results:
                return {
                    "status": "no_results",
                    "message": "No relevant information found in knowledge base.",
                    "results": [],
                    "query": query
                }

            # Enhanced result processing with relevance scoring
            enhanced_results = []
            for result in results:
                # Calculate combined relevance score
                similarity_score = result.get("similarity_score", 0.0)
                metadata = result.get("metadata", {})

                # Boost score based on metadata quality
                quality_boost = 0.0
                if metadata.get("confidence_score", 0) > 0.8:
                    quality_boost += 0.1
                if metadata.get("source_type") in ["search_result", "web_source"]:
                    quality_boost += 0.05

                combined_score = min(similarity_score + quality_boost, 1.0)

                enhanced_result = {
                    "content": result["content"],
                    "similarity_score": similarity_score,
                    "combined_score": combined_score,
                    "metadata": metadata,
                    "source_type": metadata.get("source_type", "unknown"),
                    "title": metadata.get("title", "Untitled"),
                    "url": metadata.get("url", ""),
                    "indexed_at": metadata.get("indexed_at", ""),
                    "confidence_score": metadata.get("confidence_score", 0.0),
                    "language": metadata.get("language", "unknown")
                }
                enhanced_results.append(enhanced_result)

            # Sort by combined score
            enhanced_results.sort(key=lambda x: x["combined_score"], reverse=True)

            return {
                "status": "success",
                "message": f"Found {len(enhanced_results)} relevant documents",
                "results": enhanced_results,
                "query": query,
                "total_results": len(enhanced_results),
                "filters_applied": search_filters
            }

        except Exception as e:
            error_msg = f"Enhanced similarity search error: {str(e)}"
            logger.error(error_msg)

            return {
                "status": "error",
                "message": error_msg,
                "results": [],
                "query": query
            }

    async def arun(self, message: str, **kwargs) -> Any:
        """Enhanced RAG agent execution with detailed logging and progress updates"""
        start_time = datetime.now()
        try:
            logger.info(f"RAG Agent starting search for query: {message[:100]}...")

            # Enhanced progress tracking with more details
            if self.session_id:
                await progress_manager.broadcast_progress(
                    self.session_id,
                    {
                        "agent": self.name,
                        "status": "started",
                        "message": "RAG Specialist initializing knowledge base search...",
                        "details": {
                            "query_length": len(message),
                            "max_results": settings.max_rag_results,
                            "search_type": "hybrid_vector_search"
                        }
                    }
                )

            # First try using agno's built-in knowledge search (preferred method)
            if hasattr(self, 'knowledge') and self.knowledge:
                logger.info("Using agno's built-in knowledge base search")
                if self.session_id:
                    await progress_manager.broadcast_progress(
                        self.session_id,
                        {
                            "agent": self.name,
                            "status": "processing",
                            "message": "Using agno's built-in knowledge base search...",
                            "details": {"method": "agno_knowledge_base"}
                        }
                    )

                # Let agno handle the knowledge search automatically
                clean_kwargs = {k: v for k, v in kwargs.items()
                              if k not in ['stream', 'stream_intermediate_steps', 'show_full_reasoning']}
                final_response = await super().arun(message, **clean_kwargs)

                # Apply relevance filtering to all search results
                if final_response:
                    logger.info(f"RAG Agent response content length: {len(final_response.content) if final_response.content else 0}")
                    if hasattr(final_response, 'tools') and final_response.tools:
                        logger.info(f"RAG Agent made {len(final_response.tools)} tool calls")
                        for i, tool in enumerate(final_response.tools):
                            logger.info(f"Tool {i+1}: {tool.tool_name} - Success: {not tool.tool_call_error}")
                            if tool.tool_name == "search_knowledge_base" and tool.result:
                                try:
                                    import json
                                    docs = json.loads(tool.result)
                                    logger.info(f"Knowledge base search returned {len(docs)} documents")

                                    # Apply relevance filtering to all results
                                    filtered_docs = await self._filter_by_relevance(message, docs)

                                    if len(filtered_docs) == 0:
                                        logger.info("No documents are relevant to the query - updating response")
                                        final_response.content = "No relevant information found in the knowledge base for this query."
                                        tool.result = json.dumps([])
                                    else:
                                        logger.info(f"Relevance filtering: {len(docs)} -> {len(filtered_docs)} documents")
                                        tool.result = json.dumps(filtered_docs)

                                        for j, doc in enumerate(filtered_docs[:3]):  # Log first 3 docs
                                            doc_title = doc.get('name', doc.get('meta_data', {}).get('title', 'Untitled'))
                                            relevance = doc.get('meta_data', {}).get('relevance_score', 'N/A')
                                            logger.info(f"  Doc {j+1}: {doc_title[:50]}... (relevance: {relevance})")

                                except Exception as e:
                                    logger.error(f"Failed to parse or filter tool result: {e}")
                    else:
                        logger.warning("RAG Agent response has no tool calls - knowledge base search may not have been triggered")

                # Log successful completion
                processing_time = (datetime.now() - start_time).total_seconds()
                logger.info(f"RAG Agent completed successfully in {processing_time:.2f}s using agno knowledge base")

                if self.session_id:
                    await progress_manager.broadcast_progress(
                        self.session_id,
                        {
                            "agent": self.name,
                            "status": "completed",
                            "message": f"RAG analysis completed using agno knowledge base in {processing_time:.2f}s",
                            "details": {
                                "processing_time": f"{processing_time:.2f}s",
                                "method": "agno_knowledge_base",
                                "response_length": len(final_response.content) if final_response and final_response.content else 0
                            },
                            "result_preview": final_response.content[:200] + "..." if final_response and final_response.content and len(final_response.content) > 200 else (final_response.content if final_response and final_response.content else "Analysis completed")
                        }
                    )

                return final_response

            else:
                # Fallback to custom vector search (backward compatibility)
                logger.warning("Agno knowledge base not available, falling back to custom vector search")
                if self.session_id:
                    await progress_manager.broadcast_progress(
                        self.session_id,
                        {
                            "agent": self.name,
                            "status": "processing",
                            "message": "Falling back to custom vector search...",
                            "details": {"method": "custom_vector_search"}
                        }
                    )

                # Search the knowledge base using custom method
                search_results = await self.search_knowledge_base(message)

                logger.info(f"Custom vector search returned {len(search_results.get('results', []))} results")

                # Prepare context for the agent
                if search_results["status"] == "success" and search_results["results"]:
                    context = "Based on the knowledge base search, here are the relevant documents:\n\n"
                    for i, result in enumerate(search_results["results"][:3], 1):  # Limit to top 3 for performance
                        context += f"{i}. **{result['title']}** (Similarity: {result['similarity_score']:.2f})\n"
                        context += f"   Content: {result['content'][:150]}...\n"  # Shorter content for faster processing
                        if result['url']:
                            context += f"   Source: {result['url']}\n"
                        context += "\n"

                    enhanced_message = f"{message}\n\nKnowledge Base Context:\n{context}"
                    logger.info(f"Enhanced message with {len(search_results['results'])} document contexts")
                else:
                    enhanced_message = f"{message}\n\nNote: No relevant information found in the knowledge base."
                    logger.warning("No relevant documents found in knowledge base")

                # Run the agent with enhanced context
                clean_kwargs = {k: v for k, v in kwargs.items()
                              if k not in ['stream', 'stream_intermediate_steps', 'show_full_reasoning']}
                final_response = await super().arun(enhanced_message, **clean_kwargs)

                # Log completion with detailed metrics
                processing_time = (datetime.now() - start_time).total_seconds()
                logger.info(f"RAG Agent completed in {processing_time:.2f}s with {len(search_results.get('results', []))} documents")

                # Send detailed completion notification
                if self.session_id:
                    await progress_manager.broadcast_progress(
                        self.session_id,
                        {
                            "agent": self.name,
                            "status": "completed",
                            "message": f"RAG analysis completed. Found {len(search_results.get('results', []))} relevant documents in {processing_time:.2f}s",
                            "details": {
                                "documents_found": len(search_results.get('results', [])),
                                "processing_time": f"{processing_time:.2f}s",
                                "method": "custom_vector_search",
                                "search_status": search_results.get("status", "unknown"),
                                "response_length": len(final_response.content) if final_response and final_response.content else 0
                            },
                            "result_preview": final_response.content[:200] + "..." if final_response and final_response.content and len(final_response.content) > 200 else (final_response.content if final_response and final_response.content else "Analysis completed")
                        }
                    )

                return final_response

        except Exception as e:
            processing_time = (datetime.now() - start_time).total_seconds()
            error_msg = f"RAG Agent error after {processing_time:.2f}s: {str(e)}"
            logger.error(error_msg, exc_info=True)

            if self.session_id:
                await progress_manager.broadcast_progress(
                    self.session_id,
                    {
                        "agent": self.name,
                        "status": "failed",
                        "message": error_msg,
                        "details": {
                            "processing_time": f"{processing_time:.2f}s",
                            "error_type": type(e).__name__
                        }
                    }
                )

            raise e


def create_rag_agent(session_id: str = None) -> RAGAgent:
    """Create a RAG agent with optional session tracking"""
    return RAGAgent(session_id=session_id)

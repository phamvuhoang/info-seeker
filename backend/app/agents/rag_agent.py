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
                num_documents=settings.max_rag_results,  # Number of documents to retrieve
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
                "ALWAYS start by searching the knowledge base using the search_knowledge_base tool.",
                "Analyze ALL returned documents thoroughly before responding.",
                "If multiple documents are returned, synthesize the information coherently.",
                "Provide context-rich answers from indexed documents with specific citations.",
                "Include relevance scores and source metadata when available.",
                "Focus on comprehensive knowledge base coverage.",
                "Always cite sources with metadata when available.",
                "If no relevant information is found, clearly state this and explain why.",
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

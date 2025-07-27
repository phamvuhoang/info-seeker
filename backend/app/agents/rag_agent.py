from agno.models.openai import OpenAIChat
from agno.storage.redis import RedisStorage
from typing import Dict, Any, List
import asyncio
from datetime import datetime
import logging
from ..core.config import settings
from ..core.vector_db import vector_db_manager
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

        super().__init__(
            name="RAG Specialist",
            model=OpenAIChat(
                id="gpt-4o",
                api_key=settings.openai_api_key
            ),
            description="RAG specialist for stored knowledge retrieval",
            instructions=[
                "You are the RAG specialist for InfoSeeker.",
                "Search the vector database for relevant stored information.",
                "Provide context-rich answers from indexed documents.",
                "Include relevance scores and source metadata.",
                "Focus on comprehensive knowledge base coverage.",
                "Always cite sources with metadata when available.",
                "If no relevant information is found, clearly state this."
            ],
            storage=storage,
            show_tool_calls=True,
            markdown=True
        )
        
        self.session_id = session_id
        self.vector_db = vector_db_manager
    
    async def search_knowledge_base(self, query: str, max_results: int = None) -> Dict[str, Any]:
        """Search the vector database for relevant information"""
        max_results = max_results or settings.max_rag_results
        
        try:
            # Broadcast progress
            if self.session_id:
                await progress_manager.broadcast_progress(
                    self.session_id,
                    {
                        "agent": self.name,
                        "status": "started",
                        "message": f"Searching knowledge base for: {query[:50]}..."
                    }
                )
            
            # Search vector database
            results = await self.vector_db.search_similar(query, limit=max_results)
            
            if not results:
                # Broadcast completion with no results
                if self.session_id:
                    await progress_manager.broadcast_progress(
                        self.session_id,
                        {
                            "agent": self.name,
                            "status": "completed",
                            "message": "No relevant documents found in knowledge base. Database is empty."
                        }
                    )

                return {
                    "status": "no_results",
                    "message": "No relevant information found in knowledge base. Database is empty.",
                    "results": [],
                    "query": query
                }
            
            # Process and format results
            formatted_results = []
            for result in results:
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
            
            # Broadcast progress
            if self.session_id:
                await progress_manager.broadcast_progress(
                    self.session_id,
                    {
                        "agent": self.name,
                        "status": "completed",
                        "message": f"Found {len(formatted_results)} relevant documents",
                        "result_preview": f"Top result: {formatted_results[0]['title'][:50]}..." if formatted_results else ""
                    }
                )
            
            return {
                "status": "success",
                "message": f"Found {len(formatted_results)} relevant documents",
                "results": formatted_results,
                "query": query,
                "total_results": len(formatted_results)
            }
            
        except Exception as e:
            error_msg = f"Error searching knowledge base: {str(e)}"

            if self.session_id:
                await progress_manager.broadcast_progress(
                    self.session_id,
                    {
                        "agent": self.name,
                        "status": "failed",
                        "message": error_msg
                    }
                )

            return {
                "status": "error",
                "message": error_msg,
                "results": [],
                "query": query
            }


    
    async def arun(self, message: str, **kwargs) -> Any:
        """Override arun to add progress tracking"""
        try:
            # Send start notification
            if self.session_id:
                await progress_manager.broadcast_progress(
                    self.session_id,
                    {
                        "agent": self.name,
                        "status": "started",
                        "message": f"RAG Specialist is analyzing your query..."
                    }
                )
            
            # Detailed step-by-step reasoning
            await self._broadcast_step("🔍 Analyzing query for relevant knowledge...")
            await asyncio.sleep(0.3)

            await self._broadcast_step("📚 Searching through document embeddings...")
            # First search the knowledge base
            search_results = await self.search_knowledge_base(message)

            await self._broadcast_step(f"📄 Found {len(search_results.get('results', []))} relevant documents")
            await asyncio.sleep(0.2)
            
            # Prepare context for the agent
            if search_results["status"] == "success" and search_results["results"]:
                context = "Based on the knowledge base search, here are the relevant documents:\n\n"
                for i, result in enumerate(search_results["results"][:5], 1):
                    context += f"{i}. **{result['title']}** (Similarity: {result['similarity_score']:.2f})\n"
                    context += f"   Content: {result['content'][:200]}...\n"
                    if result['url']:
                        context += f"   Source: {result['url']}\n"
                    context += "\n"
                
                enhanced_message = f"{message}\n\nKnowledge Base Context:\n{context}"
            else:
                enhanced_message = f"{message}\n\nNote: No relevant information found in the knowledge base."
            
            # Run the agent with streaming enabled to capture detailed events
            final_response = await self.arun_with_streaming(enhanced_message, **kwargs)
            
            # Send completion notification
            if self.session_id:
                await progress_manager.broadcast_progress(
                    self.session_id,
                    {
                        "agent": self.name,
                        "status": "completed",
                        "message": f"RAG analysis completed. Found {len(search_results.get('results', []))} relevant documents.",
                        "result_preview": final_response.content[:200] + "..." if final_response and final_response.content and len(final_response.content) > 200 else (final_response.content if final_response and final_response.content else "Analysis completed")
                    }
                )

            return final_response
            
        except Exception as e:
            error_msg = f"RAG Agent error: {str(e)}"
            
            if self.session_id:
                await progress_manager.broadcast_progress(
                    self.session_id,
                    {
                        "agent": self.name,
                        "status": "failed",
                        "message": error_msg
                    }
                )
            
            raise e


def create_rag_agent(session_id: str = None) -> RAGAgent:
    """Create a RAG agent with optional session tracking"""
    return RAGAgent(session_id=session_id)

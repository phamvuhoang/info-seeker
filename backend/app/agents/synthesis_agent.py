from agno.models.openai import OpenAIChat
from agno.storage.redis import RedisStorage
from typing import Dict, Any, List
import asyncio
from datetime import datetime
from ..core.config import settings
from ..services.sse_manager import progress_manager
from .base_streaming_agent import BaseStreamingAgent


class SynthesisAgent(BaseStreamingAgent):
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
                    prefix="infoseeker_synthesis",
                    host=host,
                    port=port,
                    db=db
                )
            except Exception as e:
                print(f"Warning: Failed to configure Redis storage: {e}")
                storage = None

        super().__init__(
            name="Information Synthesizer",
            model=OpenAIChat(
                id="gpt-4o",
                api_key=settings.openai_api_key
            ),
            description="Information synthesis specialist",
            instructions=[
                "You are the information synthesis specialist for InfoSeeker.",
                "Combine information from RAG and web search results intelligently.",
                "Identify complementary and conflicting information across sources.",
                "Create coherent, comprehensive responses that leverage all available data.",
                "Maintain source attribution throughout synthesis.",
                "Highlight when information from different sources agrees or disagrees.",
                "Prioritize recent information for current events, stored knowledge for established facts.",
                "Create well-structured responses with clear sections and citations.",
                "Identify gaps in information and note areas where more research might be needed."
            ],
            storage=storage,
            show_tool_calls=True,
            markdown=True
        )
        
        self.session_id = session_id
    
    async def synthesize_information(self, 
                                   query: str,
                                   rag_results: Dict[str, Any] = None,
                                   web_results: Dict[str, Any] = None) -> Dict[str, Any]:
        """Synthesize information from multiple sources"""
        
        try:
            # Broadcast progress
            if self.session_id:
                await progress_manager.broadcast_progress(
                    self.session_id,
                    {
                        "agent": self.name,
                        "status": "started",
                        "message": "Synthesizing information from multiple sources..."
                    }
                )
            
            # Prepare synthesis context
            synthesis_context = self._prepare_synthesis_context(query, rag_results, web_results)
            
            # Create synthesis prompt
            synthesis_prompt = f"""
Query: {query}

Please synthesize the following information sources to provide a comprehensive answer:

{synthesis_context}

Instructions for synthesis:
1. Combine information from both stored knowledge and current web sources
2. Identify areas where sources agree or disagree
3. Prioritize recent information for current events
4. Maintain clear source attribution
5. Create a well-structured, coherent response
6. Note any gaps or limitations in the available information
"""
            
            # Run synthesis
            response = await super().arun(synthesis_prompt)
            
            # Analyze the synthesis
            analysis = self._analyze_synthesis(rag_results, web_results)
            
            # Broadcast progress
            if self.session_id:
                await progress_manager.broadcast_progress(
                    self.session_id,
                    {
                        "agent": self.name,
                        "status": "completed",
                        "message": f"Information synthesis completed. Combined {analysis['total_sources']} sources.",
                        "result_preview": response.content[:200] + "..." if len(response.content) > 200 else response.content
                    }
                )
            
            return {
                "status": "success",
                "synthesis": response.content,
                "analysis": analysis,
                "query": query
            }
            
        except Exception as e:
            error_msg = f"Error synthesizing information: {str(e)}"
            
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
                "synthesis": "",
                "query": query
            }
    
    def _prepare_synthesis_context(self, 
                                 query: str,
                                 rag_results: Dict[str, Any] = None,
                                 web_results: Dict[str, Any] = None) -> str:
        """Prepare context for synthesis"""
        
        context = ""
        
        # Add RAG results
        if rag_results and rag_results.get("status") == "success" and rag_results.get("results"):
            context += "## Stored Knowledge Base Results:\n\n"
            for i, result in enumerate(rag_results["results"][:5], 1):
                context += f"### Source {i} (Similarity: {result.get('similarity_score', 0):.2f})\n"
                context += f"**Title:** {result.get('title', 'Untitled')}\n"
                context += f"**Content:** {result.get('content', '')[:500]}...\n"
                if result.get('url'):
                    context += f"**URL:** {result['url']}\n"
                context += f"**Source Type:** {result.get('source_type', 'unknown')}\n"
                context += f"**Indexed:** {result.get('indexed_at', 'unknown')}\n\n"
        else:
            context += "## Stored Knowledge Base Results:\nNo relevant stored information found.\n\n"
        
        # Add web results
        if web_results and web_results.get("status") == "success" and web_results.get("results"):
            context += "## Current Web Search Results:\n\n"
            for i, result in enumerate(web_results["results"][:5], 1):
                context += f"### Source {i} (Relevance: {result.get('relevance_score', 0):.2f})\n"
                context += f"**Title:** {result.get('title', 'Untitled')}\n"
                context += f"**Content:** {result.get('content', '')[:500]}...\n"
                if result.get('url'):
                    context += f"**URL:** {result['url']}\n"
                context += f"**Timestamp:** {result.get('timestamp', 'unknown')}\n\n"
        else:
            context += "## Current Web Search Results:\nNo current web information found.\n\n"
        
        return context
    
    def _analyze_synthesis(self, 
                          rag_results: Dict[str, Any] = None,
                          web_results: Dict[str, Any] = None) -> Dict[str, Any]:
        """Analyze the synthesis for metadata"""
        
        analysis = {
            "total_sources": 0,
            "rag_sources": 0,
            "web_sources": 0,
            "source_types": set(),
            "has_recent_info": False,
            "has_stored_info": False
        }
        
        # Analyze RAG results
        if rag_results and rag_results.get("status") == "success":
            rag_count = len(rag_results.get("results", []))
            analysis["rag_sources"] = rag_count
            analysis["total_sources"] += rag_count
            analysis["has_stored_info"] = rag_count > 0
            
            for result in rag_results.get("results", []):
                source_type = result.get("source_type", "unknown")
                analysis["source_types"].add(source_type)
        
        # Analyze web results
        if web_results and web_results.get("status") == "success":
            web_count = len(web_results.get("results", []))
            analysis["web_sources"] = web_count
            analysis["total_sources"] += web_count
            analysis["has_recent_info"] = web_count > 0
            
            for result in web_results.get("results", []):
                analysis["source_types"].add("web_search")
        
        # Convert set to list for JSON serialization
        analysis["source_types"] = list(analysis["source_types"])
        
        return analysis
    
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
                        "message": "Information Synthesizer is combining sources..."
                    }
                )
            
            # Run the agent with streaming
            response = await self.arun_with_streaming(message, **kwargs)
            
            # Send completion notification
            if self.session_id:
                await progress_manager.broadcast_progress(
                    self.session_id,
                    {
                        "agent": self.name,
                        "status": "completed",
                        "message": "Information synthesis completed.",
                        "result_preview": response.content[:200] + "..." if len(response.content) > 200 else response.content
                    }
                )
            
            return response
            
        except Exception as e:
            error_msg = f"Synthesis Agent error: {str(e)}"
            
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


def create_synthesis_agent(session_id: str = None) -> SynthesisAgent:
    """Create a synthesis agent with optional session tracking"""
    return SynthesisAgent(session_id=session_id)

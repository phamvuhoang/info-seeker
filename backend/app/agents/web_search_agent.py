from agno.models.openai import OpenAIChat
from agno.storage.redis import RedisStorage
from typing import Dict, Any, List
from datetime import datetime, timezone
import asyncio
from ..core.config import settings
from ..tools.web_search import WebSearchTools
from ..services.sse_manager import progress_manager
from ..services.document_processor import document_processor
from .base_streaming_agent import BaseStreamingAgent


class WebSearchAgent(BaseStreamingAgent):
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
                    prefix="infoseeker_web",
                    host=host,
                    port=port,
                    db=db
                )
            except Exception as e:
                print(f"Warning: Failed to configure Redis storage: {e}")
                storage = None

        # Initialize web search tools
        web_search_tools = WebSearchTools()

        super().__init__(
            name="Web Search Specialist",
            model=OpenAIChat(
                id="gpt-4o",
                api_key=settings.openai_api_key
            ),
            description="Web search specialist for current information",
            instructions=[
                "You are the web search specialist for InfoSeeker.",
                "Search the web for the latest, most relevant information.",
                "Extract and summarize content from multiple sources.",
                "Prioritize recent and authoritative sources.",
                "Provide source URLs and publication dates.",
                "Focus on factual, up-to-date information.",
                "Always verify information from multiple sources when possible."
            ],
            tools=[web_search_tools],
            storage=storage,
            show_tool_calls=True,
            markdown=True
        )
        
        self.session_id = session_id
        self.web_tools = web_search_tools
    
    async def perform_web_search(self, query: str, max_results: int = None) -> Dict[str, Any]:
        """Perform web search and return structured results"""
        max_results = max_results or settings.max_web_results
        
        try:
            # Broadcast progress
            if self.session_id:
                await progress_manager.broadcast_progress(
                    self.session_id,
                    {
                        "agent": self.name,
                        "status": "started",
                        "message": f"Searching the web for: {query[:50]}..."
                    }
                )
            
            # Perform web search using the tools
            search_result = await self.web_tools.web_search(query, max_results)
            
            if "Web search failed" in search_result:
                return {
                    "status": "error",
                    "message": search_result,
                    "results": [],
                    "query": query
                }
            
            # Parse the search results (assuming they're in a structured format)
            # This is a simplified parser - in production you'd want more robust parsing
            results = self._parse_search_results(search_result, query)
            
            # Process results for quality and relevance
            processed_results = document_processor.process_search_results(results)
            
            # Calculate relevance scores
            for result in processed_results:
                result['relevance_score'] = document_processor.calculate_relevance_score(result, query)
            
            # Sort by relevance
            processed_results.sort(key=lambda x: x['relevance_score'], reverse=True)
            
            # Broadcast progress
            if self.session_id:
                await progress_manager.broadcast_progress(
                    self.session_id,
                    {
                        "agent": self.name,
                        "status": "completed",
                        "message": f"Found {len(processed_results)} web results",
                        "result_preview": f"Top result: {processed_results[0]['title'][:50]}..." if processed_results else ""
                    }
                )
            
            return {
                "status": "success",
                "message": f"Found {len(processed_results)} web results",
                "results": processed_results,
                "query": query,
                "total_results": len(processed_results)
            }
            
        except Exception as e:
            error_msg = f"Error performing web search: {str(e)}"
            
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
    
    def _parse_search_results(self, search_result: str, query: str) -> List[Dict[str, Any]]:
        """Parse search results from string format to structured data"""
        results = []
        
        # This is a simplified parser - you'd want more robust parsing in production
        # For now, we'll create mock results based on the search result string
        lines = search_result.split('\n')
        current_result = {}
        
        for line in lines:
            line = line.strip()
            if not line:
                if current_result:
                    results.append(current_result)
                    current_result = {}
                continue
            
            if line.startswith('Title:'):
                current_result['title'] = line.replace('Title:', '').strip()
            elif line.startswith('URL:'):
                current_result['url'] = line.replace('URL:', '').strip()
            elif line.startswith('Content:') or line.startswith('Summary:'):
                current_result['content'] = line.replace('Content:', '').replace('Summary:', '').strip()
            elif 'http' in line and not current_result.get('url'):
                current_result['url'] = line.strip()
            elif not current_result.get('content') and len(line) > 50:
                current_result['content'] = line
        
        # Add the last result if exists
        if current_result:
            results.append(current_result)
        
        # Ensure all results have required fields
        for result in results:
            if 'title' not in result:
                result['title'] = 'Web Search Result'
            if 'content' not in result:
                result['content'] = result.get('title', '')
            if 'url' not in result:
                result['url'] = ''
            result['source_type'] = 'web_search'
            result['search_query'] = query
            result['timestamp'] = datetime.now(timezone.utc).isoformat()
        
        return results
    
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
                        "message": f"Web Search Specialist is searching for current information..."
                    }
                )
            
            # Detailed step-by-step reasoning
            await self._broadcast_step("🌐 Formulating search queries...")
            await asyncio.sleep(0.3)

            await self._broadcast_step("🔎 Searching the web for current information...")
            # Perform web search
            search_results = await self.perform_web_search(message)

            await self._broadcast_step(f"📰 Retrieved {len(search_results.get('results', []))} web results")
            await asyncio.sleep(0.2)
            
            # Prepare context for the agent
            if search_results["status"] == "success" and search_results["results"]:
                context = "Based on the web search, here are the current results:\n\n"
                for i, result in enumerate(search_results["results"][:5], 1):
                    context += f"{i}. **{result['title']}** (Relevance: {result.get('relevance_score', 0):.2f})\n"
                    context += f"   Content: {result['content'][:200]}...\n"
                    if result['url']:
                        context += f"   Source: {result['url']}\n"
                    context += f"   Timestamp: {result.get('timestamp', 'Unknown')}\n\n"
                
                enhanced_message = f"{message}\n\nWeb Search Results:\n{context}"
            else:
                enhanced_message = f"{message}\n\nNote: No current web results found."
            
            # Run the agent with streaming
            response = await self.arun_with_streaming(enhanced_message, **kwargs)
            
            # Send completion notification
            if self.session_id:
                await progress_manager.broadcast_progress(
                    self.session_id,
                    {
                        "agent": self.name,
                        "status": "completed",
                        "message": f"Web search completed. Found {len(search_results.get('results', []))} current results.",
                        "result_preview": response.content[:200] + "..." if len(response.content) > 200 else response.content
                    }
                )
            
            return response
            
        except Exception as e:
            error_msg = f"Web Search Agent error: {str(e)}"
            
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


def create_web_search_agent(session_id: str = None) -> WebSearchAgent:
    """Create a web search agent with optional session tracking"""
    return WebSearchAgent(session_id=session_id)

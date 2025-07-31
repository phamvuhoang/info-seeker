from agno.models.openai import OpenAIChat
from agno.storage.redis import RedisStorage
from agno.tools.duckduckgo import DuckDuckGoTools
from typing import Dict, Any, List
from datetime import datetime, timezone
import asyncio
import json
import re
from ..core.config import settings
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

        # Initialize DuckDuckGo tools with optimized settings
        ddg_tools = DuckDuckGoTools(search=True, news=True, fixed_max_results=5)  # Reduced for performance

        super().__init__(
            name="Web Search Specialist",
            model=OpenAIChat(
                id="gpt-4o",
                api_key=settings.openai_api_key
            ),
            description="Web search specialist for current information",
            instructions=[
                "You are the web search specialist for InfoSeeker.",
                "Use DuckDuckGo search to find the most relevant information quickly.",
                "Extract key search terms from user requests.",
                "Search for current information using relevant keywords.",
                "Provide concise summaries with source URLs.",
                "Focus on factual, up-to-date information.",
                "Be efficient and provide results quickly.",
                "IMPORTANT: Always respond in the same language as the user's query.",
                "If you receive a language instruction at the beginning of the message, follow it strictly.",
                "Maintain the same language throughout your entire response."
            ],
            tools=[ddg_tools],
            storage=storage,
            show_tool_calls=True,
            markdown=True
        )

        self.session_id = session_id

    async def search_and_process(self, query: str) -> Dict[str, Any]:
        """Enhanced search method that processes and stores results"""
        try:
            # Run the agent to perform web search
            response = await self.arun(f"Search for comprehensive information about: {query}")

            if response and hasattr(response, 'content'):
                # Extract URLs and content from the response
                search_results = self._extract_search_results(response.content, query)

                # Store results for future use (async, don't wait)
                if search_results:
                    asyncio.create_task(self._store_web_results(search_results, query))

                return {
                    "content": response.content,
                    "search_results": search_results,
                    "status": "success"
                }
            else:
                return {
                    "content": "No search results found",
                    "search_results": [],
                    "status": "no_results"
                }

        except Exception as e:
            print(f"Web search error: {e}")
            return {
                "content": f"Web search failed: {str(e)}",
                "search_results": [],
                "status": "error"
            }

    def _extract_search_results(self, content: str, query: str) -> List[Dict[str, Any]]:
        """Extract structured search results from agent response"""
        results = []

        # Extract URLs from the content
        url_pattern = r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+'
        urls = re.findall(url_pattern, content)

        # Split content into sections (rough heuristic)
        sections = content.split('\n\n')

        for i, section in enumerate(sections):
            if len(section.strip()) < 50:  # Skip very short sections
                continue

            # Try to find a URL in this section
            section_urls = re.findall(url_pattern, section)
            url = section_urls[0] if section_urls else (urls[i] if i < len(urls) else "")

            # Extract title (look for markdown headers or first line)
            title_match = re.search(r'^#+\s*(.+)$', section, re.MULTILINE)
            if title_match:
                title = title_match.group(1).strip()
                content_text = section.replace(title_match.group(0), '').strip()
            else:
                lines = section.strip().split('\n')
                title = lines[0][:100] if lines else "Untitled"
                content_text = '\n'.join(lines[1:]) if len(lines) > 1 else section

            if content_text and len(content_text.strip()) > 30:
                results.append({
                    "title": title,
                    "content": content_text.strip(),
                    "url": url,
                    "source_type": "web_search",
                    "relevance_score": self._calculate_relevance(content_text, query),
                    "extracted_at": datetime.now(timezone.utc).isoformat()
                })

        return results[:10]  # Limit to top 10 results

    def _calculate_relevance(self, content: str, query: str) -> float:
        """Calculate relevance score between content and query"""
        query_terms = query.lower().split()
        content_lower = content.lower()

        score = 0.0
        for term in query_terms:
            if term in content_lower:
                # Count occurrences and boost score
                occurrences = content_lower.count(term)
                score += min(occurrences * 0.1, 0.3)  # Cap per term at 0.3

        # Boost for exact phrase matches
        if query.lower() in content_lower:
            score += 0.4

        return min(score, 1.0)

    async def _store_web_results(self, results: List[Dict[str, Any]], query: str):
        """Store web search results in vector database"""
        try:
            for result in results:
                content = result.get("content", "")
                if len(content.strip()) < 50:
                    continue

                metadata = {
                    "type": "web_search_result",
                    "title": result.get("title", ""),
                    "url": result.get("url", ""),
                    "source_type": "web_search",
                    "relevance_score": result.get("relevance_score", 0.5),
                    "query": query,
                    "session_id": self.session_id,
                    "extracted_at": result.get("extracted_at", datetime.now(timezone.utc).isoformat())
                }

                await document_processor.process_and_index_content(content, metadata)

            print(f"Stored {len(results)} web search results for query: {query[:50]}...")

        except Exception as e:
            print(f"Error storing web results: {e}")

    # Web search functionality is now handled directly by DuckDuckGoTools
    # The agent will automatically use the tools when needed


def create_web_search_agent(session_id: str = None) -> WebSearchAgent:
    """Create a web search agent with optional session tracking"""
    return WebSearchAgent(session_id=session_id)

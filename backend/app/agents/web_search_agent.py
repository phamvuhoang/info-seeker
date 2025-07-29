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

        # Initialize DuckDuckGo tools
        ddg_tools = DuckDuckGoTools(search=True, news=True, fixed_max_results=10)

        super().__init__(
            name="Web Search Specialist",
            model=OpenAIChat(
                id="gpt-4o",
                api_key=settings.openai_api_key
            ),
            description="Web search specialist for current information",
            instructions=[
                "You are the web search specialist for InfoSeeker.",
                "Use DuckDuckGo search and news tools to find the latest, most relevant information.",
                "Extract specific search keywords from user requests.",
                "Search for current news and information using relevant keywords.",
                "Provide source URLs and publication information.",
                "Focus on factual, up-to-date information.",
                "Always include sources in your responses."
            ],
            tools=[ddg_tools],
            storage=storage,
            show_tool_calls=True,
            markdown=True
        )

        self.session_id = session_id
    
    # Web search functionality is now handled directly by DuckDuckGoTools
    # The agent will automatically use the tools when needed
    
    # Old parsing method removed - DuckDuckGoTools handles this automatically
    
    # Using BaseStreamingAgent's arun method directly
    # DuckDuckGoTools will be called automatically by the agent when needed


def create_web_search_agent(session_id: str = None) -> WebSearchAgent:
    """Create a web search agent with optional session tracking"""
    return WebSearchAgent(session_id=session_id)

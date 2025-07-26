from agno.agent import Agent
from agno.models.openai import OpenAIChat
from agno.storage.redis import RedisStorage
from ..core.config import settings
from ..tools.web_search import WebSearchTools


def create_search_agent(session_id: str = None) -> Agent:
    """Create InfoSeeker search agent with Agno framework"""

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
                host=host,
                port=port,
                db=db
            )
        except Exception as e:
            print(f"Warning: Failed to configure Redis storage: {e}")
            storage = None

    # Initialize tools
    web_search_tools = WebSearchTools()

    agent = Agent(
        name="InfoSeeker Assistant",
        model=OpenAIChat(
            id="gpt-4o",
            api_key=settings.openai_api_key
        ),
        description="InfoSeeker AI assistant for information retrieval and answer generation",
        instructions=[
            "You are InfoSeeker, an AI-powered search assistant.",
            "Provide concise, accurate, and contextually relevant answers.",
            "Always cite sources when available.",
            "Ask clarifying questions when the query is ambiguous.",
            "Prioritize recent information for current events.",
            "Combine information from multiple sources for comprehensive answers.",
            "Use web search to find current information when needed.",
            "Extract content from relevant URLs to provide detailed answers."
        ],
        tools=[web_search_tools],
        storage=storage,
        session_id=session_id,
        show_tool_calls=True,
        markdown=True
    )

    return agent
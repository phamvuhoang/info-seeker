from fastapi import APIRouter, HTTPException, Query, BackgroundTasks
from typing import Optional
import time
import uuid
import logging
from ..models.search import SearchQuery, SearchResponse, SearchResult
from ..agents.search_agent import create_search_agent
from ..agents.team_coordinator import create_search_team
from ..services.content_processor import ContentProcessor
from pydantic import BaseModel

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

router = APIRouter()
content_processor = ContentProcessor()


class HybridSearchRequest(BaseModel):
    query: str
    session_id: str
    include_web: bool = True
    include_rag: bool = True
    max_results: int = 10


class HybridSearchResponse(BaseModel):
    status: str
    session_id: str
    message: str


@router.post("/search", response_model=SearchResponse)
async def search(
    query: SearchQuery,
    session_id: Optional[str] = Query(None, description="Session ID for maintaining context")
):
    """Search endpoint for InfoSeeker"""
    start_time = time.time()

    try:
        # Generate session ID if not provided
        if not session_id:
            session_id = str(uuid.uuid4())

        logger.info(f"Processing search query: '{query.query}' for session: {session_id}")

        # Create agent
        agent = create_search_agent(session_id)

        # Run the agent with the query
        response = await agent.arun(query.query)

        # Extract answer content
        answer = response.content if hasattr(response, 'content') else str(response)

        # Process sources if available (this will be enhanced when web search is integrated)
        sources = []
        if hasattr(response, 'sources') and response.sources:
            processed_sources = content_processor.process_search_results(response.sources)
            sources = [
                SearchResult(
                    title=source.get('title', ''),
                    content=source.get('content', ''),
                    url=source.get('url'),
                    source=source.get('source', 'Unknown'),
                    relevance_score=content_processor.calculate_relevance_score(source, query.query),
                    timestamp=source.get('timestamp')
                )
                for source in processed_sources
            ]

        processing_time = time.time() - start_time

        # Create response
        search_response = SearchResponse(
            query=query.query,
            answer=answer,
            sources=sources,
            processing_time=processing_time,
            session_id=session_id
        )

        logger.info(f"Search completed in {processing_time:.2f}s for session: {session_id}")

        return search_response

    except Exception as e:
        logger.error(f"Search failed for query '{query.query}': {str(e)}")
        raise HTTPException(status_code=500, detail=f"Search failed: {str(e)}")


@router.post("/search/hybrid", response_model=HybridSearchResponse)
async def hybrid_search(request: HybridSearchRequest, background_tasks: BackgroundTasks):
    """Multi-agent hybrid search with real-time updates"""

    try:
        logger.info(f"Starting hybrid search for session {request.session_id}: {request.query}")

        # Start background task for search
        background_tasks.add_task(
            execute_hybrid_search,
            request.query,
            request.session_id,
            request.include_web,
            request.include_rag,
            request.max_results
        )

        return HybridSearchResponse(
            status="started",
            session_id=request.session_id,
            message="Multi-agent search initiated. Connect to SSE endpoint for real-time updates."
        )

    except Exception as e:
        logger.error(f"Failed to start hybrid search: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to start search: {str(e)}")


async def execute_hybrid_search(
    query: str,
    session_id: str,
    include_web: bool,
    include_rag: bool,
    max_results: int
):
    """Execute the multi-agent hybrid search workflow"""

    try:
        logger.info(f"Executing hybrid search for session {session_id}")

        # Create search team
        search_team = create_search_team(session_id)

        # Execute hybrid search
        result = await search_team.execute_hybrid_search(
            query=query,
            include_rag=include_rag,
            include_web=include_web,
            max_results=max_results
        )

        logger.info(f"Hybrid search completed for session {session_id}")

    except Exception as e:
        logger.error(f"Hybrid search failed for session {session_id}: {str(e)}")
        # Error will be broadcast by the search team


@router.get("/search/history/{session_id}")
async def get_search_history(session_id: str):
    """Get search history for a session"""
    # TODO: Implement search history retrieval
    return {"session_id": session_id, "history": []}
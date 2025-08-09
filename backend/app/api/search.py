from fastapi import APIRouter, HTTPException, Query, BackgroundTasks, Request
from typing import Optional, List, Dict, Any
import time
import uuid
import logging
from ..models.search import (
    SearchQuery, SearchResponse, SearchResult,
    SiteSpecificSearchQuery, SiteSpecificSearchResponse, ProductResult,
    SearchIntentResponse, EnhancedSearchResponse
)
from ..agents.search_agent import create_search_agent
from ..agents.team_coordinator import create_search_team
from ..agents.rag_agent import create_rag_agent
from ..services.content_processor import ContentProcessor
from ..services.database_service import database_service
from ..services.vector_embedding_service import vector_embedding_service
from ..services.search_intent_detector import search_intent_detector
from ..services.jina_ai_client import jina_ai_client
from ..services.site_config_service import site_config_service
from ..services.rate_limiter import rate_limit_manager, error_handler
from pydantic import BaseModel, Field

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


class SearchFeedbackRequest(BaseModel):
    session_id: str
    query: str
    rating: int = Field(..., ge=1, le=5, description="Rating from 1 to 5")
    feedback_text: Optional[str] = None
    sources_helpful: Optional[List[str]] = None


class RAGSearchRequest(BaseModel):
    query: str
    max_results: int = Field(10, description="Maximum number of results to return")
    filters: Optional[Dict[str, Any]] = Field(None, description="Optional filters for search")
    include_metadata: bool = Field(True, description="Include metadata in results")


class RAGSearchResult(BaseModel):
    content: str
    similarity_score: float
    combined_score: Optional[float] = None
    metadata: Dict[str, Any]
    source_type: str
    title: str
    url: Optional[str] = None
    indexed_at: Optional[str] = None
    confidence_score: Optional[float] = None
    language: Optional[str] = None


class RAGSearchResponse(BaseModel):
    status: str
    message: str
    query: str
    results: List[RAGSearchResult]
    total_results: int
    filters_applied: Optional[Dict[str, Any]] = None
    processing_time: float


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

        # Save search to database
        await database_service.save_search_history(
            session_id=session_id,
            query=query.query,
            response=answer,
            sources=[{
                'title': source.title,
                'url': source.url,
                'source': source.source,
                'relevance_score': source.relevance_score
            } for source in sources],
            processing_time=processing_time
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

        # Execute hybrid search (RAG + Web only)
        result = await search_team.execute_hybrid_search(
            query=query,
            include_rag=include_rag,
            include_web=include_web,
            include_site_specific=False,  # Always False for hybrid search
            target_sites=None,  # No target sites for hybrid search
            max_results=max_results
        )

        logger.info(f"Hybrid search completed for session {session_id}")

    except Exception as e:
        logger.error(f"Hybrid search failed for session {session_id}: {str(e)}")
        # Error will be broadcast by the search team


@router.post("/search/site-specific", response_model=SiteSpecificSearchResponse)
async def site_specific_search(request: SiteSpecificSearchQuery, http_request: Request):
    """Enhanced site-specific search with detailed product results and pagination"""

    try:
        logger.info(f"Starting site-specific search: {request.query} on sites: {request.target_sites} (page {request.page})")

        # Check rate limits
        client_ip = http_request.client.host
        api_rate_check = await rate_limit_manager.check_api_rate_limit(client_ip)
        if not api_rate_check["allowed"]:
            raise HTTPException(
                status_code=429,
                detail=api_rate_check["message"],
                headers={"Retry-After": str(int(api_rate_check["wait_time"]))}
            )

        jina_rate_check = await rate_limit_manager.check_jina_rate_limit()
        if not jina_rate_check["allowed"]:
            raise HTTPException(
                status_code=429,
                detail=jina_rate_check["message"],
                headers={"Retry-After": str(int(jina_rate_check["wait_time"]))}
            )

        # Validate target sites
        try:
            active_sites = await site_config_service.get_active_sites()
            invalid_sites = [site for site in request.target_sites if site not in active_sites]

            if invalid_sites:
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid or inactive sites: {', '.join(invalid_sites)}"
                )
        except Exception as e:
            error_info = error_handler.handle_site_config_error(e)
            raise HTTPException(status_code=500, detail=error_info["user_message"])

        # Perform site-specific search with enhanced results
        start_time = time.time()
        try:
            # Calculate results per site based on pagination
            results_per_site = max(request.per_page, 10)  # Get more results for better pagination

            search_responses = await jina_ai_client.search_multiple_sites(
                query=request.query,
                site_keys=request.target_sites,
                max_results_per_site=results_per_site
            )
        except Exception as e:
            error_info = error_handler.handle_jina_api_error(e)
            if error_info["retry_after"]:
                raise HTTPException(
                    status_code=503,
                    detail=error_info["user_message"],
                    headers={"Retry-After": str(error_info["retry_after"])}
                )
            else:
                raise HTTPException(status_code=500, detail=error_info["user_message"])

        # Process and enhance results
        all_products = []
        successful_sites = []
        failed_sites = []
        total_tokens = 0

        for site_key, response in search_responses.items():
            if response.success:
                successful_sites.append(site_key)
                total_tokens += response.total_tokens_used

                site_config = active_sites.get(site_key)
                site_name = site_config.site_name if site_config else site_key

                for result in response.results:
                    # Extract enhanced product information
                    product = ProductResult(
                        title=result.title or "No title",
                        description=result.description or "",
                        url=result.url or "",
                        image_url=_extract_image_url(result.metadata, result.content),
                        price=_extract_price(result.metadata, result.content),
                        rating=_extract_rating(result.metadata, result.content),
                        site_key=result.site_key,
                        site_name=site_name,
                        content=result.content[:500] + "..." if len(result.content) > 500 else result.content,
                        metadata=result.metadata,
                        tokens_used=result.tokens_used,
                        relevance_score=_calculate_relevance_score(result, request.query)
                    )
                    all_products.append(product)
            else:
                failed_sites.append(site_key)
                logger.error(f"Site search failed for {site_key}: {response.error_message}")

        # Apply sorting
        all_products = _sort_products(all_products, request.sort_by)

        # Apply filtering
        if request.filter_by_site:
            all_products = [p for p in all_products if p.site_key == request.filter_by_site]

        # Apply pagination
        total_results = len(all_products)
        start_idx = (request.page - 1) * request.per_page
        end_idx = start_idx + request.per_page
        paginated_products = all_products[start_idx:end_idx]

        # Calculate pagination info
        total_pages = (total_results + request.per_page - 1) // request.per_page
        pagination = {
            "current_page": request.page,
            "per_page": request.per_page,
            "total_pages": total_pages,
            "total_results": total_results,
            "has_next": request.page < total_pages,
            "has_prev": request.page > 1,
            "next_page": request.page + 1 if request.page < total_pages else None,
            "prev_page": request.page - 1 if request.page > 1 else None
        }

        processing_time = time.time() - start_time

        return SiteSpecificSearchResponse(
            query=request.query,
            results=paginated_products,
            pagination=pagination,
            sites_searched=successful_sites,
            sites_failed=failed_sites,
            total_results=total_results,
            total_tokens_used=total_tokens,
            processing_time=processing_time
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Site-specific search failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Site-specific search failed: {str(e)}")


@router.post("/search/intent", response_model=SearchIntentResponse)
async def analyze_search_intent(query: str = Query(..., description="Query to analyze")):
    """Analyze search intent and get recommendations"""

    try:
        logger.info(f"Analyzing search intent for: {query}")

        recommendations = await search_intent_detector.get_search_recommendations(query)

        return SearchIntentResponse(
            query=recommendations["query"],
            detected_language=recommendations["detected_language"],
            category=recommendations["category"],
            recommendations=recommendations["recommendations"],
            confidence=recommendations["confidence"],
            reasoning=recommendations["reasoning"]
        )

    except Exception as e:
        logger.error(f"Search intent analysis failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Intent analysis failed: {str(e)}")


@router.get("/search/sites/active")
async def get_active_sites():
    """Get list of active sites available for site-specific search"""

    try:
        active_sites = await site_config_service.get_active_sites()

        sites_info = []
        for site_key, config in active_sites.items():
            sites_info.append({
                "site_key": site_key,
                "site_name": config.site_name,
                "site_url": config.site_url,
                "category": config.category,
                "language": config.language,
                "country": config.country
            })

        return {
            "active_sites": sites_info,
            "total_count": len(sites_info)
        }

    except Exception as e:
        logger.error(f"Failed to get active sites: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to get active sites: {str(e)}")


# Helper functions for product information extraction
def _extract_image_url(metadata: Dict[str, Any], content: str) -> Optional[str]:
    """Extract product image URL from metadata or content"""
    # Check metadata first
    if metadata:
        for key in ['image_url', 'image', 'thumbnail', 'picture']:
            if key in metadata and metadata[key]:
                return str(metadata[key])

    # Simple regex to find image URLs in content
    import re
    img_patterns = [
        r'<img[^>]+src=["\']([^"\']+)["\']',
        r'https?://[^\s]+\.(?:jpg|jpeg|png|gif|webp)',
    ]

    for pattern in img_patterns:
        matches = re.findall(pattern, content, re.IGNORECASE)
        if matches:
            return matches[0]

    return None


def _extract_price(metadata: Dict[str, Any], content: str) -> Optional[str]:
    """Extract product price from metadata or content"""
    # Check metadata first
    if metadata:
        for key in ['price', 'cost', 'amount', 'value']:
            if key in metadata and metadata[key]:
                return str(metadata[key])

    # Simple regex to find price patterns in content
    import re
    price_patterns = [
        r'¥[\d,]+',
        r'￥[\d,]+',
        r'\d+円',
        r'価格[：:]\s*¥?[\d,]+',
    ]

    for pattern in price_patterns:
        matches = re.findall(pattern, content)
        if matches:
            return matches[0]

    return None


def _extract_rating(metadata: Dict[str, Any], content: str) -> Optional[float]:
    """Extract product rating from metadata or content"""
    # Check metadata first
    if metadata:
        for key in ['rating', 'score', 'stars']:
            if key in metadata and metadata[key]:
                try:
                    return float(metadata[key])
                except (ValueError, TypeError):
                    continue

    # Simple regex to find rating patterns in content
    import re
    rating_patterns = [
        r'評価[：:]\s*(\d+(?:\.\d+)?)',
        r'★(\d+(?:\.\d+)?)',
        r'(\d+(?:\.\d+)?)/5',
        r'(\d+(?:\.\d+)?)点',
    ]

    for pattern in rating_patterns:
        matches = re.findall(pattern, content)
        if matches:
            try:
                return float(matches[0])
            except (ValueError, TypeError):
                continue

    return None


def _calculate_relevance_score(result, query: str) -> float:
    """Calculate relevance score based on query match"""
    if not query or not result.title:
        return 0.5

    query_lower = query.lower()
    title_lower = result.title.lower()
    description_lower = (result.description or "").lower()

    score = 0.0

    # Title exact match
    if query_lower in title_lower:
        score += 0.5

    # Description match
    if query_lower in description_lower:
        score += 0.3

    # Word overlap
    query_words = set(query_lower.split())
    title_words = set(title_lower.split())
    description_words = set(description_lower.split())

    title_overlap = len(query_words.intersection(title_words)) / max(len(query_words), 1)
    description_overlap = len(query_words.intersection(description_words)) / max(len(query_words), 1)

    score += title_overlap * 0.3
    score += description_overlap * 0.2

    return min(score, 1.0)


def _sort_products(products: List[ProductResult], sort_by: str) -> List[ProductResult]:
    """Sort products based on the specified criteria"""
    if sort_by == "title":
        return sorted(products, key=lambda p: p.title.lower())
    elif sort_by == "site":
        return sorted(products, key=lambda p: p.site_name.lower())
    elif sort_by == "price":
        # Sort by price (products with price first, then by price value)
        def price_key(p):
            if not p.price:
                return (1, 0)  # No price goes to end
            # Extract numeric value from price string
            import re
            numbers = re.findall(r'\d+', p.price.replace(',', ''))
            if numbers:
                return (0, int(numbers[0]))
            return (1, 0)
        return sorted(products, key=price_key)
    elif sort_by == "rating":
        return sorted(products, key=lambda p: p.rating or 0, reverse=True)
    else:  # relevance (default)
        return sorted(products, key=lambda p: p.relevance_score or 0, reverse=True)


@router.get("/search/history/{session_id}")
async def get_search_history(session_id: str):
    """Get search history for a session"""
    try:
        history = await database_service.get_search_history(session_id)
        return {"session_id": session_id, "history": history}
    except Exception as e:
        logger.error(f"Failed to get search history for session {session_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to retrieve search history: {str(e)}")


@router.post("/search/feedback")
async def submit_search_feedback(feedback: SearchFeedbackRequest):
    """Submit feedback for a search result"""
    try:
        success = await database_service.save_search_feedback(
            session_id=feedback.session_id,
            query=feedback.query,
            rating=feedback.rating,
            feedback_text=feedback.feedback_text,
            sources_helpful=feedback.sources_helpful
        )

        if success:
            return {"status": "success", "message": "Feedback saved successfully"}
        else:
            raise HTTPException(status_code=500, detail="Failed to save feedback")

    except Exception as e:
        logger.error(f"Failed to save search feedback: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to save feedback: {str(e)}")


@router.post("/search/rag", response_model=RAGSearchResponse)
async def rag_similarity_search(request: RAGSearchRequest):
    """RAG similarity search using vector embeddings"""
    start_time = time.time()

    try:
        logger.info(f"RAG similarity search for query: '{request.query}'")

        # Perform similarity search using vector embedding service
        results = await vector_embedding_service.similarity_search(
            query=request.query,
            limit=request.max_results,
            filters=request.filters
        )

        # Convert results to response format
        rag_results = []
        for result in results:
            rag_result = RAGSearchResult(
                content=result["content"],
                similarity_score=result["similarity_score"],
                combined_score=result.get("combined_score"),
                metadata=result["metadata"] if request.include_metadata else {},
                source_type=result["metadata"].get("source_type", "unknown"),
                title=result["metadata"].get("title", "Untitled"),
                url=result["metadata"].get("url"),
                indexed_at=result["metadata"].get("indexed_at"),
                confidence_score=result["metadata"].get("confidence_score"),
                language=result["metadata"].get("language")
            )
            rag_results.append(rag_result)

        processing_time = time.time() - start_time

        response = RAGSearchResponse(
            status="success",
            message=f"Found {len(rag_results)} relevant documents",
            query=request.query,
            results=rag_results,
            total_results=len(rag_results),
            filters_applied=request.filters,
            processing_time=processing_time
        )

        logger.info(f"RAG search completed in {processing_time:.2f}s, found {len(rag_results)} results")
        return response

    except Exception as e:
        logger.error(f"RAG similarity search failed for query '{request.query}': {str(e)}")
        raise HTTPException(status_code=500, detail=f"RAG search failed: {str(e)}")


@router.get("/search/rag/stats")
async def get_rag_database_stats():
    """Get statistics about the RAG vector database"""
    try:
        stats = await vector_embedding_service.get_database_stats()
        return {
            "status": "success",
            "stats": stats
        }
    except Exception as e:
        logger.error(f"Failed to get RAG database stats: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to get database stats: {str(e)}")
"""
Site-Specific Search Agent for InfoSeeker
Handles targeted search using Jina AI for specific websites
"""

import asyncio
import logging
from datetime import datetime
from typing import Dict, List, Any, Optional

from agno.agent import Agent
from agno.models.openai import OpenAIChat
from agno.storage.redis import RedisStorage

from app.core.config import settings
from app.services.jina_ai_client import jina_ai_client, JinaSearchResponse
from app.services.site_config_service import site_config_service
from app.services.database_service import database_service
from app.services.sse_manager import progress_manager

logger = logging.getLogger(__name__)


def create_site_specific_search_agent(session_id: str = None) -> Agent:
    """Create a site-specific search agent with Jina AI integration"""
    
    # Create Redis storage for agent coordination
    # Parse Redis URL to get connection details
    redis_parts = settings.redis_url.replace("redis://", "").split("/")
    host_port = redis_parts[0].split(":")
    host = host_port[0]
    port = int(host_port[1]) if len(host_port) > 1 else 6379
    db = int(redis_parts[1]) if len(redis_parts) > 1 else 0

    storage = RedisStorage(
        prefix=f"infoseeker_site_specific_{session_id}" if session_id else "infoseeker_site_specific",
        host=host,
        port=port,
        db=db
    )
    
    agent = Agent(
        name="Site-Specific Search Specialist",
        model=OpenAIChat(
            id="gpt-4o",
            api_key=settings.openai_api_key
        ),
        description="Specialist agent for targeted website search using Jina AI",
        instructions=[
            "You are a Site-Specific Search Specialist for InfoSeeker.",
            "Your role is to search specific websites using Jina AI for targeted, high-quality results.",
            "You specialize in searching Japanese e-commerce and food websites.",
            "Focus on finding relevant, current information from the target sites.",
            "Always provide structured, accurate information with proper source attribution.",
            "IMPORTANT: Always respond in the same language as the user's query.",
            "If you receive a language instruction at the beginning of the message, follow it strictly.",
            "Maintain the same language throughout your entire response.",
            "Provide detailed, contextual information from the specific sites searched."
        ],
        storage=storage,
        show_tool_calls=True,
        markdown=True
    )
    
    # Add the site-specific search functionality
    agent.session_id = session_id
    agent.search_and_process = lambda query, target_sites=None: _search_and_process(agent, query, target_sites)
    
    return agent


async def _search_and_process(agent: Agent, query: str, target_sites: Optional[List[str]] = None) -> Dict[str, Any]:
    """Enhanced search method for site-specific search with detailed logging"""
    search_start_time = datetime.now()
    session_id = getattr(agent, 'session_id', None)
    
    try:
        logger.info(f"Site-Specific Search Agent starting search for query: {query[:100]}...")
        
        # Broadcast detailed progress
        if session_id:
            await progress_manager.broadcast_progress(
                session_id,
                {
                    "agent": agent.name,
                    "status": "started",
                    "message": f"Analyzing query for site-specific search: {query[:50]}...",
                    "details": {
                        "query_length": len(query),
                        "search_engine": "Jina AI",
                        "target_sites": target_sites or "auto-detect"
                    }
                }
            )
        
        # Determine target sites
        if not target_sites:
            target_sites = await site_config_service.detect_target_sites(query)
            logger.info(f"Auto-detected target sites: {target_sites}")
        
        if not target_sites:
            logger.warning("No target sites detected for query")
            return {
                "success": False,
                "results": [],
                "message": "No suitable target sites found for this query",
                "search_time": 0,
                "sites_searched": []
            }
        
        # Update progress with detected sites
        if session_id:
            await progress_manager.broadcast_progress(
                session_id,
                {
                    "agent": agent.name,
                    "status": "processing",
                    "message": f"Searching {len(target_sites)} target sites...",
                    "details": {
                        "target_sites": target_sites,
                        "sites_count": len(target_sites)
                    }
                }
            )
        
        # Perform site-specific searches
        search_responses = await jina_ai_client.search_multiple_sites(
            query=query,
            site_keys=target_sites,
            max_results_per_site=settings.site_specific_max_results
        )
        
        search_time = (datetime.now() - search_start_time).total_seconds()
        logger.info(f"Site-specific search completed in {search_time:.2f}s")
        
        # Process and store results
        all_results = []
        total_tokens_used = 0
        successful_sites = []
        failed_sites = []
        
        for site_key, response in search_responses.items():
            if response.success:
                successful_sites.append(site_key)
                total_tokens_used += response.total_tokens_used
                
                # Store results in database
                for result in response.results:
                    await _store_search_result(session_id, site_key, query, result, response.response_time_ms)
                    all_results.append({
                        "site": site_key,
                        "title": result.title,
                        "url": result.url,
                        "description": result.description,
                        "content": result.content[:500] + "..." if len(result.content) > 500 else result.content,
                        "metadata": result.metadata
                    })
            else:
                failed_sites.append(site_key)
                logger.error(f"Search failed for {site_key}: {response.error_message}")
        
        # Log performance metrics
        await _log_performance_metrics(
            session_id=session_id,
            query=query,
            successful_sites=successful_sites,
            failed_sites=failed_sites,
            response_time_ms=int(search_time * 1000),
            results_count=len(all_results),
            tokens_used=total_tokens_used
        )
        
        # Update progress with results
        if session_id:
            await progress_manager.broadcast_progress(
                session_id,
                {
                    "agent": agent.name,
                    "status": "completed",
                    "message": f"Found {len(all_results)} results from {len(successful_sites)} sites",
                    "details": {
                        "results_count": len(all_results),
                        "successful_sites": successful_sites,
                        "failed_sites": failed_sites,
                        "total_tokens": total_tokens_used,
                        "search_time_ms": int(search_time * 1000)
                    }
                }
            )
        
        # Generate agent response using the found results
        if all_results:
            logger.info(f"Site-specific search found {len(all_results)} results from {len(successful_sites)} sites")
            
            # Create context for the agent
            results_context = _format_results_for_agent(all_results, query)
            
            # Run the agent to process and synthesize the results
            agent_response = await agent.arun(
                f"Based on the site-specific search results below, provide a comprehensive answer to the query: '{query}'\n\n"
                f"Search Results:\n{results_context}\n\n"
                f"Please synthesize this information into a helpful, accurate response that addresses the user's query. "
                f"Include specific details from the sites and provide proper attribution."
            )
            
            return {
                "success": True,
                "results": all_results,
                "agent_response": agent_response.content if hasattr(agent_response, 'content') else str(agent_response),
                "search_time": search_time,
                "sites_searched": successful_sites,
                "sites_failed": failed_sites,
                "total_tokens_used": total_tokens_used
            }
        else:
            logger.warning("No results found from site-specific search")
            return {
                "success": False,
                "results": [],
                "message": "No results found from the target sites",
                "search_time": search_time,
                "sites_searched": successful_sites,
                "sites_failed": failed_sites
            }
    
    except Exception as e:
        search_time = (datetime.now() - search_start_time).total_seconds()
        logger.error(f"Site-specific search error: {e}")
        
        if session_id:
            await progress_manager.broadcast_progress(
                session_id,
                {
                    "agent": agent.name,
                    "status": "error",
                    "message": f"Site-specific search failed: {str(e)}",
                    "details": {"error": str(e)}
                }
            )
        
        return {
            "success": False,
            "results": [],
            "error": str(e),
            "search_time": search_time,
            "sites_searched": [],
            "sites_failed": target_sites or []
        }


def _format_results_for_agent(results: List[Dict[str, Any]], query: str) -> str:
    """Format search results for agent processing"""
    formatted_results = []
    
    for i, result in enumerate(results, 1):
        formatted_result = f"""
Result {i} (from {result['site']}):
Title: {result['title']}
URL: {result['url']}
Description: {result['description']}
Content: {result['content']}
---
"""
        formatted_results.append(formatted_result)
    
    return "\n".join(formatted_results)


async def _store_search_result(session_id: str, site_key: str, query: str, result, response_time_ms: int):
    """Store search result in database"""
    try:
        store_query = """
        INSERT INTO site_search_results 
        (session_id, site_key, query, title, url, description, content, metadata, tokens_used, response_time_ms)
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
        """
        
        await database_service.execute_query(
            store_query,
            session_id,
            site_key,
            query,
            result.title,
            result.url,
            result.description,
            result.content,
            result.metadata,
            result.tokens_used,
            response_time_ms
        )
    except Exception as e:
        logger.error(f"Error storing search result: {e}")


async def _log_performance_metrics(session_id: str, query: str, successful_sites: List[str], 
                                 failed_sites: List[str], response_time_ms: int, 
                                 results_count: int, tokens_used: int):
    """Log performance metrics for monitoring"""
    try:
        # Log metrics for successful sites
        for site_key in successful_sites:
            metrics_query = """
            INSERT INTO search_performance_metrics 
            (session_id, search_type, site_key, query, response_time_ms, results_count, tokens_used, success)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
            """
            
            await database_service.execute_query(
                metrics_query,
                session_id,
                "site_specific",
                site_key,
                query,
                response_time_ms,
                results_count,
                tokens_used,
                True
            )
        
        # Log metrics for failed sites
        for site_key in failed_sites:
            await database_service.execute_query(
                metrics_query,
                session_id,
                "site_specific",
                site_key,
                query,
                response_time_ms,
                0,
                0,
                False
            )
    
    except Exception as e:
        logger.error(f"Error logging performance metrics: {e}")

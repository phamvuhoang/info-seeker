"""
Jina AI Client for Site-Specific Search
Handles integration with Jina AI API for targeted website search
"""

import asyncio
import aiohttp
import json
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime
from dataclasses import dataclass

from app.core.config import settings
from app.services.site_config_service import site_config_service, SiteConfig

logger = logging.getLogger(__name__)


@dataclass
class JinaSearchResult:
    """Structured result from Jina AI search"""
    title: str
    url: str
    description: str
    content: str
    metadata: Dict[str, Any]
    tokens_used: int
    site_key: str


@dataclass
class JinaSearchResponse:
    """Complete response from Jina AI search"""
    results: List[JinaSearchResult]
    total_tokens_used: int
    response_time_ms: int
    success: bool
    error_message: Optional[str] = None


class JinaAIClient:
    """Client for interacting with Jina AI API for site-specific search"""
    
    def __init__(self):
        self.base_url = settings.jina_base_url
        self.api_key = settings.jina_api_key
        self.timeout = settings.jina_timeout
        self.max_tokens_per_request = settings.jina_max_tokens_per_request
        self.rate_limit_per_minute = settings.jina_rate_limit_per_minute
        
        # Rate limiting tracking
        self._request_timestamps: List[datetime] = []
        self._rate_limit_lock = asyncio.Lock()
    
    async def search_site(self, 
                         query: str, 
                         site_key: str,
                         max_results: Optional[int] = None) -> JinaSearchResponse:
        """
        Perform site-specific search using Jina AI
        
        Args:
            query: Search query
            site_key: Key identifying the target site
            max_results: Maximum number of results (uses site config if not provided)
            
        Returns:
            JinaSearchResponse with results and metadata
        """
        start_time = datetime.now()
        
        try:
            # Get site configuration
            site_config = await site_config_service.get_site_config(site_key)
            if not site_config:
                return JinaSearchResponse(
                    results=[],
                    total_tokens_used=0,
                    response_time_ms=0,
                    success=False,
                    error_message=f"Site configuration not found for {site_key}"
                )
            
            if not site_config.is_active:
                return JinaSearchResponse(
                    results=[],
                    total_tokens_used=0,
                    response_time_ms=0,
                    success=False,
                    error_message=f"Site {site_key} is not active"
                )
            
            # Check rate limiting
            await self._check_rate_limit()
            
            # Prepare request
            request_data = {
                "q": query,
                "gl": site_config.country,
                "hl": site_config.language
            }
            
            headers = {
                "Accept": "application/json",
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
                "X-Engine": "direct",
                "X-Site": site_config.site_url
            }
            
            # Make API request
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=self.timeout)) as session:
                async with session.post(
                    self.base_url,
                    json=request_data,
                    headers=headers
                ) as response:
                    
                    response_time_ms = int((datetime.now() - start_time).total_seconds() * 1000)
                    
                    if response.status == 200:
                        response_data = await response.json()
                        return await self._parse_response(response_data, site_key, response_time_ms)
                    else:
                        error_text = await response.text()
                        logger.error(f"Jina AI API error for {site_key}: {response.status} - {error_text}")
                        
                        return JinaSearchResponse(
                            results=[],
                            total_tokens_used=0,
                            response_time_ms=response_time_ms,
                            success=False,
                            error_message=f"API error: {response.status} - {error_text}"
                        )
        
        except asyncio.TimeoutError:
            response_time_ms = int((datetime.now() - start_time).total_seconds() * 1000)
            logger.error(f"Jina AI API timeout for {site_key}")
            return JinaSearchResponse(
                results=[],
                total_tokens_used=0,
                response_time_ms=response_time_ms,
                success=False,
                error_message="Request timeout"
            )
        
        except Exception as e:
            response_time_ms = int((datetime.now() - start_time).total_seconds() * 1000)
            logger.error(f"Jina AI API error for {site_key}: {e}")
            return JinaSearchResponse(
                results=[],
                total_tokens_used=0,
                response_time_ms=response_time_ms,
                success=False,
                error_message=str(e)
            )
    
    async def search_multiple_sites(self, 
                                   query: str, 
                                   site_keys: List[str],
                                   max_results_per_site: Optional[int] = None) -> Dict[str, JinaSearchResponse]:
        """
        Search multiple sites concurrently
        
        Args:
            query: Search query
            site_keys: List of site keys to search
            max_results_per_site: Maximum results per site
            
        Returns:
            Dictionary mapping site_key to JinaSearchResponse
        """
        if not site_keys:
            return {}
        
        # Create concurrent search tasks
        tasks = []
        for site_key in site_keys:
            task = self.search_site(query, site_key, max_results_per_site)
            tasks.append((site_key, task))
        
        # Execute searches concurrently
        results = {}
        for site_key, task in tasks:
            try:
                response = await task
                results[site_key] = response
            except Exception as e:
                logger.error(f"Error searching site {site_key}: {e}")
                results[site_key] = JinaSearchResponse(
                    results=[],
                    total_tokens_used=0,
                    response_time_ms=0,
                    success=False,
                    error_message=str(e)
                )
        
        return results
    
    async def _parse_response(self, 
                             response_data: Dict[str, Any], 
                             site_key: str, 
                             response_time_ms: int) -> JinaSearchResponse:
        """Parse Jina AI API response into structured format"""
        try:
            if response_data.get("code") != 200:
                return JinaSearchResponse(
                    results=[],
                    total_tokens_used=0,
                    response_time_ms=response_time_ms,
                    success=False,
                    error_message=f"API returned code {response_data.get('code')}"
                )
            
            data_items = response_data.get("data", [])
            results = []
            total_tokens = 0
            
            for item in data_items:
                # Extract tokens used from usage info
                tokens_used = item.get("usage", {}).get("tokens", 0)
                total_tokens += tokens_used
                
                result = JinaSearchResult(
                    title=item.get("title", ""),
                    url=item.get("url", ""),
                    description=item.get("description", ""),
                    content=item.get("content", ""),
                    metadata=item.get("metadata", {}),
                    tokens_used=tokens_used,
                    site_key=site_key
                )
                results.append(result)
            
            return JinaSearchResponse(
                results=results,
                total_tokens_used=total_tokens,
                response_time_ms=response_time_ms,
                success=True
            )
        
        except Exception as e:
            logger.error(f"Error parsing Jina AI response for {site_key}: {e}")
            return JinaSearchResponse(
                results=[],
                total_tokens_used=0,
                response_time_ms=response_time_ms,
                success=False,
                error_message=f"Response parsing error: {str(e)}"
            )
    
    async def _check_rate_limit(self):
        """Check and enforce rate limiting"""
        async with self._rate_limit_lock:
            now = datetime.now()
            
            # Remove timestamps older than 1 minute
            cutoff_time = now.timestamp() - 60
            self._request_timestamps = [
                ts for ts in self._request_timestamps 
                if ts.timestamp() > cutoff_time
            ]
            
            # Check if we're at the rate limit
            if len(self._request_timestamps) >= self.rate_limit_per_minute:
                # Calculate how long to wait
                oldest_request = min(self._request_timestamps)
                wait_time = 60 - (now - oldest_request).total_seconds()
                
                if wait_time > 0:
                    logger.warning(f"Rate limit reached, waiting {wait_time:.2f} seconds")
                    await asyncio.sleep(wait_time)
            
            # Add current request timestamp
            self._request_timestamps.append(now)
    
    async def health_check(self) -> Dict[str, Any]:
        """Perform health check on Jina AI service"""
        try:
            # Simple test query to check service availability
            test_response = await self.search_site("test", "otoriyose.net")
            
            return {
                "service": "jina_ai",
                "status": "healthy" if test_response.success or "timeout" in (test_response.error_message or "") else "unhealthy",
                "response_time_ms": test_response.response_time_ms,
                "error": test_response.error_message,
                "timestamp": datetime.now().isoformat()
            }
        
        except Exception as e:
            return {
                "service": "jina_ai",
                "status": "unhealthy",
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }


# Global instance
jina_ai_client = JinaAIClient()

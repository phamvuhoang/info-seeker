"""
Rate Limiting Service for API Endpoints
Implements rate limiting for Jina AI and other external services
"""

import asyncio
import time
import logging
from typing import Dict, Optional, Any
from datetime import datetime, timedelta
from collections import defaultdict, deque

from app.core.config import settings

logger = logging.getLogger(__name__)


class RateLimiter:
    """Rate limiter with sliding window algorithm"""
    
    def __init__(self, max_requests: int, window_seconds: int):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.requests: Dict[str, deque] = defaultdict(deque)
        self._lock = asyncio.Lock()
    
    async def is_allowed(self, key: str) -> bool:
        """Check if request is allowed for the given key"""
        async with self._lock:
            now = time.time()
            window_start = now - self.window_seconds
            
            # Remove old requests outside the window
            while self.requests[key] and self.requests[key][0] < window_start:
                self.requests[key].popleft()
            
            # Check if we're within the limit
            if len(self.requests[key]) < self.max_requests:
                self.requests[key].append(now)
                return True
            
            return False
    
    async def get_reset_time(self, key: str) -> Optional[float]:
        """Get the time when the rate limit will reset for the key"""
        async with self._lock:
            if not self.requests[key]:
                return None
            
            oldest_request = self.requests[key][0]
            return oldest_request + self.window_seconds
    
    async def get_remaining_requests(self, key: str) -> int:
        """Get the number of remaining requests for the key"""
        async with self._lock:
            now = time.time()
            window_start = now - self.window_seconds
            
            # Remove old requests outside the window
            while self.requests[key] and self.requests[key][0] < window_start:
                self.requests[key].popleft()
            
            return max(0, self.max_requests - len(self.requests[key]))


class APIRateLimitManager:
    """Manages rate limiting for different API services"""
    
    def __init__(self):
        # Jina AI rate limiter
        self.jina_limiter = RateLimiter(
            max_requests=settings.jina_rate_limit_per_minute,
            window_seconds=60
        )
        
        # General API rate limiter (per IP)
        self.api_limiter = RateLimiter(
            max_requests=100,  # 100 requests per minute per IP
            window_seconds=60
        )
        
        # Site-specific search rate limiter
        self.site_search_limiter = RateLimiter(
            max_requests=30,  # 30 site-specific searches per minute
            window_seconds=60
        )
    
    async def check_jina_rate_limit(self) -> Dict[str, Any]:
        """Check Jina AI rate limit"""
        key = "jina_api"
        allowed = await self.jina_limiter.is_allowed(key)
        
        if not allowed:
            reset_time = await self.jina_limiter.get_reset_time(key)
            wait_time = reset_time - time.time() if reset_time else 60
            
            return {
                "allowed": False,
                "wait_time": wait_time,
                "message": f"Jina AI rate limit exceeded. Try again in {wait_time:.1f} seconds."
            }
        
        remaining = await self.jina_limiter.get_remaining_requests(key)
        return {
            "allowed": True,
            "remaining_requests": remaining,
            "message": "Request allowed"
        }
    
    async def check_api_rate_limit(self, client_ip: str) -> Dict[str, Any]:
        """Check general API rate limit for client IP"""
        allowed = await self.api_limiter.is_allowed(client_ip)
        
        if not allowed:
            reset_time = await self.api_limiter.get_reset_time(client_ip)
            wait_time = reset_time - time.time() if reset_time else 60
            
            return {
                "allowed": False,
                "wait_time": wait_time,
                "message": f"API rate limit exceeded for IP {client_ip}. Try again in {wait_time:.1f} seconds."
            }
        
        remaining = await self.api_limiter.get_remaining_requests(client_ip)
        return {
            "allowed": True,
            "remaining_requests": remaining,
            "message": "Request allowed"
        }
    
    async def check_site_search_rate_limit(self, session_id: str) -> Dict[str, Any]:
        """Check site-specific search rate limit for session"""
        allowed = await self.site_search_limiter.is_allowed(session_id)
        
        if not allowed:
            reset_time = await self.site_search_limiter.get_reset_time(session_id)
            wait_time = reset_time - time.time() if reset_time else 60
            
            return {
                "allowed": False,
                "wait_time": wait_time,
                "message": f"Site-specific search rate limit exceeded. Try again in {wait_time:.1f} seconds."
            }
        
        remaining = await self.site_search_limiter.get_remaining_requests(session_id)
        return {
            "allowed": True,
            "remaining_requests": remaining,
            "message": "Request allowed"
        }


class ErrorHandler:
    """Centralized error handling for API endpoints"""
    
    @staticmethod
    def handle_jina_api_error(error: Exception) -> Dict[str, Any]:
        """Handle Jina AI API errors"""
        error_str = str(error).lower()
        
        if "timeout" in error_str:
            return {
                "error_type": "timeout",
                "message": "Jina AI service timeout. Please try again.",
                "retry_after": 30,
                "user_message": "The search service is temporarily slow. Please try again in a moment."
            }
        elif "rate limit" in error_str or "429" in error_str:
            return {
                "error_type": "rate_limit",
                "message": "Jina AI rate limit exceeded.",
                "retry_after": 60,
                "user_message": "Too many requests. Please wait a minute before trying again."
            }
        elif "401" in error_str or "unauthorized" in error_str:
            return {
                "error_type": "auth_error",
                "message": "Jina AI authentication failed.",
                "retry_after": None,
                "user_message": "Search service authentication error. Please contact support."
            }
        elif "400" in error_str or "bad request" in error_str:
            return {
                "error_type": "bad_request",
                "message": "Invalid request to Jina AI.",
                "retry_after": None,
                "user_message": "Invalid search request. Please check your query and try again."
            }
        else:
            return {
                "error_type": "unknown",
                "message": f"Jina AI error: {str(error)}",
                "retry_after": 30,
                "user_message": "Search service error. Please try again later."
            }
    
    @staticmethod
    def handle_site_config_error(error: Exception) -> Dict[str, Any]:
        """Handle site configuration errors"""
        return {
            "error_type": "config_error",
            "message": f"Site configuration error: {str(error)}",
            "retry_after": None,
            "user_message": "Site configuration error. Some search features may be unavailable."
        }
    
    @staticmethod
    def handle_database_error(error: Exception) -> Dict[str, Any]:
        """Handle database errors"""
        return {
            "error_type": "database_error",
            "message": f"Database error: {str(error)}",
            "retry_after": 10,
            "user_message": "Database temporarily unavailable. Please try again shortly."
        }
    
    @staticmethod
    def handle_generic_error(error: Exception) -> Dict[str, Any]:
        """Handle generic errors"""
        return {
            "error_type": "internal_error",
            "message": f"Internal error: {str(error)}",
            "retry_after": 30,
            "user_message": "An unexpected error occurred. Please try again later."
        }


# Global instances
rate_limit_manager = APIRateLimitManager()
error_handler = ErrorHandler()

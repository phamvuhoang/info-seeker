import asyncio
import aiohttp
import logging
from typing import Optional
from contextlib import asynccontextmanager

logger = logging.getLogger(__name__)


class ConnectionManager:
    """Manages HTTP connections to prevent resource leaks"""
    
    def __init__(self):
        self._session: Optional[aiohttp.ClientSession] = None
        self._lock = asyncio.Lock()
    
    async def get_session(self) -> aiohttp.ClientSession:
        """Get or create HTTP session with proper connection management"""
        if self._session is None or self._session.closed:
            async with self._lock:
                if self._session is None or self._session.closed:
                    # Configure connection limits and timeouts
                    connector = aiohttp.TCPConnector(
                        limit=100,  # Total connection pool size
                        limit_per_host=30,  # Per-host connection limit
                        ttl_dns_cache=300,  # DNS cache TTL
                        use_dns_cache=True,
                        keepalive_timeout=30,
                        enable_cleanup_closed=True
                    )
                    
                    timeout = aiohttp.ClientTimeout(
                        total=30,  # Total timeout
                        connect=10,  # Connection timeout
                        sock_read=10  # Socket read timeout
                    )
                    
                    self._session = aiohttp.ClientSession(
                        connector=connector,
                        timeout=timeout,
                        headers={
                            'User-Agent': 'InfoSeeker/1.0'
                        }
                    )
                    logger.info("Created new HTTP session with connection pooling")
        
        return self._session
    
    @asynccontextmanager
    async def request(self, method: str, url: str, **kwargs):
        """Context manager for HTTP requests with proper resource cleanup"""
        session = await self.get_session()
        try:
            async with session.request(method, url, **kwargs) as response:
                yield response
        except Exception as e:
            logger.error(f"HTTP request failed: {e}")
            raise
    
    async def close(self):
        """Close the HTTP session and cleanup resources"""
        if self._session and not self._session.closed:
            await self._session.close()
            logger.info("HTTP session closed")
    
    async def __aenter__(self):
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()


# Global connection manager instance
connection_manager = ConnectionManager()


async def cleanup_connections():
    """Cleanup function to be called on application shutdown"""
    await connection_manager.close()

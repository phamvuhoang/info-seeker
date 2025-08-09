"""
Site Configuration Service for Site-Specific Search
Manages configuration for target sites in Jina AI integration
"""

from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from datetime import datetime
import logging
from app.services.database_service import database_service

logger = logging.getLogger(__name__)


@dataclass
class SiteConfig:
    """Configuration for a site-specific search target"""
    site_key: str
    site_url: str
    site_name: str
    category: str
    language: str = "ja"
    country: str = "JP"
    max_results: int = 10
    timeout_seconds: int = 30
    is_active: bool = True


class SiteConfigService:
    """Service for managing site-specific search configurations"""
    
    def __init__(self):
        self._config_cache: Dict[str, SiteConfig] = {}
        self._cache_timestamp: Optional[datetime] = None
        self._cache_ttl_seconds = 300  # 5 minutes cache TTL
    
    async def get_active_sites(self) -> Dict[str, SiteConfig]:
        """Get all active site configurations"""
        await self._refresh_cache_if_needed()
        return {k: v for k, v in self._config_cache.items() if v.is_active}
    
    async def get_site_config(self, site_key: str) -> Optional[SiteConfig]:
        """Get configuration for a specific site"""
        await self._refresh_cache_if_needed()
        return self._config_cache.get(site_key)
    
    async def get_sites_by_category(self, category: str) -> List[SiteConfig]:
        """Get all active sites in a specific category"""
        active_sites = await self.get_active_sites()
        return [config for config in active_sites.values() if config.category == category]
    
    async def is_site_supported(self, site_key: str) -> bool:
        """Check if a site is supported and active"""
        config = await self.get_site_config(site_key)
        return config is not None and config.is_active
    
    async def get_supported_site_keys(self) -> List[str]:
        """Get list of all supported site keys"""
        active_sites = await self.get_active_sites()
        return list(active_sites.keys())
    
    async def detect_target_sites(self, query: str) -> List[str]:
        """
        Detect which sites might be relevant for a given query
        This is a simple implementation - can be enhanced with ML in the future
        """
        query_lower = query.lower()
        relevant_sites = []
        
        active_sites = await self.get_active_sites()
        
        # Simple keyword-based detection
        site_keywords = {
            'otoriyose.net': ['お取り寄せ', 'グルメ', '食品', '通販', 'おとりよせ'],
            'ippin.gnavi.co.jp': ['パン', 'ヤマザキ', '山崎製パン', 'bread', 'yamazaki'],
            'gurusuguri.com': ['ぐるすぐり', 'プレミアム', '高級食材', 'premium', 'gourmet']
        }
        
        for site_key, keywords in site_keywords.items():
            if site_key in active_sites:
                if any(keyword in query_lower for keyword in keywords):
                    relevant_sites.append(site_key)
        
        # If no specific sites detected, return all active sites for broad queries
        if not relevant_sites and len(query.strip()) > 0:
            # For food-related queries, include all food sites
            food_keywords = ['食べ物', '料理', '食品', 'food', '美味しい', 'おいしい', 'グルメ']
            if any(keyword in query_lower for keyword in food_keywords):
                relevant_sites = list(active_sites.keys())
        
        return relevant_sites
    
    async def add_site_config(self, config: SiteConfig) -> bool:
        """Add a new site configuration"""
        try:
            query = """
            INSERT INTO site_search_configs 
            (site_key, site_url, site_name, category, language, country, max_results, timeout_seconds, is_active)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
            ON CONFLICT (site_key) DO UPDATE SET
                site_url = EXCLUDED.site_url,
                site_name = EXCLUDED.site_name,
                category = EXCLUDED.category,
                language = EXCLUDED.language,
                country = EXCLUDED.country,
                max_results = EXCLUDED.max_results,
                timeout_seconds = EXCLUDED.timeout_seconds,
                is_active = EXCLUDED.is_active,
                updated_at = CURRENT_TIMESTAMP
            """
            
            await database_service.execute_query(
                query,
                config.site_key,
                config.site_url,
                config.site_name,
                config.category,
                config.language,
                config.country,
                config.max_results,
                config.timeout_seconds,
                config.is_active
            )
            
            # Clear cache to force refresh
            self._cache_timestamp = None
            logger.info(f"Added/updated site configuration for {config.site_key}")
            return True
            
        except Exception as e:
            logger.error(f"Error adding site configuration for {config.site_key}: {e}")
            return False
    
    async def update_site_status(self, site_key: str, is_active: bool) -> bool:
        """Update the active status of a site"""
        try:
            query = """
            UPDATE site_search_configs 
            SET is_active = $2, updated_at = CURRENT_TIMESTAMP
            WHERE site_key = $1
            """
            
            result = await database_service.execute_query(query, site_key, is_active)
            
            # Clear cache to force refresh
            self._cache_timestamp = None
            logger.info(f"Updated site {site_key} status to {'active' if is_active else 'inactive'}")
            return True
            
        except Exception as e:
            logger.error(f"Error updating site status for {site_key}: {e}")
            return False
    
    async def _refresh_cache_if_needed(self):
        """Refresh the configuration cache if needed"""
        now = datetime.now()
        
        if (self._cache_timestamp is None or 
            (now - self._cache_timestamp).total_seconds() > self._cache_ttl_seconds):
            
            await self._load_configurations()
    
    async def _load_configurations(self):
        """Load all site configurations from database"""
        try:
            query = """
            SELECT site_key, site_url, site_name, category, language, country, 
                   max_results, timeout_seconds, is_active
            FROM site_search_configs
            ORDER BY site_name
            """
            
            rows = await database_service.fetch_all(query)
            
            self._config_cache = {}
            for row in rows:
                config = SiteConfig(
                    site_key=row['site_key'],
                    site_url=row['site_url'],
                    site_name=row['site_name'],
                    category=row['category'],
                    language=row['language'],
                    country=row['country'],
                    max_results=row['max_results'],
                    timeout_seconds=row['timeout_seconds'],
                    is_active=row['is_active']
                )
                self._config_cache[config.site_key] = config
            
            self._cache_timestamp = datetime.now()
            logger.info(f"Loaded {len(self._config_cache)} site configurations")
            
        except Exception as e:
            logger.error(f"Error loading site configurations: {e}")
            # Keep existing cache if load fails
    
    async def get_site_statistics(self) -> Dict[str, Any]:
        """Get statistics about site configurations and usage"""
        try:
            # Get configuration stats
            config_query = """
            SELECT 
                COUNT(*) as total_sites,
                COUNT(*) FILTER (WHERE is_active = true) as active_sites,
                COUNT(*) FILTER (WHERE is_active = false) as inactive_sites
            FROM site_search_configs
            """
            
            config_stats = await database_service.fetch_one(config_query)
            
            # Get usage stats from the last 24 hours
            usage_query = """
            SELECT 
                site_key,
                COUNT(*) as search_count,
                AVG(response_time_ms) as avg_response_time,
                SUM(tokens_used) as total_tokens
            FROM search_performance_metrics 
            WHERE search_type = 'site_specific' 
                AND timestamp > NOW() - INTERVAL '24 hours'
            GROUP BY site_key
            ORDER BY search_count DESC
            """
            
            usage_stats = await database_service.fetch_all(usage_query)
            
            return {
                'configuration': dict(config_stats) if config_stats else {},
                'usage_24h': [dict(row) for row in usage_stats] if usage_stats else []
            }
            
        except Exception as e:
            logger.error(f"Error getting site statistics: {e}")
            return {'configuration': {}, 'usage_24h': []}


# Global instance
site_config_service = SiteConfigService()

import asyncio
import logging
import json
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone, timedelta
import asyncpg
from ..core.config import settings
from .base import BaseScraper

logger = logging.getLogger(__name__)


class ScrapingEngine:
    """Engine for managing and executing scraping tasks"""
    
    def __init__(self):
        self.connection_pool = None
        self.scrapers: Dict[str, BaseScraper] = {}
    
    async def get_connection(self):
        """Get database connection"""
        if not self.connection_pool:
            db_url = settings.database_url
            if db_url.startswith("postgresql+psycopg://"):
                db_url = db_url.replace("postgresql+psycopg://", "postgresql://")
            
            self.connection_pool = await asyncpg.create_pool(db_url, min_size=1, max_size=10)
        
        return self.connection_pool.acquire()
    
    def register_scraper(self, source_name: str, scraper_class: type):
        """Register a scraper class for a source"""
        self.scrapers[source_name] = scraper_class
        logger.info(f"Registered scraper for {source_name}")
    
    async def get_scraping_configs(self, active_only: bool = True) -> List[Dict[str, Any]]:
        """Get scraping configurations from database"""
        try:
            async with await self.get_connection() as conn:
                if active_only:
                    query = """
                        SELECT id, source_name, base_url, extraction_schema, 
                               scrape_interval_hours, last_scraped_at, created_at
                        FROM scraping_configs 
                        WHERE is_active = TRUE
                        ORDER BY source_name;
                    """
                else:
                    query = """
                        SELECT id, source_name, base_url, extraction_schema, 
                               scrape_interval_hours, last_scraped_at, created_at, is_active
                        FROM scraping_configs 
                        ORDER BY source_name;
                    """
                
                rows = await conn.fetch(query)
                
                configs = []
                for row in rows:
                    # Parse extraction_schema from JSONB to dict
                    extraction_schema = row['extraction_schema']
                    if isinstance(extraction_schema, str):
                        try:
                            extraction_schema = json.loads(extraction_schema)
                        except json.JSONDecodeError as e:
                            logger.error(f"Failed to parse extraction_schema for {row['source_name']}: {e}")
                            extraction_schema = {}
                    elif extraction_schema is None:
                        extraction_schema = {}

                    config = {
                        'id': row['id'],
                        'source_name': row['source_name'],
                        'base_url': row['base_url'],
                        'extraction_schema': extraction_schema,
                        'scrape_interval_hours': row['scrape_interval_hours'],
                        'last_scraped_at': row['last_scraped_at'],
                        'created_at': row['created_at']
                    }
                    if not active_only:
                        config['is_active'] = row['is_active']
                    configs.append(config)
                
                return configs
                
        except Exception as e:
            logger.error(f"Error getting scraping configs: {e}")
            return []
    
    async def update_last_scraped(self, source_name: str) -> bool:
        """Update last_scraped_at timestamp for a source"""
        try:
            async with await self.get_connection() as conn:
                query = """
                    UPDATE scraping_configs 
                    SET last_scraped_at = NOW() 
                    WHERE source_name = $1;
                """
                
                await conn.execute(query, source_name)
                logger.info(f"Updated last_scraped_at for {source_name}")
                return True
                
        except Exception as e:
            logger.error(f"Error updating last_scraped_at for {source_name}: {e}")
            return False
    
    async def get_sources_due_for_scraping(self) -> List[Dict[str, Any]]:
        """Get sources that are due for scraping based on their interval"""
        try:
            configs = await self.get_scraping_configs(active_only=True)
            due_sources = []
            
            current_time = datetime.now(timezone.utc)
            
            for config in configs:
                last_scraped = config['last_scraped_at']
                interval_hours = config['scrape_interval_hours']
                
                # If never scraped, it's due
                if not last_scraped:
                    due_sources.append(config)
                    continue
                
                # Convert to UTC if needed
                if last_scraped.tzinfo is None:
                    last_scraped = last_scraped.replace(tzinfo=timezone.utc)
                
                # Check if enough time has passed
                time_since_last = current_time - last_scraped
                if time_since_last >= timedelta(hours=interval_hours):
                    due_sources.append(config)
            
            logger.info(f"Found {len(due_sources)} sources due for scraping")
            return due_sources
            
        except Exception as e:
            logger.error(f"Error getting sources due for scraping: {e}")
            return []
    
    async def run_scraper(self, source_name: str, config: Dict[str, Any] = None) -> Dict[str, Any]:
        """Run scraper for a specific source"""
        try:
            # Get config if not provided
            if not config:
                configs = await self.get_scraping_configs(active_only=True)
                config = next((c for c in configs if c['source_name'] == source_name), None)
                
                if not config:
                    return {
                        'source_name': source_name,
                        'status': 'failed',
                        'error': f'No configuration found for source: {source_name}'
                    }
            
            # Check if scraper is registered
            if source_name not in self.scrapers:
                return {
                    'source_name': source_name,
                    'status': 'failed',
                    'error': f'No scraper registered for source: {source_name}'
                }
            
            logger.info(f"Starting scraper for {source_name}")
            
            # Create scraper instance
            scraper_class = self.scrapers[source_name]
            scraper = scraper_class(config)
            
            # Run scraper
            result = await scraper.run()
            
            # Update last scraped timestamp if successful
            if result.get('status') == 'completed':
                await self.update_last_scraped(source_name)
            
            return result
            
        except Exception as e:
            error_msg = f"Error running scraper for {source_name}: {e}"
            logger.error(error_msg)
            return {
                'source_name': source_name,
                'status': 'failed',
                'error': error_msg
            }
    
    async def run_scheduled_scraping(self) -> Dict[str, Any]:
        """Run scraping for all sources that are due"""
        start_time = datetime.now(timezone.utc)
        results = {
            'started_at': start_time.isoformat(),
            'sources_processed': 0,
            'sources_successful': 0,
            'sources_failed': 0,
            'results': []
        }
        
        try:
            logger.info("Starting scheduled scraping run")
            
            # Get sources due for scraping
            due_sources = await self.get_sources_due_for_scraping()
            
            if not due_sources:
                logger.info("No sources due for scraping")
                results['status'] = 'completed'
                return results
            
            # Run scrapers for due sources
            for config in due_sources:
                source_name = config['source_name']
                
                try:
                    logger.info(f"Running scheduled scraping for {source_name}")
                    result = await self.run_scraper(source_name, config)
                    
                    results['results'].append(result)
                    results['sources_processed'] += 1
                    
                    if result.get('status') == 'completed':
                        results['sources_successful'] += 1
                    else:
                        results['sources_failed'] += 1
                    
                    # Add delay between sources to avoid overwhelming servers
                    await asyncio.sleep(5)
                    
                except Exception as e:
                    error_msg = f"Error in scheduled scraping for {source_name}: {e}"
                    logger.error(error_msg)
                    results['results'].append({
                        'source_name': source_name,
                        'status': 'failed',
                        'error': error_msg
                    })
                    results['sources_processed'] += 1
                    results['sources_failed'] += 1
            
            results['status'] = 'completed'
            
        except Exception as e:
            error_msg = f"Error in scheduled scraping run: {e}"
            logger.error(error_msg)
            results['status'] = 'failed'
            results['error'] = error_msg
        
        finally:
            end_time = datetime.now(timezone.utc)
            results['completed_at'] = end_time.isoformat()
            results['duration_seconds'] = (end_time - start_time).total_seconds()
            
            logger.info(f"Scheduled scraping completed: {results['sources_successful']}/{results['sources_processed']} successful")
        
        return results
    
    async def cleanup(self):
        """Clean up resources"""
        try:
            if self.connection_pool:
                await self.connection_pool.close()
                logger.info("Scraping engine connection pool closed")
        except Exception as e:
            logger.error(f"Error cleaning up scraping engine: {e}")


# Global instance
scraping_engine = ScrapingEngine()

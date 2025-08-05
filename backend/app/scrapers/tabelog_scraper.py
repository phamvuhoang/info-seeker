import asyncio
import logging
import re
from typing import Dict, Any, List, Optional
from urllib.parse import urljoin, urlparse, parse_qs
import asyncpg
from datetime import datetime, timezone
from .base import BaseScraper
from ..core.config import settings

logger = logging.getLogger(__name__)


class TabelogScraper(BaseScraper):
    """Scraper for Tabelog restaurant data"""
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.connection_pool = None
        
        # Tabelog search URLs for different areas
        self.search_urls = [
            # Tokyo restaurants
            "https://tabelog.com/tokyo/",
            # Osaka restaurants
            "https://tabelog.com/osaka/",
            # Kyoto restaurants
            "https://tabelog.com/kyoto/",
        ]
    
    async def get_connection(self):
        """Get database connection"""
        if not self.connection_pool:
            db_url = settings.database_url
            if db_url.startswith("postgresql+psycopg://"):
                db_url = db_url.replace("postgresql+psycopg://", "postgresql://")
            
            self.connection_pool = await asyncpg.create_pool(db_url, min_size=1, max_size=10)
        
        return self.connection_pool.acquire()
    
    async def scrape_urls(self) -> List[str]:
        """Get list of restaurant URLs to scrape from search pages"""
        restaurant_urls = []
        
        try:
            for search_url in self.search_urls:
                logger.info(f"Scraping search page: {search_url}")
                
                # Navigate to search page
                success = await self.navigate_with_retry(search_url)
                if not success:
                    logger.warning(f"Failed to navigate to search page: {search_url}")
                    continue
                
                # Wait for search results to load
                try:
                    await self.page.wait_for_selector('.list-rst, .js-rst-cassette, .list-restaurant', timeout=15000)
                except:
                    logger.warning(f"No restaurant items found on search page: {search_url}")
                    continue
                
                # Extract restaurant URLs from search results
                page_urls = await self.extract_restaurant_urls_from_search()
                restaurant_urls.extend(page_urls)
                
                logger.info(f"Found {len(page_urls)} restaurant URLs on search page")
                
                # Add delay between search pages
                await asyncio.sleep(2)
        
        except Exception as e:
            logger.error(f"Error scraping restaurant URLs: {e}")
        
        # Remove duplicates and limit to reasonable number
        unique_urls = list(set(restaurant_urls))[:50]  # Limit to 50 restaurants for testing
        logger.info(f"Total unique restaurant URLs found: {len(unique_urls)}")
        
        return unique_urls
    
    async def extract_restaurant_urls_from_search(self) -> List[str]:
        """Extract restaurant URLs from search results page"""
        urls = []
        
        try:
            # Wait a bit for dynamic content
            await asyncio.sleep(2)
            
            # Get all restaurant links
            restaurant_links = await self.page.query_selector_all('.list-rst__rst-name-target, .js-rst-cassette-wrap a, .list-restaurant a')
            
            for link in restaurant_links:
                try:
                    href = await link.get_attribute('href')
                    if href:
                        # Convert relative URLs to absolute
                        if href.startswith('/'):
                            full_url = urljoin(self.base_url, href)
                        else:
                            full_url = href
                        
                        # Only include restaurant detail pages, exclude reviewer pages
                        if ('tabelog.com' in full_url and
                            '/rvwr/' not in full_url and
                            '/dtlrvwlst/' not in full_url and
                            len(full_url.split('/')) >= 6):  # Proper restaurant URLs have more path segments
                            urls.append(full_url)
                            
                except Exception as e:
                    logger.debug(f"Error extracting URL from link: {e}")
                    continue
        
        except Exception as e:
            logger.error(f"Error extracting restaurant URLs from search page: {e}")
        
        return urls
    
    async def extract_data(self, url: str) -> Optional[Dict[str, Any]]:
        """Extract restaurant data from a single restaurant page"""
        try:
            logger.info(f"Extracting data from: {url}")
            
            # Navigate to restaurant page
            success = await self.navigate_with_retry(url)
            if not success:
                return None
            
            # Wait for page content to load
            try:
                await self.page.wait_for_selector('.display-name, h1.shop-name, .rdheader-subinfo__item', timeout=10000)
            except:
                logger.warning(f"Restaurant page content not loaded: {url}")
                return None
            
            # Extract restaurant data using the extraction schema
            data = await self.extract_restaurant_data()
            
            if not data or not data.get('name'):
                logger.warning(f"No valid data extracted from: {url}")
                return None
            
            # Add metadata
            data['url'] = url
            data['source_name'] = self.source_name
            data['source_item_id'] = self.extract_restaurant_id_from_url(url)
            
            # Generate content hash
            data['content_hash'] = self.generate_hash(data)
            
            logger.info(f"Successfully extracted data for: {data.get('name', 'Unknown')}")
            return data
            
        except Exception as e:
            logger.error(f"Error extracting data from {url}: {e}")
            return None
    
    async def extract_restaurant_data(self) -> Dict[str, Any]:
        """Extract restaurant data from current page using extraction schema"""
        data = {}

        try:
            # Extract name
            name_selectors = self.extraction_schema.get('name', '')
            name = await self.extract_text_safely(name_selectors)
            if name:
                data['name'] = name

            # Extract rating
            rating_selectors = self.extraction_schema.get('rating', '')
            rating_text = await self.extract_text_safely(rating_selectors)
            if rating_text:
                rating = self.clean_rating(rating_text)
                if rating:
                    data['rating'] = rating

            # Extract review count
            review_selectors = self.extraction_schema.get('review_count', '')
            review_text = await self.extract_text_safely(review_selectors)
            if review_text:
                review_count = self.clean_review_count(review_text)
                if review_count:
                    data['review_count'] = review_count

            # Extract cuisine type
            cuisine_selectors = self.extraction_schema.get('cuisine_type', '')
            cuisine = await self.extract_text_safely(cuisine_selectors)
            if cuisine:
                data['cuisine_type'] = cuisine

            # Extract price range
            price_selectors = self.extraction_schema.get('price_range', '')
            price_range = await self.extract_text_safely(price_selectors)
            if price_range:
                data['price_range'] = price_range

            # Extract address
            address_selectors = self.extraction_schema.get('address', '')
            address = await self.extract_text_safely(address_selectors)
            if address:
                data['address'] = address
                # Try to extract city from address
                city = self.extract_city_from_address(address)
                if city:
                    data['city'] = city

            # Extract image URL
            image_selectors = self.extraction_schema.get('image', '')
            image_url = await self.extract_attribute_safely(image_selectors, 'src')
            if image_url:
                # Convert relative URLs to absolute
                if image_url.startswith('/'):
                    image_url = urljoin(self.base_url, image_url)
                data['image_url'] = image_url
            
        except Exception as e:
            logger.error(f"Error extracting restaurant data: {e}")
        
        return data
    
    def extract_restaurant_id_from_url(self, url: str) -> str:
        """Extract restaurant ID from Tabelog URL"""
        try:
            # Tabelog URLs typically contain restaurant ID in the path
            # Example: https://tabelog.com/tokyo/A1301/A130101/13001234/
            
            # Try to extract from URL path
            path_match = re.search(r'/(\d+)/?$', url)
            if path_match:
                return path_match.group(1)
            
            # Try alternative pattern
            path_match = re.search(r'/A\d+/A\d+/(\d+)/', url)
            if path_match:
                return path_match.group(1)
            
            # Fallback: use a hash of the URL
            return str(hash(url))
            
        except Exception as e:
            logger.debug(f"Error extracting restaurant ID from URL {url}: {e}")
            return str(hash(url))
    
    def extract_city_from_address(self, address: str) -> Optional[str]:
        """Extract city name from address"""
        try:
            # Common Japanese city patterns
            japanese_cities = ['Tokyo', 'Osaka', 'Kyoto', 'Yokohama', 'Kobe', 'Nara', 'Hiroshima']
            
            for city in japanese_cities:
                if city.lower() in address.lower():
                    return city
            
            # Try to extract from Japanese address format
            # Many addresses contain prefecture and city info
            if '東京' in address:
                return 'Tokyo'
            elif '大阪' in address:
                return 'Osaka'
            elif '京都' in address:
                return 'Kyoto'
            elif '横浜' in address:
                return 'Yokohama'
            elif '神戸' in address:
                return 'Kobe'
            
            # Try to extract from address format
            parts = address.split(',')
            if len(parts) >= 2:
                potential_city = parts[-2].strip()
                if len(potential_city) > 2 and len(potential_city) < 50:
                    return potential_city
            
        except Exception as e:
            logger.debug(f"Error extracting city from address: {e}")
        
        return None
    
    async def save_data(self, data_list: List[Dict[str, Any]]) -> bool:
        """Save restaurant data to database"""
        try:
            async with await self.get_connection() as conn:
                saved_count = 0
                
                for data in data_list:
                    try:
                        # Prepare data for insertion
                        query = """
                            INSERT INTO scraped_restaurants 
                            (source_item_id, source_name, name, url, rating, review_count, 
                             cuisine_type, price_range, address, city, image_url, content_hash, scraped_at)
                            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, NOW())
                            ON CONFLICT (source_item_id, source_name) 
                            DO UPDATE SET 
                                name = EXCLUDED.name,
                                url = EXCLUDED.url,
                                rating = EXCLUDED.rating,
                                review_count = EXCLUDED.review_count,
                                cuisine_type = EXCLUDED.cuisine_type,
                                price_range = EXCLUDED.price_range,
                                address = EXCLUDED.address,
                                city = EXCLUDED.city,
                                image_url = EXCLUDED.image_url,
                                content_hash = EXCLUDED.content_hash,
                                scraped_at = NOW()
                            WHERE scraped_restaurants.content_hash != EXCLUDED.content_hash;
                        """
                        
                        await conn.execute(
                            query,
                            data.get('source_item_id'),
                            data.get('source_name'),
                            data.get('name'),
                            data.get('url'),
                            data.get('rating'),
                            data.get('review_count'),
                            data.get('cuisine_type'),
                            data.get('price_range'),
                            data.get('address'),
                            data.get('city'),
                            data.get('image_url'),
                            data.get('content_hash')
                        )
                        
                        saved_count += 1
                        
                    except Exception as e:
                        logger.error(f"Error saving restaurant data: {e}")
                        continue
                
                logger.info(f"Saved {saved_count}/{len(data_list)} restaurant records")
                return saved_count > 0
                
        except Exception as e:
            logger.error(f"Error saving restaurant data to database: {e}")
            return False
        
        finally:
            if self.connection_pool:
                await self.connection_pool.close()

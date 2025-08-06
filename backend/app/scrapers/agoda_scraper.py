import asyncio
import logging
import re
from typing import Dict, Any, List, Optional
from urllib.parse import urljoin, urlparse, parse_qs, urlencode
import asyncpg
from datetime import datetime, timezone, timedelta
from .base import BaseScraper
from ..core.config import settings

logger = logging.getLogger(__name__)


class AgodaScraper(BaseScraper):
    """Scraper for Agoda hotel data"""
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.connection_pool = None
        
        # Dynamic search configuration for Japanese hotels
        self.search_config = {
            'destinations': [
                {'name': 'Tokyo', 'city_id': '4150'},
                {'name': 'Osaka', 'city_id': '4151'},
                {'name': 'Kyoto', 'city_id': '4152'},
                {'name': 'Yokohama', 'city_id': '4153'},
                {'name': 'Nagoya', 'city_id': '4154'},
            ],
            'check_in_days_ahead': 30,
            'nights': 2,
            'adults': 2,
            'rooms': 1,
            'max_pages': 3,  # Limit pages per destination
            'min_rating': 4.0,
        }
    
    async def get_connection(self):
        """Get database connection"""
        if not self.connection_pool:
            db_url = settings.database_url
            if db_url.startswith("postgresql+psycopg://"):
                db_url = db_url.replace("postgresql+psycopg://", "postgresql://")
            
            self.connection_pool = await asyncpg.create_pool(db_url, min_size=1, max_size=10)
        
        return self.connection_pool.acquire()

    def build_search_url(self, destination: Dict[str, str], page: int = 1) -> str:
        """Build dynamic search URL for a destination"""
        check_in = datetime.now() + timedelta(days=self.search_config['check_in_days_ahead'])
        check_out = check_in + timedelta(days=self.search_config['nights'])

        params = {
            'city': destination['city_id'],
            'checkIn': check_in.strftime("%Y-%m-%d"),
            'checkOut': check_out.strftime("%Y-%m-%d"),
            'adults': self.search_config['adults'],
            'rooms': self.search_config['rooms'],
            'countryId': '153',  # Japan country ID
            'page': page
        }

        base_url = "https://www.agoda.com/ja-jp/search"
        return f"{base_url}?{urlencode(params)}"

    async def scrape_urls(self) -> List[str]:
        """Get list of hotel URLs by scraping search results dynamically"""
        hotel_urls = []

        try:
            for destination in self.search_config['destinations']:
                logger.info(f"Scraping hotels in {destination['name']}")

                for page in range(1, self.search_config['max_pages'] + 1):
                    search_url = self.build_search_url(destination, page)
                    logger.info(f"Scraping search page {page} for {destination['name']}: {search_url}")

                    # Navigate to search page
                    success = await self.navigate_with_retry(search_url)
                    if not success:
                        logger.warning(f"Failed to navigate to search page: {search_url}")
                        continue

                    # Wait for search results to load
                    found_results = await self.wait_for_search_results()
                    if not found_results:
                        logger.warning(f"No hotel results found on page {page} for {destination['name']}")
                        break  # No more results, stop pagination

                    # Extract hotel URLs from current page
                    page_urls = await self.extract_hotel_urls_from_search()
                    hotel_urls.extend(page_urls)

                    logger.info(f"Found {len(page_urls)} hotel URLs on page {page} for {destination['name']}")

                    # Add delay between pages
                    await asyncio.sleep(2)

        except Exception as e:
            logger.error(f"Error scraping hotel URLs: {e}")

        # Remove duplicates and limit total results
        unique_urls = list(set(hotel_urls))[:50]  # Limit to 50 hotels total
        logger.info(f"Total unique hotel URLs found: {len(unique_urls)}")

        return unique_urls

    async def wait_for_search_results(self) -> bool:
        """Wait for search results to load and return True if found"""
        selectors_to_wait = [
            '[data-selenium="hotel-item"]',
            '.PropertyCard',
            '[data-testid="property-card"]',
            '.property-card',
            'a[href*="/hotel/"]'
        ]

        for selector in selectors_to_wait:
            try:
                await self.page.wait_for_selector(selector, timeout=10000)
                logger.info(f"Found search results with selector: {selector}")
                return True
            except:
                continue

        return False

    async def extract_hotel_urls_from_search(self) -> List[str]:
        """Extract hotel URLs from current search results page"""
        urls = []

        try:
            # Wait for dynamic content to load
            await asyncio.sleep(3)

            # Try multiple selectors for hotel links
            selectors = [
                'a[data-selenium="hotel-item"]',
                '.PropertyCard a[href*="/hotel/"]',
                '.hotel-item a[href*="/hotel/"]',
                'a[href*="/hotel/"]',
                '[data-testid="property-card"] a',
                '.property-card a'
            ]

            for selector in selectors:
                try:
                    hotel_links = await self.page.query_selector_all(selector)
                    logger.debug(f"Found {len(hotel_links)} links with selector: {selector}")

                    for link in hotel_links:
                        try:
                            href = await link.get_attribute('href')
                            if href and '/hotel/' in href:
                                # Convert relative URLs to absolute
                                if href.startswith('/'):
                                    full_url = urljoin('https://www.agoda.com', href)
                                else:
                                    full_url = href

                                # Ensure it's a valid Agoda hotel URL in Japan
                                if ('agoda.com' in full_url and '/hotel/' in full_url and
                                    ('-jp.html' in full_url or 'countryId=153' in full_url)):
                                    urls.append(full_url)

                        except Exception as e:
                            logger.debug(f"Error extracting URL from link: {e}")
                            continue

                    # If we found URLs with this selector, break
                    if urls:
                        logger.info(f"Successfully found {len(urls)} URLs with selector: {selector}")
                        break

                except Exception as e:
                    logger.debug(f"Selector {selector} failed: {e}")
                    continue

            # Remove duplicates
            urls = list(set(urls))

        except Exception as e:
            logger.error(f"Error extracting hotel URLs from search page: {e}")

        return urls

    async def extract_data(self, url: str) -> Optional[Dict[str, Any]]:
        """Extract hotel data from a single hotel page"""
        try:
            logger.info(f"Extracting data from: {url}")
            
            # Navigate to hotel page
            success = await self.navigate_with_retry(url)
            if not success:
                return None
            
            # Wait for page content to load
            try:
                await self.page.wait_for_selector('h1, .hotel-name, [data-selenium="hotel-header-name"]', timeout=10000)
            except:
                logger.warning(f"Hotel page content not loaded: {url}")
                return None
            
            # Extract hotel data using the extraction schema
            data = await self.extract_hotel_data()
            
            if not data or not data.get('name'):
                logger.warning(f"No valid data extracted from: {url}")
                return None
            
            # Add metadata
            data['url'] = url
            data['source_name'] = self.source_name
            data['source_item_id'] = self.extract_hotel_id_from_url(url)
            
            # Generate content hash
            data['content_hash'] = self.generate_hash(data)
            
            logger.info(f"Successfully extracted data for: {data.get('name', 'Unknown')}")
            return data
            
        except Exception as e:
            logger.error(f"Error extracting data from {url}: {e}")
            return None
    
    async def extract_hotel_data(self) -> Dict[str, Any]:
        """Extract hotel data from current page using extraction schema"""
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

            # Extract price
            price_selectors = self.extraction_schema.get('price', '')
            price_text = await self.extract_text_safely(price_selectors)
            if price_text:
                price = self.clean_price(price_text)
                if price:
                    data['price_per_night'] = price
                    # Try to extract currency
                    currency_match = re.search(r'([A-Z]{3}|\$|€|£|¥)', price_text)
                    if currency_match:
                        currency = currency_match.group(1)
                        if currency == '$':
                            currency = 'USD'
                        elif currency == '€':
                            currency = 'EUR'
                        elif currency == '£':
                            currency = 'GBP'
                        elif currency == '¥':
                            currency = 'JPY'
                        data['currency'] = currency

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
            logger.error(f"Error extracting hotel data: {e}")
        
        return data
    
    def extract_hotel_id_from_url(self, url: str) -> str:
        """Extract hotel ID from Agoda URL"""
        try:
            # Agoda URLs typically contain hotel ID in various formats
            # Example: https://www.agoda.com/hotel-name/hotel/tokyo-jp.html?cid=123456
            
            # Try to extract from URL path
            path_match = re.search(r'/hotel/[^/]+\.html\?.*?cid=(\d+)', url)
            if path_match:
                return path_match.group(1)
            
            # Try to extract from query parameters
            parsed_url = urlparse(url)
            query_params = parse_qs(parsed_url.query)
            if 'cid' in query_params:
                return query_params['cid'][0]
            
            # Fallback: use a hash of the URL
            return str(hash(url))
            
        except Exception as e:
            logger.debug(f"Error extracting hotel ID from URL {url}: {e}")
            return str(hash(url))
    
    def extract_city_from_address(self, address: str) -> Optional[str]:
        """Extract city name from address"""
        try:
            # Common Japanese city patterns
            japanese_cities = ['Tokyo', 'Osaka', 'Kyoto', 'Yokohama', 'Kobe', 'Nara', 'Hiroshima']
            
            for city in japanese_cities:
                if city.lower() in address.lower():
                    return city
            
            # Try to extract from address format
            # Many addresses end with ", City, Country"
            parts = address.split(',')
            if len(parts) >= 2:
                potential_city = parts[-2].strip()
                if len(potential_city) > 2 and len(potential_city) < 50:
                    return potential_city
            
        except Exception as e:
            logger.debug(f"Error extracting city from address: {e}")
        
        return None
    
    async def save_data(self, data_list: List[Dict[str, Any]]) -> bool:
        """Save hotel data to database"""
        try:
            async with await self.get_connection() as conn:
                saved_count = 0
                
                for data in data_list:
                    try:
                        # Prepare data for insertion
                        query = """
                            INSERT INTO scraped_hotels 
                            (source_item_id, source_name, name, url, rating, review_count, 
                             price_per_night, currency, address, city, image_url, content_hash, scraped_at)
                            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, NOW())
                            ON CONFLICT (source_item_id, source_name) 
                            DO UPDATE SET 
                                name = EXCLUDED.name,
                                url = EXCLUDED.url,
                                rating = EXCLUDED.rating,
                                review_count = EXCLUDED.review_count,
                                price_per_night = EXCLUDED.price_per_night,
                                currency = EXCLUDED.currency,
                                address = EXCLUDED.address,
                                city = EXCLUDED.city,
                                image_url = EXCLUDED.image_url,
                                content_hash = EXCLUDED.content_hash,
                                scraped_at = NOW()
                            WHERE scraped_hotels.content_hash != EXCLUDED.content_hash;
                        """
                        
                        await conn.execute(
                            query,
                            data.get('source_item_id'),
                            data.get('source_name'),
                            data.get('name'),
                            data.get('url'),
                            data.get('rating'),
                            data.get('review_count'),
                            data.get('price_per_night'),
                            data.get('currency'),
                            data.get('address'),
                            data.get('city'),
                            data.get('image_url'),
                            data.get('content_hash')
                        )
                        
                        saved_count += 1
                        
                    except Exception as e:
                        logger.error(f"Error saving hotel data: {e}")
                        continue
                
                logger.info(f"Saved {saved_count}/{len(data_list)} hotel records")
                return saved_count > 0
                
        except Exception as e:
            logger.error(f"Error saving hotel data to database: {e}")
            return False
        
        finally:
            if self.connection_pool:
                await self.connection_pool.close()

from abc import ABC, abstractmethod
from playwright.async_api import async_playwright, Browser, Page
import hashlib
import json
import logging
import asyncio
import random
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone
import re
from urllib.parse import urljoin, urlparse

logger = logging.getLogger(__name__)


class BaseScraper(ABC):
    """Base class for all scrapers with common functionality"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.source_name = config.get('source_name', 'unknown')
        self.base_url = config.get('base_url', '')
        self.extraction_schema = config.get('extraction_schema', {})
        self.browser: Optional[Browser] = None
        self.page: Optional[Page] = None
        
        # Anti-bot measures configuration
        self.user_agents = [
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15'
        ]
        
    async def initialize_browser(self) -> None:
        """Initialize Playwright browser with anti-bot measures"""
        try:
            playwright = await async_playwright().start()
            
            # Use random user agent
            user_agent = random.choice(self.user_agents)
            
            # Launch browser with stealth settings
            self.browser = await playwright.chromium.launch(
                headless=True,
                args=[
                    '--no-sandbox',
                    '--disable-blink-features=AutomationControlled',
                    '--disable-dev-shm-usage',
                    '--disable-extensions',
                    '--disable-gpu',
                    '--disable-web-security',
                    '--no-first-run',
                    '--no-default-browser-check'
                ]
            )
            
            # Create context with realistic settings
            context = await self.browser.new_context(
                user_agent=user_agent,
                viewport={'width': 1920, 'height': 1080},
                locale='en-US',
                timezone_id='America/New_York'
            )
            
            # Create page
            self.page = await context.new_page()
            
            # Add stealth scripts
            await self.page.add_init_script("""
                Object.defineProperty(navigator, 'webdriver', {
                    get: () => undefined,
                });
                
                Object.defineProperty(navigator, 'plugins', {
                    get: () => [1, 2, 3, 4, 5],
                });
                
                Object.defineProperty(navigator, 'languages', {
                    get: () => ['en-US', 'en'],
                });
            """)
            
            logger.info(f"Browser initialized for {self.source_name}")
            
        except Exception as e:
            logger.error(f"Failed to initialize browser for {self.source_name}: {e}")
            raise
    
    async def cleanup_browser(self) -> None:
        """Clean up browser resources"""
        try:
            if self.page:
                await self.page.close()
            if self.browser:
                await self.browser.close()
            logger.info(f"Browser cleaned up for {self.source_name}")
        except Exception as e:
            logger.error(f"Error cleaning up browser for {self.source_name}: {e}")
    
    async def navigate_with_retry(self, url: str, max_retries: int = 3) -> bool:
        """Navigate to URL with retry logic and random delays"""
        for attempt in range(max_retries):
            try:
                # Random delay between requests
                if attempt > 0:
                    delay = random.uniform(2, 5)
                    await asyncio.sleep(delay)
                
                logger.info(f"Navigating to {url} (attempt {attempt + 1})")
                
                # Navigate with timeout
                response = await self.page.goto(url, wait_until='networkidle', timeout=30000)
                
                if response and response.status < 400:
                    # Additional wait for dynamic content
                    await asyncio.sleep(random.uniform(1, 3))
                    return True
                else:
                    logger.warning(f"HTTP {response.status if response else 'No response'} for {url}")
                    
            except Exception as e:
                logger.warning(f"Navigation attempt {attempt + 1} failed for {url}: {e}")
                
        logger.error(f"Failed to navigate to {url} after {max_retries} attempts")
        return False
    
    def generate_hash(self, data: Dict[str, Any]) -> str:
        """Generate SHA-256 hash of a dictionary for content comparison"""
        try:
            # Create a normalized string representation
            normalized_data = json.dumps(data, sort_keys=True, ensure_ascii=False)
            dhash = hashlib.sha256()
            dhash.update(normalized_data.encode('utf-8'))
            return dhash.hexdigest()
        except Exception as e:
            logger.error(f"Error generating hash: {e}")
            return ""
    
    async def extract_text_safely(self, selectors: str) -> Optional[str]:
        """Safely extract text using CSS selectors with Playwright page methods"""
        try:
            if not selectors:
                return None

            # Handle multiple selectors separated by comma
            selector_list = [s.strip() for s in selectors.split(',')]

            for selector in selector_list:
                if selector:
                    try:
                        element = await self.page.query_selector(selector)
                        if element:
                            text = await element.inner_text()
                            if text and text.strip():
                                return text.strip()
                    except:
                        continue

            return None
        except Exception as e:
            logger.debug(f"Error extracting text with selectors '{selectors}': {e}")
            return None

    async def extract_attribute_safely(self, selectors: str, attribute: str) -> Optional[str]:
        """Safely extract attribute using CSS selectors with Playwright page methods"""
        try:
            if not selectors:
                return None

            selector_list = [s.strip() for s in selectors.split(',')]

            for selector in selector_list:
                if selector:
                    try:
                        element = await self.page.query_selector(selector)
                        if element:
                            attr_value = await element.get_attribute(attribute)
                            if attr_value:
                                return attr_value.strip()
                    except:
                        continue

            return None
        except Exception as e:
            logger.debug(f"Error extracting attribute '{attribute}' with selectors '{selectors}': {e}")
            return None
    
    def clean_price(self, price_text: str) -> Optional[float]:
        """Extract numeric price from text"""
        if not price_text:
            return None
        
        try:
            # Remove currency symbols and extract numbers
            price_clean = re.sub(r'[^\d.,]', '', price_text)
            price_clean = price_clean.replace(',', '')
            
            if price_clean:
                return float(price_clean)
        except:
            pass
        
        return None
    
    def clean_rating(self, rating_text: str) -> Optional[float]:
        """Extract numeric rating from text"""
        if not rating_text:
            return None
        
        try:
            # Extract first number that looks like a rating
            match = re.search(r'(\d+\.?\d*)', rating_text)
            if match:
                rating = float(match.group(1))
                # Normalize to 5-point scale if needed
                if rating > 5:
                    rating = rating / 2  # Assume 10-point scale
                return min(5.0, max(0.0, rating))
        except:
            pass
        
        return None
    
    def clean_review_count(self, review_text: str) -> Optional[int]:
        """Extract review count from text"""
        if not review_text:
            return None
        
        try:
            # Extract numbers from text
            numbers = re.findall(r'\d+', review_text.replace(',', ''))
            if numbers:
                return int(numbers[0])
        except:
            pass
        
        return None
    
    @abstractmethod
    async def scrape_urls(self) -> List[str]:
        """Get list of URLs to scrape - must be implemented by subclasses"""
        pass
    
    @abstractmethod
    async def extract_data(self, url: str) -> Optional[Dict[str, Any]]:
        """Extract data from a single URL - must be implemented by subclasses"""
        pass
    
    @abstractmethod
    async def save_data(self, data_list: List[Dict[str, Any]]) -> bool:
        """Save extracted data to database - must be implemented by subclasses"""
        pass
    
    async def run(self) -> Dict[str, Any]:
        """Main scraping workflow"""
        start_time = datetime.now(timezone.utc)
        results = {
            'source_name': self.source_name,
            'started_at': start_time.isoformat(),
            'status': 'running',
            'urls_processed': 0,
            'items_scraped': 0,
            'items_saved': 0,
            'errors': []
        }
        
        try:
            logger.info(f"Starting scraping for {self.source_name}")
            
            # Initialize browser
            await self.initialize_browser()
            
            # Get URLs to scrape
            urls = await self.scrape_urls()
            logger.info(f"Found {len(urls)} URLs to scrape for {self.source_name}")
            
            scraped_data = []
            
            # Process each URL
            for i, url in enumerate(urls):
                try:
                    logger.info(f"Processing URL {i+1}/{len(urls)}: {url}")
                    
                    data = await self.extract_data(url)
                    if data:
                        scraped_data.append(data)
                        results['items_scraped'] += 1
                    
                    results['urls_processed'] += 1
                    
                    # Rate limiting - random delay between requests
                    if i < len(urls) - 1:  # Don't delay after last URL
                        delay = random.uniform(1, 3)
                        await asyncio.sleep(delay)
                        
                except Exception as e:
                    error_msg = f"Error processing URL {url}: {e}"
                    logger.error(error_msg)
                    results['errors'].append(error_msg)
            
            # Save all scraped data
            if scraped_data:
                save_success = await self.save_data(scraped_data)
                if save_success:
                    results['items_saved'] = len(scraped_data)
                    results['status'] = 'completed'
                else:
                    results['status'] = 'failed'
                    results['errors'].append("Failed to save scraped data")
            else:
                results['status'] = 'completed'
                logger.warning(f"No data scraped for {self.source_name}")
            
        except Exception as e:
            error_msg = f"Scraping failed for {self.source_name}: {e}"
            logger.error(error_msg)
            results['status'] = 'failed'
            results['errors'].append(error_msg)
        
        finally:
            # Clean up browser
            await self.cleanup_browser()
            
            # Update results
            end_time = datetime.now(timezone.utc)
            results['completed_at'] = end_time.isoformat()
            results['duration_seconds'] = (end_time - start_time).total_seconds()
            
            logger.info(f"Scraping completed for {self.source_name}: {results['status']}")
            
        return results

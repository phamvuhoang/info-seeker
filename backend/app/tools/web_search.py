from agno.tools import Toolkit
from playwright.async_api import async_playwright
from typing import List, Dict, Any
import re


class WebSearchTools(Toolkit):
    def __init__(self):
        super().__init__(name="web_search_tools")
        self.max_results = 10
        self.timeout = 30000  # 30 seconds

        # Register the tools
        self.register(self.web_search)
        self.register(self.extract_content)

    async def web_search(self, query: str, max_results: int = 10) -> str:
        """Search the web for current information using DuckDuckGo

        Args:
            query: The search query
            max_results: Maximum number of results to return (default: 10)

        Returns:
            Formatted search results as a string
        """
        try:
            results = await self._search_duckduckgo(query, max_results)
            return self._format_results(results, query)
        except Exception as e:
            # As per requirements: no fallbacks/mocks, report actual errors
            error_msg = f"Web search failed: {str(e)}"
            print(error_msg)  # Log the error for debugging
            raise Exception(error_msg)  # Re-raise to ensure error is properly handled upstream

    async def web_search_structured(self, query: str, max_results: int = 10) -> List[Dict[str, Any]]:
        """Search the web and return structured results

        Args:
            query: The search query
            max_results: Maximum number of results to return (default: 10)

        Returns:
            List of structured search results
        """
        try:
            results = await self._search_duckduckgo(query, max_results)
            print(f"DEBUG: DuckDuckGo returned {len(results)} raw results for '{query}'")
            return results
        except Exception as e:
            # As per requirements: no fallbacks/mocks, report actual errors
            error_msg = f"Web search failed: {str(e)}"
            print(error_msg)  # Log the error for debugging
            raise Exception(error_msg)  # Re-raise to ensure error is properly handled upstream
    
    async def _search_duckduckgo(self, query: str, max_results: int = 10) -> List[Dict[str, Any]]:
        """Search using DuckDuckGo"""
        try:
            async with async_playwright() as p:
                # More robust browser launch configuration
                browser = await p.chromium.launch(
                    headless=True,
                    args=[
                        '--no-sandbox',
                        '--disable-dev-shm-usage',
                        '--disable-gpu',
                        '--disable-web-security',
                        '--disable-features=VizDisplayCompositor',
                        '--no-first-run',
                        '--disable-extensions',
                        '--disable-default-apps'
                    ]
                )
                page = await browser.new_page()

                try:
                    # Navigate to DuckDuckGo
                    await page.goto("https://duckduckgo.com/", timeout=self.timeout)

                    # Search
                    await page.fill('input[name="q"]', query)
                    await page.press('input[name="q"]', 'Enter')

                    # Wait for results with multiple selector fallbacks
                    result_elements = []
                    selectors_to_try = [
                        '[data-testid="result"]',
                        '.result',
                        '[data-layout="organic"]',
                        '.web-result',
                        '.result__body',
                        'article[data-testid="result"]',
                        '.results .result'
                    ]

                    for selector in selectors_to_try:
                        try:
                            await page.wait_for_selector(selector, timeout=3000)
                            result_elements = await page.query_selector_all(selector)
                            if result_elements:
                                break
                        except Exception:
                            continue

                    # If no results found with any selector, try a more general approach
                    if not result_elements:
                        await page.wait_for_load_state('networkidle', timeout=5000)
                        # Try to find any clickable links that might be results
                        result_elements = await page.query_selector_all('a[href*="http"]:has(h2), a[href*="http"]:has(h3)')

                    # Extract results
                    results = []

                    for i, element in enumerate(result_elements[:max_results]):
                        try:
                            # Try multiple selectors for title and URL
                            title = ""
                            url = ""
                            snippet = ""

                            # Try different title selectors
                            title_selectors = ['h2 a', 'h3 a', 'a h2', 'a h3', '.result__title a', '[data-testid="result-title-a"]']
                            for title_sel in title_selectors:
                                title_elem = await element.query_selector(title_sel)
                                if title_elem:
                                    title = await title_elem.inner_text()
                                    url = await title_elem.get_attribute('href')
                                    break

                            # If no title found, try getting it from the element itself if it's a link
                            if not title and not url:
                                if await element.get_attribute('href'):
                                    url = await element.get_attribute('href')
                                    title = await element.inner_text()

                            # Try different snippet selectors
                            snippet_selectors = ['[data-result="snippet"]', '.result__snippet', '.result-snippet', '.snippet']
                            for snippet_sel in snippet_selectors:
                                snippet_elem = await element.query_selector(snippet_sel)
                                if snippet_elem:
                                    snippet = await snippet_elem.inner_text()
                                    break

                            # Clean up the data
                            if title and url:
                                # Clean title and snippet
                                title = title.strip()[:200]  # Limit title length
                                snippet = snippet.strip()[:500]  # Limit snippet length

                                # Ensure URL is absolute
                                if url.startswith('/'):
                                    url = f"https://duckduckgo.com{url}"

                                results.append({
                                    "title": title,
                                    "url": url,
                                    "snippet": snippet,
                                    "source": "DuckDuckGo",
                                    "rank": i + 1
                                })
                        except Exception as e:
                            # Log the error but continue with other results
                            print(f"Error extracting result {i}: {e}")
                            continue

                    return results

                finally:
                    await browser.close()

        except Exception as e:
            # Log the error and return empty results
            print(f"Web search failed: {str(e)}")
            raise e
    


    def _format_results(self, results: List[Dict[str, Any]], query: str) -> str:
        """Format search results for the agent"""
        if not results:
            return f"No web search results found for query: {query}"
        
        formatted = f"Web search results for '{query}':\n\n"
        
        for i, result in enumerate(results, 1):
            formatted += f"{i}. **{result['title']}**\n"
            formatted += f"   URL: {result['url']}\n"
            formatted += f"   Summary: {result['snippet']}\n\n"
        
        return formatted


    async def extract_content(self, url: str) -> str:
        """Extract and clean content from web pages

        Args:
            url: The URL to extract content from

        Returns:
            Cleaned content from the web page
        """
        try:
            async with async_playwright() as p:
                browser = await p.chromium.launch(
                    headless=True,
                    args=[
                        '--no-sandbox',
                        '--disable-dev-shm-usage',
                        '--disable-gpu',
                        '--disable-web-security',
                        '--disable-features=VizDisplayCompositor'
                    ]
                )
                page = await browser.new_page()

                try:
                    await page.goto(url, timeout=self.timeout)

                    # Wait for content to load
                    await page.wait_for_load_state('networkidle', timeout=10000)

                    # Extract main content
                    content = await self._extract_main_content(page)

                    return self._clean_content(content)

                finally:
                    await browser.close()

        except Exception as e:
            # As per requirements: no fallbacks/mocks, report actual errors
            error_msg = f"Failed to extract content from {url}: {str(e)}"
            print(error_msg)  # Log the error for debugging
            raise Exception(error_msg)  # Re-raise to ensure error is properly handled upstream
    
    async def _extract_main_content(self, page) -> str:
        """Extract main content from page"""
        # Try common content selectors
        selectors = [
            'article',
            'main',
            '[role="main"]',
            '.content',
            '.post-content',
            '.entry-content',
            '#content',
            'body'
        ]
        
        for selector in selectors:
            try:
                element = await page.query_selector(selector)
                if element:
                    content = await element.inner_text()
                    if len(content.strip()) > 100:  # Ensure meaningful content
                        return content
            except:
                continue
        
        # Fallback to body text
        return await page.inner_text('body')
    
    def _clean_content(self, content: str) -> str:
        """Clean and format extracted content"""
        if not content:
            return ""
        
        # Remove excessive whitespace
        content = re.sub(r'\n\s*\n', '\n\n', content)
        content = re.sub(r' +', ' ', content)
        
        # Limit content length
        max_length = 5000
        if len(content) > max_length:
            content = content[:max_length] + "..."
        
        return content.strip()
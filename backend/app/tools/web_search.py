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
            return f"Web search failed: {str(e)}"
    
    async def _search_duckduckgo(self, query: str, max_results: int = 10) -> List[Dict[str, Any]]:
        """Search using DuckDuckGo"""
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()
            
            try:
                # Navigate to DuckDuckGo
                await page.goto("https://duckduckgo.com/", timeout=self.timeout)
                
                # Search
                await page.fill('input[name="q"]', query)
                await page.press('input[name="q"]', 'Enter')
                
                # Wait for results
                await page.wait_for_selector('[data-testid="result"]', timeout=self.timeout)
                
                # Extract results
                results = []
                result_elements = await page.query_selector_all('[data-testid="result"]')
                
                for i, element in enumerate(result_elements[:max_results]):
                    try:
                        title_elem = await element.query_selector('h2 a')
                        title = await title_elem.inner_text() if title_elem else "No title"
                        url = await title_elem.get_attribute('href') if title_elem else ""
                        
                        snippet_elem = await element.query_selector('[data-result="snippet"]')
                        snippet = await snippet_elem.inner_text() if snippet_elem else ""
                        
                        if title and url:
                            results.append({
                                "title": title.strip(),
                                "url": url,
                                "snippet": snippet.strip(),
                                "source": "DuckDuckGo",
                                "rank": i + 1
                            })
                    except Exception:
                        continue
                
                return results
                
            finally:
                await browser.close()
    
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
                browser = await p.chromium.launch(headless=True)
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
            return f"Failed to extract content from {url}: {str(e)}"
    
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
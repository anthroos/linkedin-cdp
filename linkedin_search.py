"""
LinkedIn Search — screenshot-based, Input-only approach.

All interactions use CDP Input domain (mouse, keyboard, scroll).
All data reading uses screenshots (caller interprets visually).
Zero DOM access.

Usage:
    from linkedin_search import LinkedInSearch

    search = LinkedInSearch()
    search.connect()
    screenshots = search.search_people("AI Engineer Kyiv")
    # caller reads screenshots visually to extract results
    search.close()
"""
import random
import time
from urllib.parse import quote

from linkedin_cdp import LinkedInBot
from rate_limiter import RateLimiter

SEARCH_URL = "https://www.linkedin.com/search/results/people/?keywords={query}"
COMPANY_SEARCH_URL = "https://www.linkedin.com/search/results/companies/?keywords={query}"


class LinkedInSearch(LinkedInBot):
    """LinkedIn search via CDP Input domain + screenshots."""

    def __init__(self, port=9222, use_rate_limiter=True):
        super().__init__(port=port)
        self.limiter = RateLimiter() if use_rate_limiter else None

    def search_people(self, query: str, scroll_pages: int = 1) -> list:
        """Search for people and return screenshots of results.

        Args:
            query: Search query string
            scroll_pages: Number of times to scroll down for more results

        Returns:
            List of base64 PNG screenshots of search results pages.
        """
        if self.limiter:
            if not self.limiter.can_search():
                print("✗ Daily search limit reached")
                return []
            self.limiter.wait_if_needed('searches')

        url = SEARCH_URL.format(query=quote(query))
        print(f"🔍 Searching: {query}")

        self.navigate_to(url, wait_seconds=10, reconnect_pattern="/search")

        if self.limiter:
            self.limiter.record_search()

        screenshots = []

        # First page
        screenshot = self.wait_for_page(seconds=3.0)
        if screenshot:
            screenshots.append(screenshot)
            print(f"✓ Search results page 1 captured")

        # Scroll for more results
        for i in range(scroll_pages):
            self.scroll_wheel(delta_y=800, x=500, y=400)
            time.sleep(random.uniform(2.0, 3.5))
            screenshot = self.take_screenshot()
            if screenshot:
                screenshots.append(screenshot)
                print(f"✓ Search results page {i + 2} captured")

        return screenshots

    def search_companies(self, query: str, scroll_pages: int = 1) -> list:
        """Search for companies and return screenshots of results.

        Args:
            query: Search query string
            scroll_pages: Number of times to scroll down

        Returns:
            List of base64 PNG screenshots.
        """
        if self.limiter:
            if not self.limiter.can_search():
                print("✗ Daily search limit reached")
                return []
            self.limiter.wait_if_needed('searches')

        url = COMPANY_SEARCH_URL.format(query=quote(query))
        print(f"🔍 Searching companies: {query}")

        self.navigate_to(url, wait_seconds=10, reconnect_pattern="/search")

        if self.limiter:
            self.limiter.record_search()

        screenshots = []

        screenshot = self.wait_for_page(seconds=3.0)
        if screenshot:
            screenshots.append(screenshot)

        for i in range(scroll_pages):
            self.scroll_wheel(delta_y=800, x=500, y=400)
            time.sleep(random.uniform(2.0, 3.5))
            screenshot = self.take_screenshot()
            if screenshot:
                screenshots.append(screenshot)

        return screenshots

    def next_page(self, next_button_x: int, next_button_y: int) -> str:
        """Click Next button to go to next page of results.

        Args:
            next_button_x, next_button_y: Coordinates of Next button
                                           (determined by caller from screenshot)

        Returns:
            base64 PNG screenshot of next results page.
        """
        self._click(next_button_x, next_button_y)
        time.sleep(random.uniform(3.0, 5.0))
        return self.wait_for_page(seconds=3.0)

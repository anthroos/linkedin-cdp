#!/usr/bin/env python3
"""
LinkedIn people and company search via CDP.
"""
import time
import random
import urllib.parse
from typing import List, Dict, Optional, Any
from linkedin_cdp import LinkedInBot
from rate_limiter import RateLimiter


class LinkedInSearch(LinkedInBot):
    """LinkedIn search functionality."""

    SEARCH_URL = "https://www.linkedin.com/search/results/people/?keywords={query}"
    COMPANY_SEARCH_URL = "https://www.linkedin.com/search/results/companies/?keywords={query}"

    def __init__(self, use_rate_limiter: bool = True):
        super().__init__()
        self.limiter = RateLimiter() if use_rate_limiter else None

    def _wait_for_results(self, timeout: int = 10) -> bool:
        """Wait for search results to load."""
        start = time.time()
        while time.time() - start < timeout:
            result = self._evaluate('''
                document.querySelectorAll('.reusable-search__result-container').length > 0 ||
                document.querySelectorAll('.search-results-container').length > 0
            ''')
            if result:
                self._human_delay(500, 1000)
                return True
            time.sleep(0.5)
        return False

    def navigate_to(self, url: str) -> bool:
        """Navigate to a URL."""
        result = self._send("Page.navigate", {"url": url})
        if result.get("error"):
            print(f"✗ Navigation failed: {result.get('error')}")
            return False

        # Wait for page load
        time.sleep(2)
        self._human_delay(1000, 2000)
        return True

    def search_people(
        self,
        query: str,
        limit: int = 10,
        filters: Dict[str, str] = None
    ) -> List[Dict[str, Any]]:
        """
        Search for people on LinkedIn.

        Args:
            query: Search query (e.g., "AI Engineer San Francisco")
            limit: Maximum results to return
            filters: Optional filters (location, company, etc.)

        Returns:
            List of people with name, title, location, profile_url
        """
        if self.limiter:
            if not self.limiter.can_search():
                print("✗ Daily search limit reached")
                return []
            self.limiter.wait_if_needed('searches')

        # Build search URL
        encoded_query = urllib.parse.quote(query)
        url = self.SEARCH_URL.format(query=encoded_query)

        print(f"🔍 Searching: {query}")
        if not self.navigate_to(url):
            return []

        if not self._wait_for_results():
            print("✗ No search results found")
            return []

        # Extract results
        results = self._evaluate('''
            (() => {
                const results = [];
                const items = document.querySelectorAll('.reusable-search__result-container');

                items.forEach((item, index) => {
                    if (index >= ''' + str(limit) + ''') return;

                    const nameEl = item.querySelector('.entity-result__title-text a span[aria-hidden="true"]');
                    const titleEl = item.querySelector('.entity-result__primary-subtitle');
                    const locationEl = item.querySelector('.entity-result__secondary-subtitle');
                    const linkEl = item.querySelector('.entity-result__title-text a');
                    const imgEl = item.querySelector('.presence-entity__image');

                    if (nameEl) {
                        results.push({
                            name: nameEl.innerText.trim(),
                            title: titleEl ? titleEl.innerText.trim() : '',
                            location: locationEl ? locationEl.innerText.trim() : '',
                            profile_url: linkEl ? linkEl.href.split('?')[0] : '',
                            image_url: imgEl ? imgEl.src : ''
                        });
                    }
                });

                return JSON.stringify(results);
            })()
        ''')

        if self.limiter:
            self.limiter.record_search()

        try:
            people = eval(results) if results else []
            print(f"✓ Found {len(people)} results")
            return people
        except:
            return []

    def search_companies(
        self,
        query: str,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Search for companies on LinkedIn.

        Args:
            query: Search query (e.g., "AI startup")
            limit: Maximum results to return

        Returns:
            List of companies with name, industry, size, url
        """
        if self.limiter:
            if not self.limiter.can_search():
                print("✗ Daily search limit reached")
                return []
            self.limiter.wait_if_needed('searches')

        encoded_query = urllib.parse.quote(query)
        url = self.COMPANY_SEARCH_URL.format(query=encoded_query)

        print(f"🔍 Searching companies: {query}")
        if not self.navigate_to(url):
            return []

        if not self._wait_for_results():
            print("✗ No search results found")
            return []

        results = self._evaluate('''
            (() => {
                const results = [];
                const items = document.querySelectorAll('.reusable-search__result-container');

                items.forEach((item, index) => {
                    if (index >= ''' + str(limit) + ''') return;

                    const nameEl = item.querySelector('.entity-result__title-text a span[aria-hidden="true"]');
                    const subtitleEl = item.querySelector('.entity-result__primary-subtitle');
                    const secondaryEl = item.querySelector('.entity-result__secondary-subtitle');
                    const linkEl = item.querySelector('.entity-result__title-text a');

                    if (nameEl) {
                        results.push({
                            name: nameEl.innerText.trim(),
                            industry: subtitleEl ? subtitleEl.innerText.trim() : '',
                            info: secondaryEl ? secondaryEl.innerText.trim() : '',
                            company_url: linkEl ? linkEl.href.split('?')[0] : ''
                        });
                    }
                });

                return JSON.stringify(results);
            })()
        ''')

        if self.limiter:
            self.limiter.record_search()

        try:
            companies = eval(results) if results else []
            print(f"✓ Found {len(companies)} companies")
            return companies
        except:
            return []

    def get_search_suggestions(self, query: str) -> List[str]:
        """Get search suggestions for a query."""
        # Navigate to LinkedIn search
        self.navigate_to("https://www.linkedin.com/search/results/all/")
        self._human_delay(500, 1000)

        # Focus search input and type
        self.click_element('input.search-global-typeahead__input')
        self._human_delay(200, 400)
        self.type_text(query)
        self._human_delay(500, 1000)

        # Get suggestions
        suggestions = self._evaluate('''
            (() => {
                const items = document.querySelectorAll('.search-typeahead-v2__suggestion-text');
                return Array.from(items).map(el => el.innerText.trim()).slice(0, 5);
            })()
        ''')

        return suggestions if suggestions else []


def main():
    """Test search functionality."""
    search = LinkedInSearch()

    if not search.connect():
        print("Failed to connect")
        return

    # Test people search
    print("\n=== People Search ===")
    people = search.search_people("AI Engineer", limit=5)
    for p in people:
        print(f"  • {p['name']} - {p['title']}")

    search.close()


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
LinkedIn people and company search via CDP.
"""
import json
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

    def _wait_for_results(self, timeout: int = 15, result_type: str = 'people') -> bool:
        """Wait for search results to load."""
        start = time.time()
        link_pattern = '/in/' if result_type == 'people' else '/company/'

        while time.time() - start < timeout:
            result = self._evaluate(f'''
                document.querySelectorAll('a[href*="{link_pattern}"]').length > 5
            ''')
            if result:
                self._human_delay(500, 1000)
                return True
            time.sleep(0.5)
        return False

    def navigate_to(self, url: str) -> bool:
        """Navigate to a URL and reconnect to the tab."""
        import requests
        import websocket

        result = self._send("Page.navigate", {"url": url})
        if result.get("error"):
            print(f"✗ Navigation failed: {result.get('error')}")
            return False

        # Wait for page load (LinkedIn needs time to render, especially company search)
        time.sleep(12)

        # Reconnect to the tab after navigation
        try:
            resp = requests.get(f"http://localhost:{self.port}/json", timeout=5)
            tabs = resp.json()

            # Find the tab with our search type (people/companies)
            target_tab = None
            search_type = 'companies' if '/companies/' in url else 'people' if '/people/' in url else ''

            for tab in tabs:
                tab_url = tab.get("url", "")
                # Match by search type to find the right tab
                if search_type and f'/search/results/{search_type}/' in tab_url:
                    target_tab = tab
                    break
                # Fallback: match by base URL
                elif url.split('?')[0] in tab_url:
                    target_tab = tab
                    break

            if target_tab and target_tab.get("webSocketDebuggerUrl"):
                if self.ws:
                    try:
                        self.ws.close()
                    except:
                        pass
                self.ws_url = target_tab["webSocketDebuggerUrl"]
                self.ws = websocket.create_connection(self.ws_url, timeout=30)
                self.ws.settimeout(30)
        except Exception as e:
            print(f"  Warning: reconnect failed: {e}")

        self._human_delay(1000, 2000)
        return True

    def _scroll_page(self):
        """Scroll to trigger lazy loading."""
        try:
            self._evaluate('window.scrollTo(0, 500)')
            time.sleep(1)
        except:
            pass  # Ignore scroll errors

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

        # Scroll to trigger lazy loading
        self._scroll_page()

        if not self._wait_for_results():
            print("✗ No search results found")
            return []

        # Extract results using profile link-based approach
        # (LinkedIn uses obfuscated class names, so we find profiles by URL pattern)
        results = self._evaluate('''
            (() => {
                const seen = new Set();
                const results = [];
                const limit = ''' + str(limit) + ''';

                document.querySelectorAll('a[href*="/in/"]').forEach(link => {
                    if (results.length >= limit) return;

                    const href = link.href;
                    const match = href.match(/\\/in\\/([a-zA-Z0-9\\-]+)/);
                    if (!match) return;

                    const username = match[1];
                    if (seen.has(username) || username === 'me') return;

                    const text = link.innerText.trim();
                    if (text.length < 3 || text.length > 100) return;
                    if (text.includes('View') && text.includes('profile')) return;

                    // Get first line as name (remove connection badges)
                    const name = text.split('\\n')[0].replace(/•.*/, '').trim();
                    if (name.length < 2) return;

                    // Get context from parent container
                    let container = link.parentElement;
                    for (let i = 0; i < 6 && container; i++) {
                        container = container.parentElement;
                    }

                    let title = '';
                    let location = '';

                    if (container) {
                        const lines = container.innerText.split('\\n')
                            .map(l => l.trim())
                            .filter(l => l.length > 3);

                        let foundName = false;
                        for (const line of lines) {
                            if (line.includes(name.substring(0, 8))) {
                                foundName = true;
                                continue;
                            }
                            if (!foundName) continue;
                            if (line.includes('•') || line === 'Message' || line === 'Connect') continue;

                            if (!title) {
                                title = line;
                            } else if (!location && line.length < 80) {
                                location = line;
                                break;
                            }
                        }
                    }

                    seen.add(username);
                    results.push({
                        name: name,
                        title: title.substring(0, 100),
                        location: location.substring(0, 80),
                        profile_url: 'https://www.linkedin.com/in/' + username
                    });
                });

                return JSON.stringify(results);
            })()
        ''')

        if self.limiter:
            self.limiter.record_search()

        try:
            people = json.loads(results) if results else []
            print(f"✓ Found {len(people)} results")
            return people
        except json.JSONDecodeError:
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

        # Scroll to trigger lazy loading
        self._scroll_page()

        if not self._wait_for_results(result_type='companies'):
            print("✗ No search results found")
            return []

        # Extract company results using link-based approach
        results = self._evaluate('''
            (() => {
                const seen = new Set();
                const results = [];
                const limit = ''' + str(limit) + ''';

                document.querySelectorAll('a[href*="/company/"]').forEach(link => {
                    if (results.length >= limit) return;

                    const href = link.href;
                    const match = href.match(/\\/company\\/([a-zA-Z0-9\\-]+)/);
                    if (!match) return;

                    const companySlug = match[1];
                    if (seen.has(companySlug)) return;

                    const text = link.innerText.trim();
                    if (text.length < 2 || text.length > 100) return;

                    const name = text.split('\\n')[0].trim();
                    if (name.length < 2) return;

                    // Get context from parent
                    let container = link.parentElement;
                    for (let i = 0; i < 6 && container; i++) {
                        container = container.parentElement;
                    }

                    let industry = '';
                    let info = '';

                    if (container) {
                        const lines = container.innerText.split('\\n')
                            .map(l => l.trim())
                            .filter(l => l.length > 3 && l !== name);

                        for (const line of lines) {
                            if (line === 'Follow' || line === 'Following') continue;
                            if (!industry) {
                                industry = line;
                            } else if (!info && line.length < 100) {
                                info = line;
                                break;
                            }
                        }
                    }

                    seen.add(companySlug);
                    results.push({
                        name: name,
                        industry: industry.substring(0, 80),
                        info: info.substring(0, 100),
                        company_url: 'https://www.linkedin.com/company/' + companySlug
                    });
                });

                return JSON.stringify(results);
            })()
        ''')

        if self.limiter:
            self.limiter.record_search()

        try:
            companies = json.loads(results) if results else []
            print(f"✓ Found {len(companies)} companies")
            return companies
        except json.JSONDecodeError:
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

#!/usr/bin/env python3
"""
LinkedIn profile data extraction via CDP.
"""
import time
import json
from typing import Dict, Any, List, Optional
from linkedin_cdp import LinkedInBot
from rate_limiter import RateLimiter


class LinkedInProfile(LinkedInBot):
    """LinkedIn profile viewing and data extraction."""

    def __init__(self, use_rate_limiter: bool = True):
        super().__init__()
        self.limiter = RateLimiter() if use_rate_limiter else None

    def navigate_to(self, url: str) -> bool:
        """Navigate to a URL."""
        result = self._send("Page.navigate", {"url": url})
        if result.get("error"):
            print(f"✗ Navigation failed: {result.get('error')}")
            return False

        time.sleep(2)
        self._human_delay(1000, 2000)
        return True

    def _wait_for_profile(self, timeout: int = 10) -> bool:
        """Wait for profile page to load."""
        start = time.time()
        while time.time() - start < timeout:
            result = self._evaluate('''
                document.querySelector('.pv-top-card') !== null ||
                document.querySelector('.profile-photo-edit__preview') !== null
            ''')
            if result:
                self._human_delay(500, 1000)
                return True
            time.sleep(0.5)
        return False

    def get_profile(self, profile_url: str) -> Dict[str, Any]:
        """
        Get full profile data from a LinkedIn profile URL.

        Args:
            profile_url: LinkedIn profile URL (e.g., https://linkedin.com/in/username)

        Returns:
            Dict with name, title, location, about, experience, education, skills
        """
        if self.limiter:
            if not self.limiter.can_view_profile():
                print("✗ Daily profile view limit reached")
                return {}
            self.limiter.wait_if_needed('profile_views')

        # Normalize URL
        if not profile_url.startswith('http'):
            profile_url = f"https://www.linkedin.com/in/{profile_url}"

        print(f"📋 Viewing profile: {profile_url}")
        if not self.navigate_to(profile_url):
            return {}

        if not self._wait_for_profile():
            print("✗ Profile page failed to load")
            return {}

        # Extract basic info
        profile_data = self._evaluate('''
            (() => {
                const data = {};

                // Name
                const nameEl = document.querySelector('.pv-top-card h1') ||
                              document.querySelector('.text-heading-xlarge');
                data.name = nameEl ? nameEl.innerText.trim() : '';

                // Title/Headline
                const titleEl = document.querySelector('.pv-top-card .text-body-medium') ||
                               document.querySelector('.pv-top-card-profile-picture + div .text-body-medium');
                data.title = titleEl ? titleEl.innerText.trim() : '';

                // Location
                const locationEl = document.querySelector('.pv-top-card .text-body-small.inline') ||
                                  document.querySelector('.pv-top-card-profile-picture + div span.text-body-small');
                data.location = locationEl ? locationEl.innerText.trim() : '';

                // Profile image
                const imgEl = document.querySelector('.pv-top-card-profile-picture__image') ||
                             document.querySelector('.profile-photo-edit__preview');
                data.image_url = imgEl ? imgEl.src : '';

                // Connection count
                const connectEl = document.querySelector('.pv-top-card--list-bullet li:first-child span');
                data.connections = connectEl ? connectEl.innerText.trim() : '';

                // About section
                const aboutEl = document.querySelector('#about ~ .display-flex .inline-show-more-text span[aria-hidden="true"]') ||
                               document.querySelector('.pv-shared-text-with-see-more span[aria-hidden="true"]');
                data.about = aboutEl ? aboutEl.innerText.trim() : '';

                return JSON.stringify(data);
            })()
        ''')

        if self.limiter:
            self.limiter.record_profile_view()

        try:
            result = json.loads(profile_data) if profile_data else {}
            result['profile_url'] = profile_url
            print(f"✓ Profile loaded: {result.get('name', 'Unknown')}")
            return result
        except json.JSONDecodeError:
            return {'profile_url': profile_url}

    def get_experience(self) -> List[Dict[str, str]]:
        """
        Get work experience from current profile page.

        Returns:
            List of dicts with company, title, duration, location, description
        """
        self._human_delay(300, 600)

        # Try to expand experience section if collapsed
        self._evaluate('''
            const showMoreBtn = document.querySelector('#experience ~ .pvs-list__outer-container button[aria-expanded="false"]');
            if (showMoreBtn) showMoreBtn.click();
        ''')
        self._human_delay(500, 1000)

        experience = self._evaluate('''
            (() => {
                const items = [];
                const expSection = document.querySelector('#experience');
                if (!expSection) return JSON.stringify([]);

                const expItems = expSection.parentElement.querySelectorAll('.pvs-entity--padded');

                expItems.forEach(item => {
                    const titleEl = item.querySelector('.t-bold span[aria-hidden="true"]');
                    const companyEl = item.querySelector('.t-normal span[aria-hidden="true"]');
                    const durationEl = item.querySelector('.pvs-entity__caption-wrapper');
                    const locationEl = item.querySelectorAll('.t-normal span[aria-hidden="true"]')[1];

                    if (titleEl) {
                        items.push({
                            title: titleEl.innerText.trim(),
                            company: companyEl ? companyEl.innerText.trim().replace(' · ', ' - ') : '',
                            duration: durationEl ? durationEl.innerText.trim() : '',
                            location: locationEl ? locationEl.innerText.trim() : ''
                        });
                    }
                });

                return JSON.stringify(items);
            })()
        ''')

        try:
            return json.loads(experience) if experience else []
        except json.JSONDecodeError:
            return []

    def get_education(self) -> List[Dict[str, str]]:
        """
        Get education from current profile page.

        Returns:
            List of dicts with school, degree, field, years
        """
        self._human_delay(300, 600)

        education = self._evaluate('''
            (() => {
                const items = [];
                const eduSection = document.querySelector('#education');
                if (!eduSection) return JSON.stringify([]);

                const eduItems = eduSection.parentElement.querySelectorAll('.pvs-entity--padded');

                eduItems.forEach(item => {
                    const schoolEl = item.querySelector('.t-bold span[aria-hidden="true"]');
                    const degreeEl = item.querySelector('.t-normal span[aria-hidden="true"]');
                    const yearsEl = item.querySelector('.pvs-entity__caption-wrapper');

                    if (schoolEl) {
                        items.push({
                            school: schoolEl.innerText.trim(),
                            degree: degreeEl ? degreeEl.innerText.trim() : '',
                            years: yearsEl ? yearsEl.innerText.trim() : ''
                        });
                    }
                });

                return JSON.stringify(items);
            })()
        ''')

        try:
            return json.loads(education) if education else []
        except json.JSONDecodeError:
            return []

    def get_skills(self) -> List[str]:
        """
        Get skills from current profile page.

        Returns:
            List of skill names
        """
        self._human_delay(300, 600)

        # Try to navigate to skills section
        self._evaluate('''
            const skillsLink = document.querySelector('a[href*="/details/skills"]');
            if (skillsLink) skillsLink.click();
        ''')
        self._human_delay(1000, 2000)

        skills = self._evaluate('''
            (() => {
                const items = [];

                // Try skills detail page first
                const skillItems = document.querySelectorAll('.pvs-list__item--line-separated .t-bold span[aria-hidden="true"]');
                if (skillItems.length > 0) {
                    skillItems.forEach(el => items.push(el.innerText.trim()));
                    return JSON.stringify(items);
                }

                // Fallback to main profile skills section
                const mainSkills = document.querySelectorAll('#skills ~ .pvs-list__outer-container .t-bold span[aria-hidden="true"]');
                mainSkills.forEach(el => items.push(el.innerText.trim()));

                return JSON.stringify(items);
            })()
        ''')

        try:
            return json.loads(skills) if skills else []
        except json.JSONDecodeError:
            return []

    def get_full_profile(self, profile_url: str) -> Dict[str, Any]:
        """
        Get complete profile data including experience, education, and skills.

        Args:
            profile_url: LinkedIn profile URL

        Returns:
            Complete profile dict
        """
        profile = self.get_profile(profile_url)
        if not profile:
            return {}

        profile['experience'] = self.get_experience()
        profile['education'] = self.get_education()
        profile['skills'] = self.get_skills()

        return profile

    def is_connected(self) -> bool:
        """Check if currently viewing a 1st degree connection."""
        result = self._evaluate('''
            document.querySelector('.dist-value')?.innerText === '1st' ||
            document.querySelector('.pv-top-card__badge')?.innerText.includes('1st')
        ''')
        return bool(result)

    def get_connection_degree(self) -> str:
        """Get connection degree (1st, 2nd, 3rd, etc.)."""
        degree = self._evaluate('''
            (() => {
                const badge = document.querySelector('.dist-value') ||
                             document.querySelector('.pv-top-card__badge');
                if (badge) {
                    const text = badge.innerText.trim();
                    const match = text.match(/(1st|2nd|3rd|\\d+)/);
                    return match ? match[1] : '';
                }
                return '';
            })()
        ''')
        return degree if degree else 'unknown'


def main():
    """Test profile functionality."""
    profile = LinkedInProfile()

    if not profile.connect():
        print("Failed to connect")
        return

    # Test with a profile URL (replace with actual)
    print("\n=== Profile Test ===")
    # data = profile.get_full_profile("https://linkedin.com/in/example")
    # print(json.dumps(data, indent=2))

    print("Profile module ready. Use get_profile(url) or get_full_profile(url)")

    profile.close()


if __name__ == "__main__":
    main()

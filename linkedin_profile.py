"""
LinkedIn Profile — screenshot-based, Input-only approach.

All interactions use CDP Input domain (mouse, keyboard, scroll).
All data reading uses screenshots (caller interprets visually).
Zero DOM access.

Usage:
    from linkedin_profile import LinkedInProfile

    prof = LinkedInProfile()
    prof.connect()
    screenshots = prof.screenshot_full_profile("https://linkedin.com/in/username")
    # caller reads screenshots visually to extract name, title, experience, etc.
    prof.close()
"""
import re
import random
import time

from linkedin_cdp import LinkedInBot
from rate_limiter import RateLimiter


class LinkedInProfile(LinkedInBot):
    """LinkedIn profile viewing via CDP Input domain + screenshots."""

    def __init__(self, port=9222, use_rate_limiter=True):
        super().__init__(port=port)
        self.limiter = RateLimiter() if use_rate_limiter else None

    @staticmethod
    def _validate_profile_input(profile_url: str) -> str:
        """Validate and normalize a profile URL or username.

        Args:
            profile_url: Full LinkedIn URL or bare username.

        Returns:
            Validated full LinkedIn profile URL.

        Raises:
            ValueError: If the input is not a valid LinkedIn profile URL or username.
        """
        if profile_url.startswith("http"):
            if not (profile_url.startswith("https://www.linkedin.com/")
                    or profile_url.startswith("https://linkedin.com/")):
                raise ValueError(
                    f"Invalid LinkedIn URL: '{profile_url}'. "
                    "Must start with https://www.linkedin.com/ or https://linkedin.com/."
                )
            return profile_url
        else:
            # Bare username: allow alphanumeric, hyphens, no path traversal
            if not re.match(r'^[a-zA-Z0-9\-]+$', profile_url):
                raise ValueError(
                    f"Invalid LinkedIn username: '{profile_url}'. "
                    "Username may only contain alphanumeric characters and hyphens."
                )
            return f"https://www.linkedin.com/in/{profile_url}"

    def view_profile(self, profile_url: str) -> str:
        """Navigate to profile and return screenshot.

        Args:
            profile_url: LinkedIn profile URL (full or just username).

        Returns:
            Screenshot file path of profile top section.

        Raises:
            ValueError: If the URL/username is invalid.
        """
        if self.limiter:
            if not self.limiter.can_view_profile():
                print("✗ Daily profile view limit reached")
                return ""
            self.limiter.wait_if_needed('profile_views')

        profile_url = self._validate_profile_input(profile_url)

        print(f"📋 Viewing profile: {profile_url}")
        self.navigate_to(profile_url, wait_seconds=10, reconnect_pattern="/in/")

        if self.limiter:
            self.limiter.record_profile_view()

        screenshot = self.wait_for_page(seconds=3.0)
        if screenshot:
            print("✓ Profile loaded")
        return screenshot

    def screenshot_full_profile(self, profile_url: str,
                                scroll_count: int = 5) -> list:
        """Navigate to profile and take multiple screenshots while scrolling.

        Captures the full profile: header, about, experience, education,
        skills, etc. by scrolling down and taking screenshots.

        Args:
            profile_url: LinkedIn profile URL
            scroll_count: Number of scroll + screenshot iterations

        Returns:
            List of base64 PNG screenshots from top to bottom of profile.
        """
        screenshots = []

        # First screenshot (top of profile)
        top = self.view_profile(profile_url)
        if top:
            screenshots.append(top)

        # Scroll down and capture more sections
        for i in range(scroll_count):
            self.scroll_wheel(delta_y=700, x=450, y=400)
            time.sleep(random.uniform(2.0, 3.5))
            screenshot = self.take_screenshot()
            if screenshot:
                screenshots.append(screenshot)
                print(f"  Section {i + 2} captured")

        return screenshots

    def scroll_to_section(self, delta_y: int = 700) -> str:
        """Scroll down on profile to see next section.

        Args:
            delta_y: Scroll amount (positive = down, negative = up)

        Returns:
            base64 PNG screenshot after scrolling.
        """
        self.scroll_wheel(delta_y=delta_y, x=450, y=400)
        time.sleep(random.uniform(1.5, 2.5))
        return self.take_screenshot()

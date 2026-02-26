"""
LinkedIn Connect — screenshot-based, Input-only approach.

All interactions use CDP Input domain (mouse, keyboard, scroll).
All data reading uses screenshots (caller interprets visually).
Zero DOM access.

Multi-step workflows (send connection request, accept invitations)
are driven by the caller providing click coordinates from screenshots.

Usage:
    from linkedin_connect import LinkedInConnect

    conn = LinkedInConnect()
    conn.connect()

    # View profile
    screenshot = conn.view_profile("https://linkedin.com/in/username")
    # Caller sees Connect button at (x, y) from screenshot

    # Click Connect
    screenshot = conn.click_at(x, y)
    # Caller sees modal, finds "Add a note" at (x2, y2)

    # Click Add note
    screenshot = conn.click_at(x2, y2)
    # Caller sees textarea

    # Type note and send
    conn.type_text("Hi, I'd love to connect!")
    screenshot = conn.click_at(send_x, send_y)
    conn.close()
"""
import random
import time

from linkedin_cdp import LinkedInBot
from rate_limiter import RateLimiter

INVITATIONS_URL = "https://www.linkedin.com/mynetwork/invitation-manager/"
SENT_INVITATIONS_URL = "https://www.linkedin.com/mynetwork/invitation-manager/sent/"


class LinkedInConnect(LinkedInBot):
    """LinkedIn connection management via CDP Input domain + screenshots."""

    def __init__(self, port=9222, use_rate_limiter=True):
        super().__init__(port=port)
        self.limiter = RateLimiter() if use_rate_limiter else None

    def view_profile(self, profile_url: str) -> str:
        """Navigate to a profile page and screenshot it.

        The caller reads the screenshot to find Connect/Message/Pending
        buttons and provides coordinates for next action.

        Args:
            profile_url: LinkedIn profile URL

        Returns:
            base64 PNG screenshot.
        """
        if not profile_url.startswith('http'):
            profile_url = f"https://www.linkedin.com/in/{profile_url}"

        self.navigate_to(profile_url, wait_seconds=10, reconnect_pattern="/in/")
        return self.wait_for_page(seconds=3.0)

    def send_connection_note(self, input_x: int, input_y: int,
                             note: str) -> str:
        """Type a connection note in the note textarea and screenshot.

        Assumes the "Add a note" modal is already open (caller clicked it).

        Args:
            input_x, input_y: Coordinates of the note textarea
            note: Connection note text

        Returns:
            base64 PNG screenshot after typing.
        """
        if self.limiter:
            if not self.limiter.can_send_connection():
                print("✗ Daily connection request limit reached")
                return ""
            self.limiter.wait_if_needed('connection_requests')

        self._click(input_x, input_y)
        self._human_delay(300, 600)
        self.type_text(note)
        self._human_delay(400, 800)

        if self.limiter:
            self.limiter.record_connection_request()

        return self.take_screenshot()

    def screenshot_invitations(self) -> str:
        """Navigate to pending invitations page and screenshot.

        Returns:
            base64 PNG screenshot of pending invitations.
        """
        self.navigate_to(INVITATIONS_URL, wait_seconds=8,
                         reconnect_pattern="mynetwork")
        return self.wait_for_page(seconds=3.0)

    def screenshot_sent_invitations(self) -> str:
        """Navigate to sent invitations page and screenshot.

        Returns:
            base64 PNG screenshot of sent invitations.
        """
        self.navigate_to(SENT_INVITATIONS_URL, wait_seconds=8,
                         reconnect_pattern="mynetwork")
        return self.wait_for_page(seconds=3.0)

    def accept_invitation(self, accept_x: int, accept_y: int) -> str:
        """Click Accept button on an invitation.

        Args:
            accept_x, accept_y: Coordinates of Accept button
                                 (determined by caller from screenshot)

        Returns:
            base64 PNG screenshot after accepting.
        """
        if self.limiter:
            if not self.limiter.can_accept_connection():
                print("✗ Daily accept limit reached")
                return ""
            self.limiter.wait_if_needed('connection_accepts')

        self._click(accept_x, accept_y)
        self._human_delay(800, 1500)

        if self.limiter:
            self.limiter.record_connection_accept()

        return self.take_screenshot()

    def scroll_invitations(self) -> str:
        """Scroll down on invitations page for more results.

        Returns:
            base64 PNG screenshot after scrolling.
        """
        self.scroll_wheel(delta_y=600, x=450, y=400)
        time.sleep(random.uniform(1.5, 2.5))
        return self.take_screenshot()

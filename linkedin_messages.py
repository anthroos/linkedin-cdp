"""
LinkedIn Messages — screenshot-based, Input-only approach.

All navigation uses human-like mouse (Bezier curves from base class).
All data reading uses screenshots (caller interprets visually).
Zero DOM access.

Usage:
    from linkedin_messages import LinkedInMessages

    lm = LinkedInMessages()
    lm.connect()
    screenshot = lm.screenshot_conversations()  # caller reads visually
    screenshot = lm.open_conversation(click_x, click_y)
    screenshot = lm.screenshot_thread()
    lm.close()
"""
import random
import time

from linkedin_cdp import LinkedInBot
from rate_limiter import RateLimiter


class LinkedInMessages(LinkedInBot):
    """LinkedIn messaging via CDP Input domain + screenshots."""

    def __init__(self, port=9222, use_rate_limiter=True):
        super().__init__(port=port)
        self.limiter = RateLimiter() if use_rate_limiter else None

    # ── Navigation ─────────────────────────────────────────────

    def ensure_messaging_page(self) -> str:
        """Navigate to LinkedIn messaging. Returns screenshot."""
        self.navigate_to("https://www.linkedin.com/messaging/",
                         wait_seconds=5, reconnect_pattern="messaging")
        return self.wait_for_page(seconds=3.0)

    # ── Conversations ──────────────────────────────────────────

    def screenshot_conversations(self) -> str:
        """Navigate to messaging and screenshot conversation list.

        Returns:
            base64 PNG of conversation list.
            Caller interprets visually to find names, times, snippets,
            and click coordinates for each conversation.
        """
        return self.ensure_messaging_page()

    def open_conversation(self, click_x: int, click_y: int) -> str:
        """Click on a conversation at given coordinates.

        Args:
            click_x, click_y: Coordinates of the conversation to click
                              (determined by caller from screenshot)

        Returns:
            base64 PNG screenshot of opened conversation thread.
        """
        self._maybe_fake_hover(click_y)
        self._click(click_x, click_y)
        time.sleep(random.uniform(1.8, 3.0))
        return self.take_screenshot()

    def screenshot_thread(self) -> str:
        """Screenshot the currently open conversation thread.

        Returns:
            base64 PNG of the thread messages.
        """
        return self.take_screenshot()

    def scroll_thread_up(self) -> str:
        """Scroll up in current thread to load older messages.

        Returns:
            base64 PNG after scrolling up.
        """
        self.scroll_wheel(delta_y=-400, x=450, y=400)
        time.sleep(random.uniform(1.5, 2.5))
        return self.take_screenshot()

    def scroll_thread_down(self) -> str:
        """Scroll down in current thread.

        Returns:
            base64 PNG after scrolling down.
        """
        self.scroll_wheel(delta_y=400, x=450, y=400)
        time.sleep(random.uniform(1.0, 2.0))
        return self.take_screenshot()

    def scroll_conversations_down(self) -> str:
        """Scroll down in the conversation list to see more conversations.

        Returns:
            base64 PNG after scrolling.
        """
        # Scroll in the left panel area
        self.scroll_wheel(delta_y=400, x=200, y=400)
        time.sleep(random.uniform(1.0, 2.0))
        return self.take_screenshot()

    # ── Send message ───────────────────────────────────────────

    def send_message(self, input_x: int, input_y: int, text: str) -> str:
        """Click message input, type text, press Enter to send.

        Args:
            input_x, input_y: Coordinates of message input field
                               (determined by caller from screenshot)
            text: Message text to type

        Returns:
            base64 PNG screenshot after sending.
        """
        # Click on input field
        self._click(input_x, input_y)
        self._human_delay(400, 800)

        # Type message
        self.type_text(text)
        self._human_delay(600, 1200)

        # Press Enter to send
        self.press_key("Enter")
        self._human_delay(500, 1000)

        return self.take_screenshot()

    # ── Multi-conversation collection (screenshot-based) ───────

    def collect_screenshots(self, coords_list: list, pause: float = 2.0) -> list:
        """Click through a list of conversation coordinates and screenshot each.

        Args:
            coords_list: List of (x, y) tuples for conversations to click
                         (determined by caller from initial screenshot)
            pause: Seconds to wait after clicking each conversation

        Returns:
            List of base64 PNG screenshots, one per conversation.
        """
        screenshots = []
        for i, (cx, cy) in enumerate(coords_list):
            # Random offset within clickable area
            cx += random.randint(-5, 5)
            cy += random.randint(-3, 3)

            # Occasional fake hover
            if i > 0:
                self._maybe_fake_hover(cy)

            self._click(cx, cy)
            time.sleep(random.uniform(pause * 0.8, pause * 1.3))

            screenshots.append(self.take_screenshot())

            # Human reading pause
            if i < len(coords_list) - 1:
                time.sleep(random.uniform(0.5, 1.5))

        return screenshots

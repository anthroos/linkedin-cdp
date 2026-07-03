#!/usr/bin/env python3
"""
General-purpose browser automation via Chrome DevTools Protocol.

Screenshot-based, like the LinkedIn modules: actions go through CDP Input,
data reading goes through Page.captureScreenshot for a caller (e.g. a vision
model) to interpret.

Unlike linkedin_cdp.py, navigation is not locked to a single domain -- but the
same safety guards apply: dangerous URL schemes (file:, javascript:, data:,
chrome:, ...) and private/loopback/link-local hosts are blocked to prevent
local-file reads and SSRF against internal services; screenshot paths are
validated against traversal. Pass an allowlist to restrict hosts further.

Usage:
    from browser_cdp import BrowserBot
    bot = BrowserBot()                       # any public https host
    bot = BrowserBot(allowed_hosts=["luma.com"])  # restrict to luma.com
    bot.connect()
    bot.navigate("https://luma.com/event123")
    bot.screenshot("/tmp/browser_screenshots/screen.png")
    bot.click(500, 300)
"""
import base64
import ipaddress
import json
import os
import random
import threading
import time
from typing import Optional
from urllib.parse import urlparse

import requests
import websocket

CDP_PORT = 9222


class BrowserBot:
    """General browser automation via CDP Input domain + screenshots."""

    _BLOCKED_SCHEMES = ("file", "javascript", "chrome", "data", "ftp", "gopher", "about")

    def __init__(self, port: int = CDP_PORT, allowed_hosts: Optional[list] = None):
        """Args:
            port: CDP debugging port.
            allowed_hosts: Optional list of hostnames (or suffixes) to allow.
                If None, any public https host is allowed (private IPs still blocked).
        """
        self.port = port
        self.allowed_hosts = [h.lower() for h in allowed_hosts] if allowed_hosts else None
        self.ws: Optional[websocket.WebSocket] = None
        self.ws_url: Optional[str] = None
        self.msg_id = 0
        self._msg_lock = threading.Lock()
        self.cur_x = random.randint(400, 700)
        self.cur_y = random.randint(250, 450)
        self._screenshot_dir = "/tmp/browser_screenshots"
        self._screenshot_count = 0

    # ── Security helpers ────────────────────────────────────────────

    def _is_safe_url(self, url: str) -> bool:
        """Block dangerous schemes and private/loopback/link-local hosts.

        Requires https. If allowed_hosts is set, the host must match one of
        them (exact or suffix). Returns True if safe to navigate to.
        """
        parsed = urlparse(url)
        scheme = parsed.scheme.lower()
        if scheme in self._BLOCKED_SCHEMES:
            return False
        if scheme != "https":
            return False

        hostname = (parsed.hostname or "").lower()
        if not hostname or hostname == "localhost":
            return False

        # Block private / loopback / link-local IP literals
        try:
            addr = ipaddress.ip_address(hostname)
            if addr.is_private or addr.is_loopback or addr.is_link_local or addr.is_reserved:
                return False
        except ValueError:
            pass  # not an IP literal -- fine

        if self.allowed_hosts is not None:
            if not any(hostname == h or hostname.endswith("." + h) for h in self.allowed_hosts):
                return False

        return True

    @staticmethod
    def _is_safe_path(path: str, safe_dir: str) -> bool:
        """Validate a file path stays within safe_dir and has no traversal."""
        if ".." in path:
            return False
        resolved = os.path.realpath(path)
        safe_dir = os.path.realpath(safe_dir)
        return resolved.startswith(safe_dir + os.sep) or resolved == safe_dir

    # ── CDP core ──────────────────────────────────────────────────

    def connect(self, tab_index: int = 0):
        """Connect to a Chrome tab via CDP."""
        tabs = requests.get(f"http://127.0.0.1:{self.port}/json", timeout=5).json()
        pages = [t for t in tabs if t.get("type") == "page"]
        if not pages:
            raise RuntimeError("No browser tabs found")
        target = pages[tab_index]
        self.ws_url = target["webSocketDebuggerUrl"]
        self.ws = websocket.create_connection(self.ws_url, timeout=30)
        self.ws.settimeout(30)
        os.makedirs(self._screenshot_dir, exist_ok=True)
        print(f"Connected to: {target.get('title', '?')} | {target.get('url', '?')}")
        return self

    def _send(self, method: str, params: dict = None) -> dict:
        with self._msg_lock:
            self.msg_id += 1
            mid = self.msg_id
        msg = {"id": mid, "method": method}
        if params:
            msg["params"] = params
        self.ws.send(json.dumps(msg))
        while True:
            resp = json.loads(self.ws.recv())
            if resp.get("id") == mid:
                if "error" in resp:
                    raise RuntimeError(f"CDP error: {resp['error']}")
                return resp.get("result", {})

    def navigate(self, url: str) -> dict:
        """Navigate to a URL (https public hosts only; see _is_safe_url).

        Raises:
            ValueError: If the URL uses a blocked scheme or private/loopback host.
        """
        if not self._is_safe_url(url):
            raise ValueError(
                f"Unsafe URL: '{url}'. Only https:// URLs to public hosts are "
                "allowed; file:/data:/javascript: schemes and private/loopback "
                "hosts are blocked."
            )
        result = self._send("Page.navigate", {"url": url})
        time.sleep(2)
        return result

    def screenshot(self, path: str = None) -> str:
        """Take screenshot, save within the screenshot dir, return path.

        Raises:
            ValueError: If an explicit path escapes the screenshot directory.
        """
        os.makedirs(self._screenshot_dir, exist_ok=True)
        if not path:
            self._screenshot_count += 1
            path = f"{self._screenshot_dir}/screen_{self._screenshot_count:03d}.png"
        elif not self._is_safe_path(path, self._screenshot_dir):
            raise ValueError(
                f"Unsafe screenshot path: '{path}'. Must be within "
                f"{self._screenshot_dir} and must not contain '..'."
            )
        result = self._send("Page.captureScreenshot", {
            "format": "png",
            "captureBeyondViewport": False,
        })
        with open(path, "wb") as f:
            f.write(base64.b64decode(result["data"]))
        print(f"Screenshot: {path}")
        return path

    def click(self, x: int, y: int):
        """Click at coordinates."""
        self._send("Input.dispatchMouseEvent", {
            "type": "mousePressed", "x": x, "y": y,
            "button": "left", "clickCount": 1,
        })
        time.sleep(0.05 + random.random() * 0.1)
        self._send("Input.dispatchMouseEvent", {
            "type": "mouseReleased", "x": x, "y": y,
            "button": "left", "clickCount": 1,
        })
        self.cur_x, self.cur_y = x, y
        time.sleep(0.3)

    def type_text(self, text: str, delay: float = 0.05):
        """Type text character by character."""
        for ch in text:
            self._send("Input.dispatchKeyEvent", {"type": "keyDown", "text": ch})
            self._send("Input.dispatchKeyEvent", {"type": "keyUp", "text": ch})
            time.sleep(delay + random.random() * 0.03)

    def press_key(self, key: str):
        """Press a special key (Enter, Tab, Escape, etc.)."""
        key_codes = {
            "Enter": 13, "Tab": 9, "Escape": 27,
            "Backspace": 8, "ArrowDown": 40, "ArrowUp": 38,
        }
        code = key_codes.get(key, 0)
        self._send("Input.dispatchKeyEvent", {
            "type": "rawKeyDown", "key": key,
            "windowsVirtualKeyCode": code, "nativeVirtualKeyCode": code,
        })
        self._send("Input.dispatchKeyEvent", {
            "type": "keyUp", "key": key,
            "windowsVirtualKeyCode": code, "nativeVirtualKeyCode": code,
        })
        time.sleep(0.2)

    def scroll(self, x: int = 0, y: int = 0, delta_x: int = 0, delta_y: int = -300):
        """Scroll page. Negative delta_y = scroll down."""
        self._send("Input.dispatchMouseEvent", {
            "type": "mouseWheel",
            "x": x or self.cur_x, "y": y or self.cur_y,
            "deltaX": delta_x, "deltaY": delta_y,
        })
        time.sleep(0.5)

    def wait(self, seconds: float = 1.0):
        time.sleep(seconds)

    def close(self):
        if self.ws:
            self.ws.close()
            self.ws = None


if __name__ == "__main__":
    bot = BrowserBot()
    bot.connect()
    path = bot.screenshot()
    print(f"Screenshot saved: {path}")

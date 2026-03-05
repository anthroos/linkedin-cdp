#!/usr/bin/env python3
"""
LinkedIn automation via Chrome DevTools Protocol — Input-only approach.

All interactions use CDP Input domain (mouse, keyboard, scroll).
All data reading uses Page.captureScreenshot (visual interpretation by caller).
Zero DOM access (no Runtime.evaluate, no querySelector, no innerText).

Mouse trajectories use cubic Bezier curves with randomized control points,
easing functions, micro-jitter, overshoot correction, and variable speed
to ensure every path is unique and human-like.
"""
import base64
import glob as globmod
import ipaddress
import json
import math
import os
import random
import subprocess
import threading
import time
from typing import Optional
from urllib.parse import urlparse

import requests
import websocket

CDP_PORT = 9222
MAX_SCREENSHOT_DIM = 1920  # Max pixel dimension for Claude API compatibility


class LinkedInBot:
    """LinkedIn automation via CDP Input domain + screenshots."""

    # Allowed URL prefixes for navigation
    _ALLOWED_URL_PREFIXES = (
        "https://www.linkedin.com/",
        "https://linkedin.com/",
    )

    # Blocked URL schemes
    _BLOCKED_SCHEMES = ("file", "javascript", "chrome", "data", "ftp", "gopher")

    def __init__(self, port: int = CDP_PORT):
        self.port = port
        self.ws: Optional[websocket.WebSocket] = None
        self.ws_url: Optional[str] = None
        self.msg_id = 0
        self._msg_lock = threading.Lock()
        # Cursor position tracking (randomized start)
        self.cur_x = random.randint(400, 700)
        self.cur_y = random.randint(250, 450)
        # Screenshot file management
        self._screenshot_dir = "/tmp/li_screenshots"
        self._screenshot_count = 0
        self._screenshot_max_keep = 50

    # ── Security helpers ────────────────────────────────────────────

    @classmethod
    def _is_safe_url(cls, url: str) -> bool:
        """Validate that a URL is safe to navigate to.

        Only allows https://www.linkedin.com/ and https://linkedin.com/ URLs.
        Blocks file://, javascript:, chrome://, data:, internal IPs, and localhost.

        Returns:
            True if the URL is safe; False otherwise.
        """
        parsed = urlparse(url)

        # Block dangerous schemes
        if parsed.scheme.lower() in cls._BLOCKED_SCHEMES:
            return False

        # Must be https
        if parsed.scheme.lower() != "https":
            return False

        # Must start with allowed prefix
        if not any(url.startswith(prefix) for prefix in cls._ALLOWED_URL_PREFIXES):
            return False

        # Block internal/private IPs in hostname
        hostname = parsed.hostname or ""
        if hostname in ("localhost",):
            return False

        try:
            addr = ipaddress.ip_address(hostname)
            if addr.is_private or addr.is_loopback or addr.is_link_local:
                return False
        except ValueError:
            # Not an IP address literal -- that's fine
            pass

        return True

    @staticmethod
    def _is_safe_path(path: str, safe_dir: str = None) -> bool:
        """Validate that a file path is safe for writing.

        Resolves the path and checks it is within the allowed directory.
        Blocks paths containing '..'.

        Args:
            path: File path to validate.
            safe_dir: Allowed base directory. Defaults to /tmp/li_screenshots.

        Returns:
            True if the path is safe; False otherwise.
        """
        if ".." in path:
            return False

        resolved = os.path.realpath(path)
        safe_dir = safe_dir or "/tmp/li_screenshots"
        safe_dir = os.path.realpath(safe_dir)

        return resolved.startswith(safe_dir + os.sep) or resolved == safe_dir

    # ── CDP core ──────────────────────────────────────────────────

    def connect(self) -> bool:
        """Connect to Chrome via CDP."""
        try:
            resp = requests.get(f"http://localhost:{self.port}/json", timeout=5)
            tabs = resp.json()

            li_tab = None

            # Priority 1: messaging tab
            for tab in tabs:
                url = tab.get("url", "")
                if "linkedin.com/messaging" in url:
                    li_tab = tab
                    break

            # Priority 2: any LinkedIn page (skip iframes)
            if not li_tab:
                for tab in tabs:
                    url = tab.get("url", "")
                    if "linkedin.com" in url:
                        if any(x in url for x in ['/m/', 'protechts', 'merchantpool', 'licdn', '/lite/']):
                            continue
                        li_tab = tab
                        break

            # Fallback: first tab
            if not li_tab:
                li_tab = tabs[0] if tabs else None

            if not li_tab:
                print("✗ No tabs found")
                return False

            self.ws_url = li_tab.get("webSocketDebuggerUrl")
            if not self.ws_url:
                print("✗ No WebSocket URL")
                return False

            self.ws = websocket.create_connection(self.ws_url, timeout=30)
            self.ws.settimeout(30)
            os.makedirs(self._screenshot_dir, exist_ok=True)
            print(f"✓ Connected to: {li_tab.get('title', 'Unknown')[:50]}")
            return True

        except requests.RequestException as e:
            print(f"✗ Connection failed (HTTP): {e}")
            return False
        except websocket.WebSocketException as e:
            print(f"✗ Connection failed (WebSocket): {e}")
            return False
        except (json.JSONDecodeError, KeyError, IndexError) as e:
            print(f"✗ Connection failed (parsing): {e}")
            return False

    def _send(self, method: str, params: dict = None) -> dict:
        """Send CDP command and return result."""
        with self._msg_lock:
            self.msg_id += 1
            target_id = self.msg_id

        msg = {"id": target_id, "method": method, "params": params or {}}
        self.ws.send(json.dumps(msg))

        timeout_count = 0
        while timeout_count < 50:
            try:
                raw = self.ws.recv()
                try:
                    resp = json.loads(raw)
                except json.JSONDecodeError:
                    # Non-JSON response from CDP; skip and retry
                    timeout_count += 1
                    continue
                if resp.get("id") == target_id:
                    return resp
            except websocket.WebSocketTimeoutException:
                timeout_count += 1
                time.sleep(0.1)

        return {"error": "timeout"}

    def close(self):
        """Close WebSocket connection."""
        if self.ws:
            self.ws.close()
            self.ws = None

    def reconnect_to_tab(self, url_pattern: str = "linkedin.com") -> bool:
        """Reconnect WebSocket to a tab matching URL pattern."""
        try:
            if self.ws:
                try:
                    self.ws.close()
                except websocket.WebSocketException:
                    pass
            time.sleep(1)
            resp = requests.get(f"http://localhost:{self.port}/json", timeout=5)
            tabs = resp.json()

            for tab in tabs:
                tab_url = tab.get("url", "")
                if url_pattern in tab_url and tab.get("webSocketDebuggerUrl"):
                    self.ws_url = tab["webSocketDebuggerUrl"]
                    self.ws = websocket.create_connection(self.ws_url, timeout=30)
                    self.ws.settimeout(30)
                    return True
            return False
        except requests.RequestException as e:
            print(f"  Warning: reconnect failed (HTTP): {e}")
            return False
        except websocket.WebSocketException as e:
            print(f"  Warning: reconnect failed (WebSocket): {e}")
            return False
        except (json.JSONDecodeError, KeyError) as e:
            print(f"  Warning: reconnect failed (parsing): {e}")
            return False

    # ── Human-like mouse ──────────────────────────────────────────

    @staticmethod
    def _bezier(p0, p1, p2, p3, t):
        """Cubic Bezier interpolation at parameter t."""
        x = ((1 - t) ** 3 * p0[0]
             + 3 * (1 - t) ** 2 * t * p1[0]
             + 3 * (1 - t) * t ** 2 * p2[0]
             + t ** 3 * p3[0])
        y = ((1 - t) ** 3 * p0[1]
             + 3 * (1 - t) ** 2 * t * p1[1]
             + 3 * (1 - t) * t ** 2 * p2[1]
             + t ** 3 * p3[1])
        return (x, y)

    def _human_path(self, sx, sy, ex, ey):
        """Generate unique mouse path with random Bezier curve + micro-jitter.

        Every call produces a different trajectory via:
        - Random control point positions (r1, r2)
        - Random jitter magnitude (jx, jy)
        - Random easing function selection
        - Gaussian hand tremor per step
        - Variable step count
        - Occasional overshoot correction (12%)
        - Occasional micro-pause (15%)
        """
        dx, dy = ex - sx, ey - sy
        dist = math.sqrt(dx ** 2 + dy ** 2)

        # Random control points (unique every call)
        r1 = random.uniform(0.15, 0.45)
        r2 = random.uniform(0.55, 0.85)
        jx = random.uniform(-max(30, abs(dx) * 0.35), max(30, abs(dx) * 0.35))
        jy = random.uniform(-max(20, abs(dy) * 0.2), max(20, abs(dy) * 0.2))
        cp1 = (sx + dx * r1 + jx, sy + dy * r1 + jy * 0.6)
        cp2 = (sx + dx * r2 - jx * 0.5, sy + dy * r2 - jy * 0.4)

        steps = max(10, min(45, int(dist / 12) + random.randint(-4, 6)))

        # Random easing function
        easing = random.choice(['hermite', 'ease_in', 'ease_out', 'linear'])

        pts = []
        for i in range(steps + 1):
            t = i / steps

            # Apply selected easing
            if easing == 'hermite':
                t = t * t * (3 - 2 * t)
            elif easing == 'ease_in':
                t = t * t
            elif easing == 'ease_out':
                t = 1 - (1 - t) * (1 - t)
            # linear: t unchanged

            px, py = self._bezier((sx, sy), cp1, cp2, (ex, ey), t)
            px += random.gauss(0, 0.7)  # hand tremor
            py += random.gauss(0, 0.7)
            pts.append((int(px), int(py)))

        # Overshoot correction (12% chance)
        if random.random() < 0.12 and dist > 50:
            overshoot = random.uniform(5, 20)
            angle = math.atan2(dy, dx)
            ox = int(ex + overshoot * math.cos(angle))
            oy = int(ey + overshoot * math.sin(angle))
            pts.append((ox, oy))
            # Correct back
            correction = self._bezier((ox, oy), (ox, oy), (ex, ey), (ex, ey), 1.0)
            pts.append((int(correction[0]), int(correction[1])))

        return pts

    def _move_to(self, x, y):
        """Move mouse to target with human-like trajectory."""
        tx = x + random.randint(-3, 3)
        ty = y + random.randint(-3, 3)
        path = self._human_path(self.cur_x, self.cur_y, tx, ty)

        # Determine if we'll have a micro-pause (15% chance)
        pause_at = -1
        if random.random() < 0.15 and len(path) > 6:
            pause_at = random.randint(len(path) // 3, 2 * len(path) // 3)

        for i, (px, py) in enumerate(path):
            self._send("Input.dispatchMouseEvent", {
                "type": "mouseMoved", "x": px, "y": py, "button": "none",
            })
            # Variable speed per segment
            base_delay = random.uniform(0.004, 0.022)
            if i == pause_at:
                time.sleep(random.uniform(0.05, 0.15))  # micro-pause
            else:
                time.sleep(base_delay)

        self.cur_x, self.cur_y = path[-1]

    def _click(self, x, y):
        """Move to element and click with realistic timing."""
        self._move_to(x, y)
        time.sleep(random.uniform(0.08, 0.25))
        self._send("Input.dispatchMouseEvent", {
            "type": "mousePressed",
            "x": self.cur_x, "y": self.cur_y,
            "button": "left", "clickCount": 1,
        })
        time.sleep(random.uniform(0.04, 0.12))
        self._send("Input.dispatchMouseEvent", {
            "type": "mouseReleased",
            "x": self.cur_x, "y": self.cur_y,
            "button": "left", "clickCount": 1,
        })

    def _maybe_fake_hover(self, target_y):
        """30% chance to hover over a nearby element first (human behavior)."""
        if random.random() < 0.3:
            fake_y = target_y + random.choice([-80, 80, -160])
            self._move_to(self.cur_x, max(50, fake_y))
            time.sleep(random.uniform(0.1, 0.3))

    def _human_delay(self, min_ms: int = 100, max_ms: int = 400):
        """Random delay like a human."""
        time.sleep(random.uniform(min_ms / 1000, max_ms / 1000))

    # ── Keyboard ──────────────────────────────────────────────────

    def type_text(self, text: str, human_like: bool = True):
        """Type text character by character like a human."""
        for i, char in enumerate(text):
            self._send("Input.insertText", {"text": char})

            if human_like:
                if char in " ":
                    self._human_delay(150, 350)
                elif char in ".,!?":
                    self._human_delay(200, 450)
                elif char in "ABCDEFGHIJKLMNOPQRSTUVWXYZ":
                    self._human_delay(120, 280)
                else:
                    self._human_delay(80, 200)

                # Occasional thinking pause
                if i > 0 and i % random.randint(8, 15) == 0:
                    self._human_delay(300, 600)

    def press_key(self, key: str, modifiers: int = 0):
        """Press a keyboard key (Enter, Tab, Escape, etc.)."""
        self._send("Input.dispatchKeyEvent", {
            "type": "keyDown",
            "key": key,
            "modifiers": modifiers,
        })
        self._human_delay(30, 80)
        self._send("Input.dispatchKeyEvent", {
            "type": "keyUp",
            "key": key,
            "modifiers": modifiers,
        })

    # ── Scroll ────────────────────────────────────────────────────

    def scroll_wheel(self, delta_y: int = 300, delta_x: int = 0,
                     x: int = None, y: int = None):
        """Scroll via mouse wheel input. Positive delta_y = scroll down."""
        x = x if x is not None else self.cur_x
        y = y if y is not None else self.cur_y
        # Add slight randomness to scroll amount
        actual_dy = delta_y + random.randint(-20, 20)
        self._send("Input.dispatchMouseEvent", {
            "type": "mouseWheel",
            "x": x, "y": y,
            "deltaX": delta_x, "deltaY": actual_dy,
        })
        self._human_delay(200, 500)

    # ── Screenshot ────────────────────────────────────────────────

    def take_screenshot(self) -> str:
        """Capture viewport screenshot as JPEG, save to file, return path.

        Returns:
            File path (e.g. '/tmp/li_screenshots/shot_0001.jpg') or "" on failure.
        """
        result = self._send("Page.captureScreenshot", {
            "format": "jpeg", "quality": 80
        })
        data = result.get("result", {}).get("data", "")
        if not data:
            return ""
        self._screenshot_count += 1
        path = os.path.join(
            self._screenshot_dir,
            f"shot_{self._screenshot_count:04d}.jpg"
        )
        with open(path, 'wb') as f:
            f.write(base64.b64decode(data))
        self._resize_screenshot(path)
        self._cleanup_old_screenshots()
        return path

    def take_screenshot_base64(self) -> str:
        """Capture viewport screenshot as base64 PNG (legacy/backward compat)."""
        result = self._send("Page.captureScreenshot", {"format": "png"})
        return result.get("result", {}).get("data", "")

    def _cleanup_old_screenshots(self):
        """Keep only the last N screenshots in the screenshot directory."""
        files = sorted(globmod.glob(os.path.join(self._screenshot_dir, "shot_*.jpg")))
        if len(files) > self._screenshot_max_keep:
            for f in files[:-self._screenshot_max_keep]:
                try:
                    os.remove(f)
                except OSError:
                    pass

    @staticmethod
    def _resize_screenshot(path: str, max_dim: int = MAX_SCREENSHOT_DIM) -> bool:
        """Resize screenshot if any dimension exceeds max_dim. Uses macOS sips.

        Returns True if resized, False if no resize needed or on error.
        """
        try:
            result = subprocess.run(
                ["sips", "-g", "pixelWidth", "-g", "pixelHeight", path],
                capture_output=True, text=True, timeout=5,
            )
            lines = result.stdout.strip().split("\n")
            w = h = 0
            for line in lines:
                if "pixelWidth" in line:
                    w = int(line.split(":")[-1].strip())
                elif "pixelHeight" in line:
                    h = int(line.split(":")[-1].strip())
            if w <= max_dim and h <= max_dim:
                return False
            if w >= h:
                subprocess.run(
                    ["sips", "--resampleWidth", str(max_dim), path],
                    capture_output=True, timeout=10,
                )
            else:
                subprocess.run(
                    ["sips", "--resampleHeight", str(max_dim), path],
                    capture_output=True, timeout=10,
                )
            return True
        except (subprocess.TimeoutExpired, OSError, ValueError):
            return False

    def save_screenshot(self, path: str, safe_dir: str = None) -> bool:
        """Take screenshot and save to specific path. Returns True on success.

        Args:
            path: File path for saving the screenshot.
            safe_dir: Allowed base directory (defaults to /tmp/li_screenshots).

        Raises:
            ValueError: If path contains traversal or is outside safe_dir.
        """
        if not self._is_safe_path(path, safe_dir):
            raise ValueError(
                f"Unsafe screenshot path: '{path}'. "
                "Path must be within the allowed directory and must not contain '..'."
            )

        result = self._send("Page.captureScreenshot", {
            "format": "jpeg", "quality": 80
        })
        data = result.get("result", {}).get("data", "")
        if data:
            with open(path, 'wb') as f:
                f.write(base64.b64decode(data))
            self._resize_screenshot(path)
            return True
        return False

    # ── Navigation ────────────────────────────────────────────────

    def navigate_to(self, url: str, wait_seconds: int = 8,
                    reconnect_pattern: str = None) -> bool:
        """Navigate to URL, wait for load, reconnect WebSocket.

        Args:
            url: Target URL (must be https://www.linkedin.com/ or https://linkedin.com/)
            wait_seconds: Seconds to wait for page load
            reconnect_pattern: URL pattern for reconnection (auto-detected if None)

        Raises:
            ValueError: If the URL is not a safe LinkedIn URL.
        """
        if not self._is_safe_url(url):
            raise ValueError(
                f"Unsafe URL: '{url}'. "
                "Only https://www.linkedin.com/ and https://linkedin.com/ URLs are allowed."
            )

        result = self._send("Page.navigate", {"url": url})
        if result.get("error"):
            print(f"✗ Navigation failed: {result.get('error')}")
            return False

        time.sleep(wait_seconds)

        # Auto-detect reconnect pattern from URL
        if reconnect_pattern is None:
            if "/in/" in url:
                reconnect_pattern = "/in/"
            elif "/company/" in url:
                reconnect_pattern = "/company/"
            elif "/messaging" in url:
                reconnect_pattern = "messaging"
            elif "/search" in url:
                reconnect_pattern = "/search"
            elif "/mynetwork" in url:
                reconnect_pattern = "mynetwork"
            else:
                reconnect_pattern = "linkedin.com"

        return self.reconnect_to_tab(reconnect_pattern)

    def wait_for_page(self, seconds: float = 3.0) -> str:
        """Wait for page to stabilize, return screenshot file path."""
        time.sleep(seconds)
        return self.take_screenshot()

    # ── Convenience ───────────────────────────────────────────────

    def click_at(self, x: int, y: int, wait: float = 1.5) -> str:
        """Click at coordinates and return screenshot file path.

        Args:
            x, y: Click coordinates
            wait: Seconds to wait after click before screenshot

        Returns:
            Screenshot file path
        """
        self._click(x, y)
        self._human_delay(int(wait * 800), int(wait * 1200))
        return self.take_screenshot()

    def type_and_screenshot(self, text: str, wait: float = 1.0) -> str:
        """Type text and return screenshot file path.

        Args:
            text: Text to type
            wait: Seconds to wait after typing

        Returns:
            Screenshot file path
        """
        self.type_text(text)
        self._human_delay(int(wait * 800), int(wait * 1200))
        return self.take_screenshot()

    def scroll_and_screenshot(self, delta_y: int = 600, wait: float = 2.0) -> str:
        """Scroll and return screenshot file path.

        Args:
            delta_y: Scroll amount (positive = down)
            wait: Seconds to wait after scroll

        Returns:
            Screenshot file path
        """
        self.scroll_wheel(delta_y=delta_y)
        time.sleep(wait)
        return self.take_screenshot()

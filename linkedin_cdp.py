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
import json
import math
import random
import time
from typing import Optional

import requests
import websocket

CDP_PORT = 9222


class LinkedInBot:
    """LinkedIn automation via CDP Input domain + screenshots."""

    def __init__(self, port: int = CDP_PORT):
        self.port = port
        self.ws: Optional[websocket.WebSocket] = None
        self.ws_url: Optional[str] = None
        self.msg_id = 0
        # Cursor position tracking (randomized start)
        self.cur_x = random.randint(400, 700)
        self.cur_y = random.randint(250, 450)

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
            print(f"✓ Connected to: {li_tab.get('title', 'Unknown')[:50]}")
            return True

        except Exception as e:
            print(f"✗ Connection failed: {e}")
            return False

    def _send(self, method: str, params: dict = None) -> dict:
        """Send CDP command and return result."""
        self.msg_id += 1
        msg = {"id": self.msg_id, "method": method, "params": params or {}}
        self.ws.send(json.dumps(msg))

        target_id = self.msg_id
        timeout_count = 0
        while timeout_count < 50:
            try:
                resp = json.loads(self.ws.recv())
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
                except Exception:
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
        except Exception as e:
            print(f"  Warning: reconnect failed: {e}")
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
        """Capture viewport screenshot. Returns base64-encoded PNG."""
        result = self._send("Page.captureScreenshot", {"format": "png"})
        return result.get("result", {}).get("data", "")

    def save_screenshot(self, path: str) -> bool:
        """Take screenshot and save to file. Returns True on success."""
        data = self.take_screenshot()
        if data:
            with open(path, 'wb') as f:
                f.write(base64.b64decode(data))
            return True
        return False

    # ── Navigation ────────────────────────────────────────────────

    def navigate_to(self, url: str, wait_seconds: int = 8,
                    reconnect_pattern: str = None) -> bool:
        """Navigate to URL, wait for load, reconnect WebSocket.

        Args:
            url: Target URL
            wait_seconds: Seconds to wait for page load
            reconnect_pattern: URL pattern for reconnection (auto-detected if None)
        """
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
        """Wait for page to stabilize, return screenshot."""
        time.sleep(seconds)
        return self.take_screenshot()

    # ── Convenience ───────────────────────────────────────────────

    def click_at(self, x: int, y: int, wait: float = 1.5) -> str:
        """Click at coordinates and return screenshot of result.

        Args:
            x, y: Click coordinates
            wait: Seconds to wait after click before screenshot

        Returns:
            base64 PNG screenshot
        """
        self._click(x, y)
        self._human_delay(int(wait * 800), int(wait * 1200))
        return self.take_screenshot()

    def type_and_screenshot(self, text: str, wait: float = 1.0) -> str:
        """Type text and return screenshot.

        Args:
            text: Text to type
            wait: Seconds to wait after typing

        Returns:
            base64 PNG screenshot
        """
        self.type_text(text)
        self._human_delay(int(wait * 800), int(wait * 1200))
        return self.take_screenshot()

    def scroll_and_screenshot(self, delta_y: int = 600, wait: float = 2.0) -> str:
        """Scroll and return screenshot.

        Args:
            delta_y: Scroll amount (positive = down)
            wait: Seconds to wait after scroll

        Returns:
            base64 PNG screenshot
        """
        self.scroll_wheel(delta_y=delta_y)
        time.sleep(wait)
        return self.take_screenshot()

"""
LinkedIn Messages Collector — human-like mouse navigation via CDP Input domain.

Navigates through conversations using Bezier curve mouse movements,
random delays, and micro-jitter to avoid detection.

Usage:
    from linkedin_messages import LinkedInMessages

    lm = LinkedInMessages()
    lm.connect()
    conversations = lm.collect_recent_conversations(count=5)
    lm.close()
"""

import json
import math
import random
import time
import websocket
import requests


class LinkedInMessages:
    def __init__(self, cdp_port=9222):
        self.cdp_port = cdp_port
        self.ws = None
        self.msg_id = 1
        self.cur_x = random.randint(400, 700)
        self.cur_y = random.randint(250, 450)

    # ── CDP core ──────────────────────────────────────────────

    def connect(self):
        """Find LinkedIn messaging tab and connect via WebSocket."""
        tabs = requests.get(f"http://localhost:{self.cdp_port}/json").json()
        for tab in tabs:
            if "linkedin.com" in tab.get("url", ""):
                ws_url = tab.get("webSocketDebuggerUrl")
                if ws_url:
                    self.ws = websocket.create_connection(ws_url, timeout=30)
                    return True
        return False

    def close(self):
        if self.ws:
            self.ws.close()
            self.ws = None

    def _send(self, method, params=None):
        cmd = {"id": self.msg_id, "method": method, "params": params or {}}
        self.ws.send(json.dumps(cmd))
        while True:
            resp = json.loads(self.ws.recv())
            if resp.get("id") == self.msg_id:
                self.msg_id += 1
                return resp

    def _js(self, expression):
        resp = self._send("Runtime.evaluate", {
            "expression": expression,
            "returnByValue": True,
        })
        return resp["result"]["result"].get("value")

    def reconnect_to_tab(self, pattern="linkedin.com"):
        """Reconnect WebSocket after navigation invalidates it."""
        if self.ws:
            try:
                self.ws.close()
            except Exception:
                pass
        time.sleep(1)
        tabs = requests.get(f"http://localhost:{self.cdp_port}/json").json()
        for tab in tabs:
            if pattern in tab.get("url", ""):
                ws_url = tab.get("webSocketDebuggerUrl")
                if ws_url:
                    self.ws = websocket.create_connection(ws_url, timeout=30)
                    return True
        return False

    # ── Human-like mouse ──────────────────────────────────────

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
        """Generate mouse path with random Bezier curve + micro-jitter."""
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
        pts = []
        for i in range(steps + 1):
            t = i / steps
            t = t * t * (3 - 2 * t)  # ease in-out
            px, py = self._bezier((sx, sy), cp1, cp2, (ex, ey), t)
            px += random.gauss(0, 0.7)  # hand tremor
            py += random.gauss(0, 0.7)
            pts.append((int(px), int(py)))
        return pts

    def _move_to(self, x, y):
        """Move mouse to target with human-like trajectory."""
        tx = x + random.randint(-3, 3)
        ty = y + random.randint(-3, 3)
        path = self._human_path(self.cur_x, self.cur_y, tx, ty)
        for px, py in path:
            self._send("Input.dispatchMouseEvent", {
                "type": "mouseMoved", "x": px, "y": py, "button": "none",
            })
            time.sleep(random.uniform(0.004, 0.022))
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
            self._move_to(self.cur_x, fake_y)
            time.sleep(random.uniform(0.1, 0.3))

    # ── Conversation list ─────────────────────────────────────

    def _get_conversation_coords(self, limit=10):
        """Get screen coordinates + names of visible conversations."""
        js = f"""(function() {{
            var ul = document.querySelector('ul.msg-conversations-container__conversations-list');
            if (!ul) return JSON.stringify({{error: 'no conversation list'}});
            var items = ul.querySelectorAll('li');
            var result = [];
            for (var i = 1; i < items.length && result.length < {limit}; i++) {{
                var li = items[i];
                var rect = li.getBoundingClientRect();
                var nameEl = li.querySelector('h3 span');
                var name = nameEl ? nameEl.innerText.trim() : '';
                var timeEl = li.querySelector('time');
                var t = timeEl ? timeEl.innerText.trim() : '';
                var snippetEl = li.querySelector('.msg-conversation-card__message-snippet-body')
                             || li.querySelector('p.msg-conversation-card__message-snippet');
                var snippet = snippetEl ? snippetEl.innerText.trim() : '';
                if (rect.height > 0 && name) {{
                    result.push({{
                        index: i,
                        name: name.substring(0, 60),
                        time: t,
                        snippet: snippet.substring(0, 100),
                        x: Math.round(rect.left + rect.width / 2),
                        y: Math.round(rect.top + rect.height / 2),
                        w: Math.round(rect.width),
                        h: Math.round(rect.height)
                    }});
                }}
            }}
            return JSON.stringify(result);
        }})()"""
        return json.loads(self._js(js))

    # ── Message reading ───────────────────────────────────────

    def _read_current_thread(self, last_n=5):
        """Read messages from currently open conversation thread."""
        js = f"""(function() {{
            var events = document.querySelectorAll('li.msg-s-message-list__event');
            var result = [];
            for (var i = 0; i < events.length; i++) {{
                var ev = events[i];
                var senderEl = ev.querySelector(
                    '.msg-s-message-group__name, .msg-s-message-group__profile-link'
                );
                var sender = senderEl ? senderEl.innerText.trim() : '';
                var timeEl = ev.querySelector('time');
                var t = timeEl ? timeEl.innerText.trim() : '';
                var bodies = ev.querySelectorAll('.msg-s-event-listitem__body');
                var msgs = [];
                for (var j = 0; j < bodies.length; j++) {{
                    msgs.push(bodies[j].innerText.trim().substring(0, 400));
                }}
                if (msgs.length > 0) result.push({{sender: sender, time: t, messages: msgs}});
            }}
            return JSON.stringify({{total: result.length, last: result.slice(-{last_n})}});
        }})()"""
        return json.loads(self._js(js))

    # ── Main API ──────────────────────────────────────────────

    def ensure_messaging_page(self):
        """Navigate to LinkedIn messaging if not already there."""
        url = self._js("window.location.href")
        if "/messaging" not in url:
            self._send("Page.navigate", {"url": "https://www.linkedin.com/messaging/"})
            time.sleep(3)
            self.reconnect_to_tab("linkedin.com/messaging")
            time.sleep(2)
        return True

    def list_conversations(self, limit=10):
        """List visible conversations with names, times, and snippets."""
        self.ensure_messaging_page()
        coords = self._get_conversation_coords(limit)
        return [
            {"name": c["name"], "time": c["time"], "snippet": c["snippet"]}
            for c in coords
        ]

    def collect_recent_conversations(self, count=5, messages_per_convo=5):
        """
        Navigate through the last N conversations using human-like mouse,
        and collect recent messages from each.

        Returns:
            list of dicts: [{name, time, total, messages: [{sender, time, text}]}]
        """
        self.ensure_messaging_page()
        time.sleep(random.uniform(0.5, 1.0))

        coords = self._get_conversation_coords(limit=count + 1)
        if isinstance(coords, dict) and "error" in coords:
            return {"error": coords["error"]}

        results = []
        for i, conv in enumerate(coords[:count]):
            name = conv["name"]

            # Random offset within clickable area
            cx = conv["x"] + random.randint(-conv["w"] // 5, conv["w"] // 5)
            cy = conv["y"] + random.randint(-conv["h"] // 6, conv["h"] // 6)

            # Occasional fake hover (human imprecision)
            if i > 0:
                self._maybe_fake_hover(cy)

            self._click(cx, cy)

            # Wait for thread to load (variable)
            time.sleep(random.uniform(1.8, 3.0))

            # Read messages
            thread = self._read_current_thread(last_n=messages_per_convo)

            messages = []
            for m in thread.get("last", []):
                for txt in m["messages"]:
                    messages.append({
                        "sender": m["sender"],
                        "time": m["time"],
                        "text": " ".join(txt.split()),
                    })

            results.append({
                "name": name,
                "time": conv["time"],
                "total_messages": thread.get("total", 0),
                "messages": messages,
            })

            # Human reading pause between conversations
            if i < count - 1:
                time.sleep(random.uniform(0.5, 1.5))

        return results

    def read_conversation(self, name, last_n=10):
        """
        Find and open a specific conversation by name, return messages.

        Uses click-based navigation. Returns None if not found in visible list.
        """
        self.ensure_messaging_page()
        coords = self._get_conversation_coords(limit=20)

        target = None
        for c in coords:
            if name.lower() in c["name"].lower():
                target = c
                break

        if not target:
            return None

        cx = target["x"] + random.randint(-3, 3)
        cy = target["y"] + random.randint(-3, 3)
        self._click(cx, cy)
        time.sleep(random.uniform(2.0, 3.0))

        thread = self._read_current_thread(last_n=last_n)
        messages = []
        for m in thread.get("last", []):
            for txt in m["messages"]:
                messages.append({
                    "sender": m["sender"],
                    "time": m["time"],
                    "text": " ".join(txt.split()),
                })

        return {
            "name": target["name"],
            "total_messages": thread.get("total", 0),
            "messages": messages,
        }

#!/usr/bin/env python3
"""
LinkedIn automation via Chrome DevTools Protocol.
Human-like behavior to avoid detection.
"""
import json
import time
import random
import requests
from typing import Optional, Any
import websocket

CDP_PORT = 9222


class LinkedInBot:
    """LinkedIn messaging bot using Chrome DevTools Protocol."""
    
    def __init__(self, port: int = CDP_PORT):
        self.port = port
        self.ws: Optional[websocket.WebSocket] = None
        self.ws_url: Optional[str] = None
        self.msg_id = 0
        
    def connect(self) -> bool:
        """Connect to Chrome via CDP."""
        try:
            # Get available tabs
            resp = requests.get(f"http://localhost:{self.port}/json", timeout=5)
            tabs = resp.json()

            # Find LinkedIn tab in priority order
            li_tab = None

            # Priority 1: messaging tab
            for tab in tabs:
                url = tab.get("url", "")
                if "linkedin.com/messaging" in url:
                    li_tab = tab
                    break

            # Priority 2: any main LinkedIn page (not iframes/widgets)
            if not li_tab:
                for tab in tabs:
                    url = tab.get("url", "")
                    if "linkedin.com" in url:
                        # Skip internal/iframe pages
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

            # Connect WebSocket with longer timeout
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
        msg = {
            "id": self.msg_id,
            "method": method,
            "params": params or {}
        }
        self.ws.send(json.dumps(msg))
        
        # Wait for response (skip events)
        target_id = self.msg_id
        timeout_count = 0
        while timeout_count < 50:  # Max 50 attempts
            try:
                resp = json.loads(self.ws.recv())
                if resp.get("id") == target_id:
                    return resp
                # Skip events (no id field)
            except websocket.WebSocketTimeoutException:
                timeout_count += 1
                time.sleep(0.1)
        
        return {"error": "timeout"}
    
    def _human_delay(self, min_ms: int = 100, max_ms: int = 400):
        """Random delay like a human."""
        time.sleep(random.uniform(min_ms / 1000, max_ms / 1000))
    
    def _evaluate(self, expression: str) -> Any:
        """Execute JavaScript and return result."""
        result = self._send("Runtime.evaluate", {
            "expression": expression,
            "returnByValue": True
        })
        return result.get("result", {}).get("result", {}).get("value")
    
    def find_element(self, selector: str) -> Optional[dict]:
        """Find element by CSS selector, return its nodeId."""
        # Get document root
        doc = self._send("DOM.getDocument")
        root_id = doc.get("result", {}).get("root", {}).get("nodeId")
        
        if not root_id:
            return None
        
        # Query selector
        result = self._send("DOM.querySelector", {
            "nodeId": root_id,
            "selector": selector
        })
        
        node_id = result.get("result", {}).get("nodeId")
        if node_id and node_id != 0:
            return {"nodeId": node_id}
        return None
    
    def get_element_box(self, node_id: int) -> Optional[dict]:
        """Get element bounding box for clicking."""
        result = self._send("DOM.getBoxModel", {"nodeId": node_id})
        content = result.get("result", {}).get("model", {}).get("content")
        
        if content and len(content) >= 4:
            # content is [x1,y1, x2,y1, x2,y2, x1,y2]
            x = (content[0] + content[2]) / 2
            y = (content[1] + content[5]) / 2
            return {"x": x, "y": y}
        return None
    
    def click_element(self, selector: str, timeout: int = 5) -> bool:
        """Click element by selector with human-like behavior."""
        start = time.time()
        
        while time.time() - start < timeout:
            elem = self.find_element(selector)
            if elem:
                box = self.get_element_box(elem["nodeId"])
                if box:
                    x, y = box["x"], box["y"]
                    
                    # Human: move mouse first
                    self._send("Input.dispatchMouseEvent", {
                        "type": "mouseMoved",
                        "x": x + random.randint(-5, 5),
                        "y": y + random.randint(-5, 5)
                    })
                    self._human_delay(50, 150)
                    
                    # Click down
                    self._send("Input.dispatchMouseEvent", {
                        "type": "mousePressed",
                        "x": x,
                        "y": y,
                        "button": "left",
                        "clickCount": 1
                    })
                    self._human_delay(30, 80)
                    
                    # Click up
                    self._send("Input.dispatchMouseEvent", {
                        "type": "mouseReleased",
                        "x": x,
                        "y": y,
                        "button": "left",
                        "clickCount": 1
                    })
                    
                    self._human_delay(100, 300)
                    return True
            
            time.sleep(0.3)
        
        print(f"✗ Element not found: {selector}")
        return False
    
    def type_text(self, text: str, human_like: bool = True):
        """Type text character by character like a human."""
        for i, char in enumerate(text):
            self._send("Input.insertText", {"text": char})
            
            if human_like:
                # Human typing speed: ~40-60 WPM = 200-300ms per char average
                if char in " ":
                    self._human_delay(150, 350)  # Longer pause at spaces
                elif char in ".,!?":
                    self._human_delay(200, 450)  # Thinking pause at punctuation
                elif char in "ABCDEFGHIJKLMNOPQRSTUVWXYZ":
                    self._human_delay(120, 280)  # Shift key takes time
                else:
                    self._human_delay(80, 200)  # Normal typing
                
                # Occasional longer pause (thinking)
                if i > 0 and i % random.randint(8, 15) == 0:
                    self._human_delay(300, 600)
    
    def focus_message_input(self) -> bool:
        """Focus the LinkedIn message input field."""
        selectors = [
            'div.msg-form__contenteditable[contenteditable="true"]',
            'div[role="textbox"][contenteditable="true"]',
            'div[data-placeholder="Write a message…"]',
            '.msg-form__contenteditable',
        ]
        
        for selector in selectors:
            if self.click_element(selector, timeout=2):
                self._human_delay(200, 400)
                return True
        
        return False
    
    def send_message(self, text: str) -> bool:
        """Send a message in the currently open conversation."""
        print(f"  Focusing input...")
        if not self.focus_message_input():
            print("✗ Could not focus message input")
            return False
        
        # Pause before typing like a human reading the conversation
        self._human_delay(800, 1500)
        
        print(f"  Typing message...")
        self.type_text(text)
        
        # Pause after typing to "review" the message
        self._human_delay(600, 1200)
        
        # Click Send button (more reliable than Enter)
        print(f"  Sending...")
        send_selectors = [
            'button.msg-form__send-button',
            'button[type="submit"]',
        ]
        for sel in send_selectors:
            if self.click_element(sel, timeout=2):
                break
        
        self._human_delay(500, 1000)
        print("✓ Message sent")
        return True
    
    def click_conversation(self, index: int) -> bool:
        """Click on conversation by index (1-based)."""
        selector = f'.msg-conversations-container__conversations-list > li:nth-child({index})'
        return self.click_element(selector)
    
    def close(self):
        """Close WebSocket connection."""
        if self.ws:
            self.ws.close()


def main():
    """Test the bot."""
    bot = LinkedInBot()
    
    if not bot.connect():
        print("Failed to connect to Chrome")
        return
    
    # Test: send message in current conversation
    print("\nSending test message...")
    bot.send_message("Test message from CDP bot")
    
    bot.close()


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
LinkedIn connection request management via CDP.
"""
import time
import json
from typing import Dict, Any, List, Optional
from linkedin_cdp import LinkedInBot
from rate_limiter import RateLimiter


class LinkedInConnect(LinkedInBot):
    """LinkedIn connection request functionality."""

    INVITATIONS_URL = "https://www.linkedin.com/mynetwork/invitation-manager/"
    SENT_INVITATIONS_URL = "https://www.linkedin.com/mynetwork/invitation-manager/sent/"

    def __init__(self, use_rate_limiter: bool = True):
        super().__init__()
        self.limiter = RateLimiter() if use_rate_limiter else None

    def navigate_to(self, url: str) -> bool:
        """Navigate to a URL and reconnect to the tab."""
        import requests
        import websocket

        result = self._send("Page.navigate", {"url": url})
        if result.get("error"):
            print(f"✗ Navigation failed: {result.get('error')}")
            return False

        # Wait for page load
        time.sleep(8)

        # Reconnect to the tab after navigation
        try:
            resp = requests.get(f"http://localhost:{self.port}/json", timeout=5)
            tabs = resp.json()

            # Find the matching tab
            target_tab = None
            for tab in tabs:
                tab_url = tab.get("url", "")
                if url.split('?')[0] in tab_url or ("/in/" in tab_url and "/in/" in url):
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

    def _wait_for_profile(self, timeout: int = 15) -> bool:
        """Wait for profile page to load."""
        start = time.time()
        while time.time() - start < timeout:
            result = self._evaluate('''
                document.querySelector('h1') !== null &&
                document.body.innerText.length > 1000
            ''')
            if result:
                self._human_delay(500, 1000)
                return True
            time.sleep(0.5)
        return False

    def send_request(
        self,
        profile_url: str,
        note: Optional[str] = None
    ) -> bool:
        """
        Send a connection request to a profile.

        Args:
            profile_url: LinkedIn profile URL
            note: Optional personalized note (max 300 chars)

        Returns:
            True if request sent successfully
        """
        if self.limiter:
            if not self.limiter.can_send_connection():
                print("✗ Daily connection request limit reached")
                return False
            self.limiter.wait_if_needed('connection_requests')

        # Normalize URL
        if not profile_url.startswith('http'):
            profile_url = f"https://www.linkedin.com/in/{profile_url}"

        print(f"🔗 Sending connection request: {profile_url}")
        if not self.navigate_to(profile_url):
            return False

        if not self._wait_for_profile():
            print("✗ Profile page failed to load")
            return False

        # Check if already connected
        is_connected = self._evaluate('''
            document.querySelector('.dist-value')?.innerText === '1st' ||
            document.querySelector('.pvs-profile-actions__action--message') !== null
        ''')

        if is_connected:
            print("✓ Already connected")
            return True

        # Check for pending request
        is_pending = self._evaluate('''
            document.querySelector('button[aria-label*="Pending"]') !== null ||
            document.querySelector('.pvs-profile-actions button')?.innerText.includes('Pending')
        ''')

        if is_pending:
            print("⏳ Connection request already pending")
            return True

        # Find and click Connect button
        clicked = self._evaluate('''
            (() => {
                // Try main Connect button
                const connectBtn = document.querySelector('button[aria-label*="connect" i]') ||
                                  Array.from(document.querySelectorAll('.pvs-profile-actions button'))
                                      .find(b => b.innerText.toLowerCase().includes('connect'));
                if (connectBtn) {
                    connectBtn.click();
                    return true;
                }

                // Try More button first, then Connect
                const moreBtn = document.querySelector('button[aria-label="More actions"]');
                if (moreBtn) {
                    moreBtn.click();
                    return 'more';
                }
                return false;
            })()
        ''')

        if clicked == 'more':
            self._human_delay(500, 1000)
            # Click Connect in dropdown
            self._evaluate('''
                const connectItem = Array.from(document.querySelectorAll('.artdeco-dropdown__item'))
                    .find(item => item.innerText.toLowerCase().includes('connect'));
                if (connectItem) connectItem.click();
            ''')
            clicked = True

        if not clicked:
            print("✗ Connect button not found")
            return False

        self._human_delay(500, 1000)

        # Handle the connection modal
        if note:
            # Click "Add a note" button
            add_note_clicked = self._evaluate('''
                (() => {
                    const addNoteBtn = document.querySelector('button[aria-label="Add a note"]') ||
                                      Array.from(document.querySelectorAll('.artdeco-modal button'))
                                          .find(b => b.innerText.toLowerCase().includes('add a note'));
                    if (addNoteBtn) {
                        addNoteBtn.click();
                        return true;
                    }
                    return false;
                })()
            ''')

            if add_note_clicked:
                self._human_delay(500, 1000)

                # Type the note
                note_text = note[:300]  # LinkedIn limit
                self._evaluate(f'''
                    const textarea = document.querySelector('textarea[name="message"]') ||
                                    document.querySelector('.connect-button-send-invite__custom-message');
                    if (textarea) {{
                        textarea.focus();
                        textarea.value = {json.dumps(note_text)};
                        textarea.dispatchEvent(new Event('input', {{ bubbles: true }}));
                    }}
                ''')
                self._human_delay(300, 600)

        # Click Send button
        self._human_delay(500, 1000)
        sent = self._evaluate('''
            (() => {
                const sendBtn = document.querySelector('button[aria-label="Send invitation"]') ||
                               document.querySelector('button[aria-label="Send now"]') ||
                               Array.from(document.querySelectorAll('.artdeco-modal button'))
                                   .find(b => b.innerText.toLowerCase() === 'send');
                if (sendBtn) {
                    sendBtn.click();
                    return true;
                }
                return false;
            })()
        ''')

        if self.limiter:
            self.limiter.record_connection_request()

        if sent:
            print("✓ Connection request sent")
            return True
        else:
            print("✗ Failed to send request")
            return False

    def withdraw_request(self, profile_url: str) -> bool:
        """
        Withdraw a pending connection request.

        Args:
            profile_url: LinkedIn profile URL

        Returns:
            True if request withdrawn successfully
        """
        if not profile_url.startswith('http'):
            profile_url = f"https://www.linkedin.com/in/{profile_url}"

        print(f"↩️ Withdrawing request: {profile_url}")
        if not self.navigate_to(profile_url):
            return False

        if not self._wait_for_profile():
            return False

        # Find and click Pending button
        clicked = self._evaluate('''
            (() => {
                const pendingBtn = document.querySelector('button[aria-label*="Pending"]') ||
                                  Array.from(document.querySelectorAll('.pvs-profile-actions button'))
                                      .find(b => b.innerText.includes('Pending'));
                if (pendingBtn) {
                    pendingBtn.click();
                    return true;
                }
                return false;
            })()
        ''')

        if not clicked:
            print("✗ No pending request found")
            return False

        self._human_delay(500, 1000)

        # Confirm withdrawal
        withdrawn = self._evaluate('''
            (() => {
                const withdrawBtn = document.querySelector('button[aria-label*="Withdraw"]') ||
                                   Array.from(document.querySelectorAll('.artdeco-modal button'))
                                       .find(b => b.innerText.toLowerCase().includes('withdraw'));
                if (withdrawBtn) {
                    withdrawBtn.click();
                    return true;
                }
                return false;
            })()
        ''')

        if withdrawn:
            print("✓ Request withdrawn")
            return True
        else:
            print("✗ Failed to withdraw")
            return False

    def accept_request(self, name: str) -> bool:
        """
        Accept an incoming connection request by name.

        Args:
            name: Name of the person (partial match)

        Returns:
            True if request accepted successfully
        """
        if self.limiter:
            if not self.limiter.can_accept_connection():
                print("✗ Daily accept limit reached")
                return False
            self.limiter.wait_if_needed('connection_accepts')

        print(f"✓ Accepting request from: {name}")

        # Navigate to invitations
        if not self.navigate_to(self.INVITATIONS_URL):
            return False

        self._human_delay(1000, 2000)

        # Find and accept the invitation
        accepted = self._evaluate(f'''
            (() => {{
                const searchName = {json.dumps(name.lower())};
                const items = document.querySelectorAll('.invitation-card');

                for (const item of items) {{
                    const nameEl = item.querySelector('.invitation-card__title');
                    if (nameEl && nameEl.innerText.toLowerCase().includes(searchName)) {{
                        const acceptBtn = item.querySelector('button[aria-label*="Accept"]');
                        if (acceptBtn) {{
                            acceptBtn.click();
                            return true;
                        }}
                    }}
                }}
                return false;
            }})()
        ''')

        if self.limiter:
            self.limiter.record_connection_accept()

        if accepted:
            print("✓ Request accepted")
            return True
        else:
            print("✗ Request not found")
            return False

    def get_pending_invitations(self) -> List[Dict[str, str]]:
        """
        Get list of pending incoming invitations.

        Returns:
            List of dicts with name, title, profile_url
        """
        print("📥 Getting pending invitations...")
        if not self.navigate_to(self.INVITATIONS_URL):
            return []

        self._human_delay(1000, 2000)

        invitations = self._evaluate('''
            (() => {
                const items = [];
                const cards = document.querySelectorAll('.invitation-card');

                cards.forEach(card => {
                    const nameEl = card.querySelector('.invitation-card__title');
                    const titleEl = card.querySelector('.invitation-card__subtitle');
                    const linkEl = card.querySelector('a[href*="/in/"]');

                    if (nameEl) {
                        items.push({
                            name: nameEl.innerText.trim(),
                            title: titleEl ? titleEl.innerText.trim() : '',
                            profile_url: linkEl ? linkEl.href.split('?')[0] : ''
                        });
                    }
                });

                return JSON.stringify(items);
            })()
        ''')

        try:
            result = json.loads(invitations) if invitations else []
            print(f"✓ Found {len(result)} pending invitations")
            return result
        except json.JSONDecodeError:
            return []

    def get_sent_invitations(self) -> List[Dict[str, str]]:
        """
        Get list of sent pending invitations.

        Returns:
            List of dicts with name, title, profile_url, sent_date
        """
        print("📤 Getting sent invitations...")
        if not self.navigate_to(self.SENT_INVITATIONS_URL):
            return []

        self._human_delay(1000, 2000)

        invitations = self._evaluate('''
            (() => {
                const items = [];
                const cards = document.querySelectorAll('.invitation-card');

                cards.forEach(card => {
                    const nameEl = card.querySelector('.invitation-card__title');
                    const titleEl = card.querySelector('.invitation-card__subtitle');
                    const linkEl = card.querySelector('a[href*="/in/"]');
                    const timeEl = card.querySelector('time');

                    if (nameEl) {
                        items.push({
                            name: nameEl.innerText.trim(),
                            title: titleEl ? titleEl.innerText.trim() : '',
                            profile_url: linkEl ? linkEl.href.split('?')[0] : '',
                            sent_date: timeEl ? timeEl.getAttribute('datetime') : ''
                        });
                    }
                });

                return JSON.stringify(items);
            })()
        ''')

        try:
            result = json.loads(invitations) if invitations else []
            print(f"✓ Found {len(result)} sent invitations")
            return result
        except json.JSONDecodeError:
            return []

    def accept_all_invitations(self, limit: int = 10) -> int:
        """
        Accept multiple pending invitations.

        Args:
            limit: Maximum invitations to accept

        Returns:
            Number of invitations accepted
        """
        invitations = self.get_pending_invitations()
        accepted = 0

        for inv in invitations[:limit]:
            if self.limiter and not self.limiter.can_accept_connection():
                print("✗ Daily accept limit reached")
                break

            if self.accept_request(inv['name']):
                accepted += 1
                self._human_delay(2000, 4000)

        print(f"✓ Accepted {accepted} invitations")
        return accepted


def main():
    """Test connection functionality."""
    connect = LinkedInConnect()

    if not connect.connect():
        print("Failed to connect")
        return

    print("\n=== Connection Manager ===")

    # List pending invitations
    pending = connect.get_pending_invitations()
    if pending:
        print("\nPending invitations:")
        for inv in pending:
            print(f"  • {inv['name']} - {inv['title']}")

    # Example: send connection request
    # connect.send_request("username", note="Hi! I'd love to connect.")

    connect.close()


if __name__ == "__main__":
    main()

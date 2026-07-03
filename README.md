# LinkedIn CDP Automation

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

LinkedIn automation toolkit using Chrome DevTools Protocol (CDP). Uses **screenshot-based** interaction with human-like behavior to avoid detection.

## Disclaimer

> **This tool is for educational and research purposes only.**
>
> - Use responsibly and in compliance with [LinkedIn's Terms of Service](https://www.linkedin.com/legal/user-agreement)
> - The author is not responsible for any misuse or account restrictions
> - Respect other users' privacy and LinkedIn's rate limits
> - Do not use for spam, harassment, or any malicious purposes

## Key Concept: Screenshot-Based Automation

This library does **not** parse the DOM or extract text from HTML. Instead:

1. All **actions** use CDP Input domain (mouse movements, keyboard input, scrolling)
2. All **data reading** uses `Page.captureScreenshot` -- the caller interprets screenshots visually (e.g., via an AI vision model)
3. **Zero DOM access** -- no `Runtime.evaluate`, no `querySelector`, no `innerText`

Screenshots are saved as **JPEG files** to `/tmp/li_screenshots/` and methods return **file paths** (not base64). The last 50 screenshots are kept automatically.

> **A vision model in the loop is required.** This library moves the mouse, types,
> and captures screenshots -- but it does **not** decide *where* to click. Methods
> like `click_at(x, y)` take pixel coordinates that a caller must supply by looking
> at the returned screenshot (e.g. GPT-4o, Claude, or a human). The design target is
> an agent loop: capture screenshot -> vision model reads it -> returns coordinates ->
> library acts -> repeat. It is not a fire-and-forget scraper.

## Features

| Feature | Status | Description |
|---------|--------|-------------|
| Send Messages | Done | Click input, type, press Enter in conversations |
| Read Messages | Done | Screenshot conversation threads |
| Search People | Done | Navigate to search results, return screenshots |
| Search Companies | Done | Navigate to company search results |
| View Profiles | Done | Screenshot profiles with scroll-and-capture |
| Connection Requests | Done | Screenshot-driven connect workflow |
| Rate Limiting | Done | Built-in daily limits and delays |
| Human-like Behavior | Done | Bezier mouse curves, random delays, typing jitter |

## How It Works

```
+------------------+     WebSocket      +------------------+
|  Python Script   | <----------------> |  Google Chrome   |
|  (linkedin_cdp)  |     CDP Protocol   |  (debugging on)  |
+------------------+                    +--------+---------+
                                                 |
                                                 v
                                        +------------------+
                                        |    LinkedIn      |
                                        |   (logged in)    |
                                        +------------------+
```

1. **Chrome** runs with `--remote-debugging-port=9222`
2. **Python script** connects to Chrome via WebSocket
3. Script sends **CDP commands** (mouse input, keyboard input, navigate, screenshot)
4. Chrome executes commands on LinkedIn page
5. Screenshots are saved as **JPEG files** for the caller to interpret
6. All mouse movements use **cubic Bezier curves** with randomized control points

## Installation

### 1. Clone the repository

```bash
git clone https://github.com/anthroos/linkedin-cdp.git
cd linkedin-cdp
```

### 2. Install dependencies

```bash
pip3 install -r requirements.txt
```

Or manually:
```bash
pip3 install websocket-client requests
```

### 3. Start Chrome with debugging

**Option A: Use the helper script**
```bash
chmod +x chrome_debug.sh
./chrome_debug.sh
```

**Option B: Manual start**
```bash
# macOS
open -a 'Google Chrome' --args \
    --remote-debugging-port=9222 \
    --remote-allow-origins=http://localhost,http://127.0.0.1 \
    --user-data-dir="$HOME/chrome-debug-profile"

# Linux
google-chrome \
    --remote-debugging-port=9222 \
    --remote-allow-origins=http://localhost,http://127.0.0.1 \
    --user-data-dir="$HOME/chrome-debug-profile"

# Windows
chrome.exe ^
    --remote-debugging-port=9222 ^
    --remote-allow-origins=http://localhost,http://127.0.0.1 ^
    --user-data-dir="%USERPROFILE%\chrome-debug-profile"
```

### 4. Login to LinkedIn

Open `https://www.linkedin.com` in the debug Chrome and log in. Your session will be saved.

### 5. Verify connection

```bash
curl -s http://localhost:9222/json/version | python3 -c "import sys,json; print(json.load(sys.stdin).get('Browser'))"
```

## Usage

### Quick Start

```python
from linkedin_messages import LinkedInMessages

lm = LinkedInMessages()
lm.connect()

# Screenshot the conversations list (returns file path)
screenshot_path = lm.screenshot_conversations()
# -> caller uses vision model to interpret the screenshot
# -> vision model returns coordinates of the conversation to click

# Open a conversation (caller provides coordinates from screenshot)
screenshot_path = lm.open_conversation(click_x=350, click_y=250)

# Send a message (caller provides input field coordinates from screenshot)
screenshot_path = lm.send_message(input_x=500, input_y=700, text="Hello!")

lm.close()
```

### Search for People

```python
from linkedin_search import LinkedInSearch

search = LinkedInSearch()
search.connect()

# Returns list of screenshot file paths (NOT dicts)
screenshots = search.search_people("AI Engineer San Francisco", scroll_pages=2)
# screenshots = ["/tmp/li_screenshots/shot_0001.jpg", ...]
# Caller interprets each screenshot visually

search.close()
```

### View Profile

```python
from linkedin_profile import LinkedInProfile

profile = LinkedInProfile()
profile.connect()

# Returns screenshot file path (NOT a dict)
screenshot = profile.view_profile("https://www.linkedin.com/in/username")

# Or capture full profile by scrolling
screenshots = profile.screenshot_full_profile(
    "https://www.linkedin.com/in/username",
    scroll_count=5
)

profile.close()
```

### Send Connection Request (Screenshot-Driven)

```python
from linkedin_connect import LinkedInConnect

conn = LinkedInConnect()
conn.connect()

# Step 1: View profile -- returns screenshot path
screenshot = conn.view_profile("https://www.linkedin.com/in/username")
# Caller reads screenshot to find Connect button coordinates

# Step 2: Click Connect button (coordinates from screenshot)
screenshot = conn.click_at(x=600, y=350)
# Caller reads screenshot to find "Add a note" button

# Step 3: Click "Add a note" (coordinates from screenshot)
screenshot = conn.click_at(x=400, y=500)
# Caller reads screenshot to find note textarea

# Step 4: Type note
screenshot = conn.send_connection_note(
    input_x=400, input_y=450,
    note="Hi! I'd love to connect."
)
# Caller reads screenshot to find Send button and clicks it

conn.close()
```

### Rate Limiting

```python
from rate_limiter import RateLimiter

limiter = RateLimiter()

# Check if action is allowed
if limiter.can_send_message():
    # ... send message ...
    limiter.record_message()
else:
    print(f"Daily limit reached. Resets in {limiter.time_until_reset()}")

# View current usage
print(limiter.get_stats())
```

## API Reference

### LinkedInBot (linkedin_cdp.py)

Base class for all LinkedIn automation. Handles CDP connection, human-like mouse/keyboard input, and screenshots.

| Method | Returns | Description |
|--------|---------|-------------|
| `connect()` | `bool` | Connect to Chrome via CDP WebSocket |
| `close()` | `None` | Close WebSocket connection |
| `reconnect_to_tab(url_pattern)` | `bool` | Reconnect WebSocket to a tab matching pattern |
| `navigate_to(url, wait_seconds=8, reconnect_pattern=None)` | `bool` | Navigate to URL (must be linkedin.com), wait, reconnect |
| `take_screenshot()` | `str` | Capture viewport as JPEG, return file path |
| `take_screenshot_base64()` | `str` | Capture viewport as base64 PNG (legacy) |
| `save_screenshot(path, safe_dir=None)` | `bool` | Save screenshot to file (path-validated) |
| `wait_for_page(seconds=3.0)` | `str` | Wait for page to stabilize, return screenshot path |
| `click_at(x, y, wait=1.5)` | `str` | Click at coordinates, return screenshot path |
| `type_text(text, human_like=True)` | `None` | Type text character by character |
| `type_and_screenshot(text, wait=1.0)` | `str` | Type text and return screenshot path |
| `press_key(key, modifiers=0)` | `None` | Press a keyboard key (Enter, Tab, Escape, etc.) |
| `scroll_wheel(delta_y=300, delta_x=0, x=None, y=None)` | `None` | Scroll via mouse wheel |
| `scroll_and_screenshot(delta_y=600, wait=2.0)` | `str` | Scroll and return screenshot path |

### LinkedInMessages (linkedin_messages.py)

Messaging via screenshots. Extends `LinkedInBot`.

| Method | Returns | Description |
|--------|---------|-------------|
| `ensure_messaging_page()` | `str` | Navigate to messaging, return screenshot path |
| `screenshot_conversations()` | `str` | Screenshot the conversation list |
| `open_conversation(click_x, click_y)` | `str` | Click a conversation, return screenshot of thread |
| `screenshot_thread()` | `str` | Screenshot the currently open thread |
| `send_message(input_x, input_y, text)` | `str` | Click input, type text, press Enter, return screenshot |
| `scroll_thread_up()` | `str` | Scroll up in thread, return screenshot |
| `scroll_thread_down()` | `str` | Scroll down in thread, return screenshot |
| `scroll_conversations_down()` | `str` | Scroll conversation list, return screenshot |
| `collect_screenshots(coords_list, pause=2.0)` | `list[str]` | Click through conversations, screenshot each |

### LinkedInSearch (linkedin_search.py)

People and company search. Extends `LinkedInBot`.

| Method | Returns | Description |
|--------|---------|-------------|
| `search_people(query, scroll_pages=1)` | `list[str]` | Search people, return list of screenshot paths |
| `search_companies(query, scroll_pages=1)` | `list[str]` | Search companies, return list of screenshot paths |
| `next_page(next_button_x, next_button_y)` | `str` | Click Next button, return screenshot path |

### LinkedInProfile (linkedin_profile.py)

Profile viewing via screenshots. Extends `LinkedInBot`.

| Method | Returns | Description |
|--------|---------|-------------|
| `view_profile(profile_url)` | `str` | Navigate to profile, return screenshot path |
| `screenshot_full_profile(profile_url, scroll_count=5)` | `list[str]` | Capture full profile via scrolling |
| `scroll_to_section(delta_y=700)` | `str` | Scroll profile, return screenshot path |

### LinkedInConnect (linkedin_connect.py)

Connection management via screenshots. Extends `LinkedInBot`.

| Method | Returns | Description |
|--------|---------|-------------|
| `view_profile(profile_url)` | `str` | Navigate to profile, return screenshot path |
| `send_connection_note(input_x, input_y, note)` | `str` | Type connection note, return screenshot path |
| `screenshot_invitations()` | `str` | Screenshot pending invitations page |
| `screenshot_sent_invitations()` | `str` | Screenshot sent invitations page |
| `accept_invitation(accept_x, accept_y)` | `str` | Click Accept on an invitation, return screenshot path |
| `scroll_invitations()` | `str` | Scroll invitations list, return screenshot path |

### RateLimiter (rate_limiter.py)

Daily rate limiting with persistent state.

| Method | Returns | Description |
|--------|---------|-------------|
| `can_send_message()` | `bool` | Check if can send a message |
| `can_view_profile()` | `bool` | Check if can view a profile |
| `can_send_connection()` | `bool` | Check if can send connection request |
| `can_search()` | `bool` | Check if can perform a search |
| `can_accept_connection()` | `bool` | Check if can accept a connection |
| `record_message()` | `None` | Record a sent message |
| `record_profile_view()` | `None` | Record a profile view |
| `record_connection_request()` | `None` | Record a connection request |
| `record_search()` | `None` | Record a search |
| `record_connection_accept()` | `None` | Record accepting a connection |
| `wait_if_needed(action)` | `float` | Wait for required delay, return wait time |
| `get_stats()` | `dict` | Get current usage statistics |
| `get_remaining(action)` | `int` | Get remaining count for an action |
| `time_until_reset()` | `str` | Human-readable time until daily reset |
| `print_stats()` | `None` | Print formatted usage statistics |

## Rate Limits (Defaults)

To avoid LinkedIn restrictions, the following conservative defaults are enforced:

| Action | Daily Limit | Delay Between |
|--------|-------------|---------------|
| Messages | 50 | 30-60 seconds |
| Profile Views | 100 | 10-30 seconds |
| Connection Requests | 25 | 60-120 seconds |
| Searches | 30 | 15-45 seconds |
| Connection Accepts | 50 | 5-15 seconds |

These limits are configurable via `RateLimiter(limits={...}, delays={...})`.

## Human-like Behavior

Built-in delays and mouse movement to mimic human behavior:

- **Mouse movement**: Cubic Bezier curves with randomized control points, micro-jitter, overshoot correction
- **Typing speed**: 80-200ms per character
- **Space/punctuation**: 150-450ms pause
- **Thinking pauses**: 300-600ms occasionally
- **Before clicking**: 100-300ms
- **After actions**: 500-1500ms

## File Structure

```
linkedin-cdp/
├── linkedin_cdp.py         # Core CDP connection, mouse/keyboard input, screenshots
├── linkedin_messages.py    # Messaging (screenshot-based)
├── linkedin_search.py      # People/company search (screenshot-based)
├── linkedin_profile.py     # Profile viewing (screenshot-based)
├── linkedin_connect.py     # Connection requests (screenshot-based)
├── linkedin_send.py        # Example messaging script
├── rate_limiter.py         # Rate limiting & protection
├── chrome_debug.sh         # Chrome launcher script
├── requirements.txt        # Python dependencies
├── README.md               # This file
├── USE_CASES.md            # Usage examples
└── LICENSE                 # MIT License
```

## Troubleshooting

### "Connection failed"
- Ensure Chrome is running with `--remote-debugging-port=9222`
- Check: `curl http://localhost:9222/json`

### "WebSocket 403 Forbidden"
- Add `--remote-allow-origins=http://localhost,http://127.0.0.1` flag to Chrome

### Account restricted
- You are likely hitting rate limits too fast
- Use the RateLimiter module
- Add longer delays between actions
- Do not send identical messages

## Security

- **Never commit** `chrome-debug-profile/` (contains your cookies!)
- Add to `.gitignore`: `chrome-debug-profile/`
- Do not share your debug Chrome profile
- Use a separate LinkedIn account for testing
- The debug port should only be used on trusted networks
- Navigation is restricted to `linkedin.com` URLs (SSRF protection)
- Screenshot paths are validated against path traversal
- State file permissions are set to `0600` (owner read/write only)

## Contributing

Contributions are welcome! Please:

1. Fork the repository
2. Create a feature branch
3. Add tests if applicable
4. Submit a pull request

## License

MIT License - see [LICENSE](LICENSE) file.

---

**Remember:** Use responsibly. Respect LinkedIn's terms and other users' privacy.

# LinkedIn CDP Automation

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

LinkedIn automation toolkit using Chrome DevTools Protocol (CDP). Human-like behavior to avoid detection.

## Disclaimer

> **This tool is for educational and research purposes only.**
>
> - Use responsibly and in compliance with [LinkedIn's Terms of Service](https://www.linkedin.com/legal/user-agreement)
> - The author is not responsible for any misuse or account restrictions
> - Respect other users' privacy and LinkedIn's rate limits
> - Do not use for spam, harassment, or any malicious purposes

## Features

| Feature | Status | Description |
|---------|--------|-------------|
| Send Messages | ✅ | Send messages in conversations |
| Read Messages | ✅ | Read conversation history |
| Search People | ✅ | Search LinkedIn for people |
| View Profiles | ✅ | Extract profile information |
| Connection Requests | ✅ | Send connection requests |
| Rate Limiting | ✅ | Built-in protection against blocks |
| Human-like Behavior | ✅ | Random delays, natural typing |

## How It Works

```
┌─────────────────┐     WebSocket      ┌─────────────────┐
│  Python Script  │ ◄────────────────► │  Google Chrome  │
│  (linkedin_cdp) │     CDP Protocol   │  (debugging on) │
└─────────────────┘                    └────────┬────────┘
                                               │
                                               ▼
                                      ┌─────────────────┐
                                      │    LinkedIn     │
                                      │   (logged in)   │
                                      └─────────────────┘
```

1. **Chrome** runs with `--remote-debugging-port=9222`
2. **Python script** connects to Chrome via WebSocket
3. Script sends **CDP commands** (click, type, navigate)
4. Chrome executes commands on LinkedIn page
5. All actions look **human-like** (delays, slow typing)

## Installation

### 1. Clone the repository

```bash
git clone https://github.com/anthroos/linkedin-cdp.git
cd linkedin-cdp
```

### 2. Install dependencies

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
    --remote-allow-origins=* \
    --user-data-dir="$HOME/chrome-debug-profile"

# Linux
google-chrome \
    --remote-debugging-port=9222 \
    --remote-allow-origins=* \
    --user-data-dir="$HOME/chrome-debug-profile"

# Windows
chrome.exe ^
    --remote-debugging-port=9222 ^
    --remote-allow-origins=* ^
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
from linkedin_cdp import LinkedInBot

bot = LinkedInBot()
bot.connect()

# Send a message in current conversation
bot.send_message("Hello! How are you?")

# Click on a conversation by index
bot.click_conversation(2)

bot.close()
```

### Search for People

```python
from linkedin_search import LinkedInSearch

search = LinkedInSearch()
search.connect()

# Search for people
results = search.search_people("AI Engineer San Francisco")

for person in results:
    print(f"{person['name']} - {person['title']}")

search.close()
```

### View Profile

```python
from linkedin_profile import LinkedInProfile

profile = LinkedInProfile()
profile.connect()

# Get profile data
data = profile.get_profile("https://linkedin.com/in/username")
print(f"Name: {data['name']}")
print(f"Title: {data['title']}")
print(f"Location: {data['location']}")

profile.close()
```

### Send Connection Request

```python
from linkedin_connect import LinkedInConnect

connect = LinkedInConnect()
connect.connect()

# Send connection with note
connect.send_request(
    profile_url="https://linkedin.com/in/username",
    note="Hi! I'd love to connect and discuss AI."
)

connect.close()
```

### Rate Limiting

```python
from rate_limiter import RateLimiter

limiter = RateLimiter()

# Check if action is allowed
if limiter.can_send_message():
    bot.send_message("Hello!")
    limiter.record_message()
else:
    print(f"Daily limit reached. Resets in {limiter.time_until_reset()}")

# View current usage
print(limiter.get_stats())
```

## API Reference

### LinkedInBot (linkedin_cdp.py)

| Method | Description |
|--------|-------------|
| `connect()` | Connect to Chrome |
| `send_message(text)` | Type and send message |
| `click_conversation(index)` | Click conversation (1-based) |
| `click_element(selector)` | Click element by CSS selector |
| `type_text(text)` | Type text human-like |
| `get_current_conversation()` | Get name of current chat partner |
| `get_conversations_list(limit)` | List visible conversations |
| `scroll_conversations(direction)` | Scroll conversation list |
| `find_conversation_by_name(name)` | Search for conversation by name |
| `read_current_messages()` | Read messages in current thread |
| `reconnect_to_tab(pattern)` | Reconnect WebSocket after navigation |
| `close()` | Close connection |

### LinkedInSearch (linkedin_search.py)

| Method | Description |
|--------|-------------|
| `search_people(query, limit=10)` | Search for people |
| `search_companies(query, limit=10)` | Search for companies |
| `get_search_results()` | Get current page results |

### LinkedInProfile (linkedin_profile.py)

| Method | Description |
|--------|-------------|
| `get_profile(url)` | Get full profile data |
| `get_experience()` | Get work experience |
| `get_education()` | Get education |
| `get_skills()` | Get skills list |

### LinkedInConnect (linkedin_connect.py)

| Method | Description |
|--------|-------------|
| `send_request(url, note=None)` | Send connection request |
| `withdraw_request(url)` | Withdraw pending request |
| `accept_request(name)` | Accept incoming request |

### RateLimiter (rate_limiter.py)

| Method | Description |
|--------|-------------|
| `can_send_message()` | Check if can send message |
| `can_view_profile()` | Check if can view profile |
| `can_send_connection()` | Check if can send connection |
| `record_*()` | Record an action |
| `get_stats()` | Get usage statistics |

## Rate Limits (Recommended)

To avoid LinkedIn restrictions:

| Action | Daily Limit | Delay Between |
|--------|-------------|---------------|
| Messages | 50-100 | 30-60 seconds |
| Profile Views | 80-150 | 10-30 seconds |
| Connection Requests | 20-50 | 60-120 seconds |
| Searches | 30-50 | 15-45 seconds |

These limits are configurable in `rate_limiter.py`.

## Human-like Behavior

Built-in delays to mimic human behavior:

- **Typing speed**: 80-200ms per character
- **Space/punctuation**: 150-450ms pause
- **Thinking pauses**: 300-600ms occasionally
- **Before clicking**: 100-300ms
- **After actions**: 500-1500ms

## File Structure

```
linkedin-cdp/
├── linkedin_cdp.py         # Core CDP connection & messaging
├── linkedin_search.py      # People/company search
├── linkedin_profile.py     # Profile data extraction
├── linkedin_connect.py     # Connection requests
├── linkedin_send.py        # Bulk messaging example
├── rate_limiter.py         # Rate limiting & protection
├── chrome_debug.sh         # Chrome launcher script
├── README.md               # This file
├── SKILL_LINKEDIN_CDP.md   # Detailed usage guide & best practices
└── LICENSE                 # MIT License
```

## Documentation

For detailed usage guide, best practices, and known limitations, see **[SKILL_LINKEDIN_CDP.md](SKILL_LINKEDIN_CDP.md)**.

## Troubleshooting

### "Connection failed"
- Ensure Chrome is running with `--remote-debugging-port=9222`
- Check: `curl http://localhost:9222/json`

### "WebSocket 403 Forbidden"
- Add `--remote-allow-origins=*` flag to Chrome

### Elements not found
- LinkedIn frequently updates their DOM
- Check selectors in browser DevTools
- Use `bot._evaluate('your JS code')` for custom queries

### Account restricted
- You're likely hitting rate limits too fast
- Use the RateLimiter module
- Add longer delays between actions
- Don't send identical messages

## Security

- **Never commit** `chrome-debug-profile/` (contains your cookies!)
- Add to `.gitignore`: `chrome-debug-profile/`
- Don't share your debug Chrome profile
- Use a separate LinkedIn account for testing

## Contributing

Contributions are welcome! Please:

1. Fork the repository
2. Create a feature branch
3. Add tests if applicable
4. Submit a pull request

## License

MIT License - see [LICENSE](LICENSE) file.

## Acknowledgments

- Chrome DevTools Protocol documentation
- LinkedIn automation community
- Contributors and testers

---

**Remember:** Use responsibly. Respect LinkedIn's terms and other users' privacy.

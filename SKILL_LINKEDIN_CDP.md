# Skill: LinkedIn CDP Automation

## Overview

LinkedIn automation toolkit using Chrome DevTools Protocol (CDP). Enables programmatic interaction with LinkedIn for messaging, profile viewing, search, and connection management while maintaining human-like behavior to avoid detection.

**Repository:** `linkedin-cdp`
**Author:** Ivan Pasichnyk
**License:** MIT

---

## Prerequisites

1. **Chrome with Remote Debugging**
   ```bash
   # macOS
   /Applications/Google\ Chrome.app/Contents/MacOS/Google\ Chrome --remote-debugging-port=9222

   # Linux
   google-chrome --remote-debugging-port=9222
   ```

2. **Python Dependencies**
   ```bash
   pip install websocket-client requests
   ```

3. **LinkedIn Session**
   - Must be logged into LinkedIn in the Chrome instance
   - Keep Chrome window open during automation

---

## Available Modules

### 1. `linkedin_cdp.py` - Core Module

Base class with CDP communication and human-like interactions.

| Function | Description |
|----------|-------------|
| `connect()` | Connect to Chrome via CDP, find LinkedIn tab |
| `send_message(text)` | Send message in current conversation |
| `type_text(text)` | Type text with human-like delays |
| `click_element(selector)` | Click element with mouse simulation |
| `get_current_conversation()` | Get name of current chat partner |
| `get_conversations_list(limit)` | List visible conversations |
| `scroll_conversations(direction)` | Scroll conversation list |
| `find_conversation_by_name(name)` | Search for conversation by name |
| `read_current_messages()` | Read messages in current thread |
| `reconnect_to_tab(pattern)` | Reconnect WebSocket after navigation |

### 2. `linkedin_search.py` - Search Module

People and company search functionality.

| Function | Description |
|----------|-------------|
| `search_people(query, limit)` | Search for people, returns name/title/location/url |
| `search_companies(query, limit)` | Search for companies, returns name/industry/url |

### 3. `linkedin_profile.py` - Profile Module

Profile viewing and data extraction.

| Function | Description |
|----------|-------------|
| `get_profile(url)` | Get basic profile info (name, title, location, about) |
| `get_full_profile(url)` | Get complete profile with experience, education, skills |
| `get_experience()` | Extract work experience from current profile |
| `get_education()` | Extract education from current profile |
| `get_skills()` | Extract skills from current profile |
| `get_connection_degree()` | Get connection degree (1st, 2nd, 3rd) |

### 4. `linkedin_connect.py` - Connection Module

Connection request management.

| Function | Description |
|----------|-------------|
| `send_request(url, note)` | Send connection request with optional note |
| `withdraw_request(url)` | Withdraw pending connection request |
| `accept_request(name)` | Accept incoming request by name |
| `get_pending_invitations()` | List incoming invitations |
| `get_sent_invitations()` | List sent pending invitations |
| `accept_all_invitations(limit)` | Accept multiple pending invitations |

### 5. `rate_limiter.py` - Rate Limiting

Protects against LinkedIn detection with configurable limits.

| Function | Description |
|----------|-------------|
| `can_search()` | Check if search limit allows action |
| `can_send_connection()` | Check connection request limit |
| `can_view_profile()` | Check profile view limit |
| `wait_if_needed(action)` | Apply delay between actions |

---

## Best Practices by Task

### Sending Messages

**Limitation:** LinkedIn's React UI blocks programmatic conversation switching.

**Best Approach:**
1. Navigate to LinkedIn messaging in Chrome
2. **User manually clicks** on the desired conversation
3. Bot verifies correct conversation is open
4. Bot types and sends message

```python
from linkedin_cdp import LinkedInBot

bot = LinkedInBot()
bot.connect()

# Verify correct conversation
current = bot.get_current_conversation()
print(f"Current conversation: {current}")

if "John" in current:
    bot.send_message("Hey John! ...")
else:
    print("Please click on John's conversation first")

bot.close()
```

### Finding Conversations

**Best Approach:** Scroll and search by name

```python
# List visible conversations
convs = bot.get_conversations_list(limit=10)
for c in convs:
    print(f"{c['name']} - {c['preview']}")

# Scroll to find specific person
found = bot.find_conversation_by_name("Max Whitehead")
if found:
    print("Found! Please click on the conversation.")
```

### Reading Messages

```python
# Read current conversation
messages = bot.read_current_messages()
print(messages)
```

### Searching People/Companies

```python
from linkedin_search import LinkedInSearch

search = LinkedInSearch()
search.connect()

# Search people
people = search.search_people("AI Engineer San Francisco", limit=10)
for p in people:
    print(f"{p['name']} - {p['title']}")
    print(f"  {p['profile_url']}")

# Search companies
companies = search.search_companies("AI startup", limit=5)

search.close()
```

### Viewing Profiles

```python
from linkedin_profile import LinkedInProfile

profile = LinkedInProfile()
profile.connect()

# Get full profile data
data = profile.get_full_profile("https://linkedin.com/in/username")
print(f"Name: {data['name']}")
print(f"Title: {data['title']}")
print(f"Experience: {data['experience']}")

profile.close()
```

### Sending Connection Requests

```python
from linkedin_connect import LinkedInConnect

connect = LinkedInConnect()
connect.connect()

# Send with personalized note
connect.send_request(
    "https://linkedin.com/in/username",
    note="Hi! I'd love to connect and discuss AI projects."
)

connect.close()
```

---

## Known Limitations

### 1. Conversation Switching
LinkedIn's React UI doesn't respond to programmatic clicks for switching conversations. The DOM updates but the message panel doesn't refresh.

**Workaround:** User manually clicks conversation, then bot sends.

### 2. Dynamic CSS Classes
LinkedIn uses obfuscated/changing CSS class names.

**Solution:** Use URL patterns (`/in/`, `/company/`) and innerText parsing instead of class selectors.

### 3. WebSocket Disconnection
`Page.navigate` invalidates the WebSocket connection.

**Solution:** Always call `reconnect_to_tab()` after navigation.

### 4. Rate Limiting
LinkedIn may temporarily restrict accounts with excessive automation.

**Solution:** Use `rate_limiter.py`, add realistic delays, don't exceed daily limits.

---

## Recommended Daily Limits

| Action | Conservative | Moderate |
|--------|-------------|----------|
| Profile views | 50 | 100 |
| Searches | 20 | 50 |
| Connection requests | 15 | 25 |
| Messages | 30 | 50 |

---

## Typical Workflow

```python
from linkedin_cdp import LinkedInBot

bot = LinkedInBot()

# 1. Connect to Chrome
if not bot.connect():
    print("Start Chrome with: --remote-debugging-port=9222")
    exit()

# 2. List conversations
convs = bot.get_conversations_list()
for c in convs:
    print(f"{c['index']}. {c['name']}: {c['preview']}")

# 3. Wait for user to click desired conversation
input("Click on the conversation you want, then press Enter...")

# 4. Verify and send
current = bot.get_current_conversation()
print(f"Sending to: {current}")
bot.send_message("Hello! This is my message.")

# 5. Cleanup
bot.close()
```

---

## Error Handling

```python
try:
    bot = LinkedInBot()
    if not bot.connect():
        raise Exception("Could not connect to Chrome")

    # ... automation code ...

except websocket.WebSocketException as e:
    print(f"WebSocket error: {e}")
    # Reconnect
    bot.reconnect_to_tab("linkedin.com")

except Exception as e:
    print(f"Error: {e}")

finally:
    bot.close()
```

---

## File Structure

```
linkedin-cdp/
├── linkedin_cdp.py      # Core CDP communication & messaging
├── linkedin_search.py   # People and company search
├── linkedin_profile.py  # Profile viewing & data extraction
├── linkedin_connect.py  # Connection request management
├── rate_limiter.py      # Rate limiting protection
├── README.md            # Project documentation
├── LICENSE              # MIT License
└── SKILL_LINKEDIN_CDP.md  # This skill file
```

---

## Value Proposition

- **Human-like behavior:** Random delays, mouse movements, typing simulation
- **Detection avoidance:** Built-in rate limiting and realistic patterns
- **Modular design:** Use only the modules you need
- **Profile data extraction:** Parse LinkedIn's dynamic DOM reliably
- **Messaging automation:** Send personalized messages at scale
- **Search capabilities:** Find people and companies programmatically
- **Connection management:** Automate networking outreach

---

## When to Use This Skill

- Sending bulk personalized messages to prospects
- Extracting profile data for CRM enrichment
- Automating connection request campaigns
- Searching for potential clients/candidates
- Managing pending invitations
- Reading and analyzing conversation history

# LinkedIn CDP — Use Cases (Input-only + Screenshots)

All use cases assume Chrome running with `--remote-debugging-port=9222` and LinkedIn logged in.

**Architecture:** Input-only (mouse/keyboard) + screenshot-based reading.
All methods return base64 PNG screenshots. Claude interprets them visually.

---

## 1. Inbox Check — "Хто мені писав?"

```python
from linkedin_messages import LinkedInMessages
lm = LinkedInMessages()
lm.connect()

screenshot = lm.screenshot_conversations()
# Claude reads screenshot: names, times, snippets
# Save: lm.save_screenshot('/tmp/inbox.png')

lm.close()
```

## 2. Read Conversation — "Покажи розмову з X"

```python
lm = LinkedInMessages()
lm.connect()
lm.screenshot_conversations()  # Claude sees list

# Claude identifies X at coordinates (200, 350)
screenshot = lm.open_conversation(200, 350)
# Claude reads messages from screenshot

# Scroll up for older messages
screenshot = lm.scroll_thread_up()

lm.close()
```

## 3. Send Message — "Напиши X в LinkedIn"

```python
lm = LinkedInMessages()
lm.connect()
lm.screenshot_conversations()

# Claude clicks conversation at (200, 350)
lm.open_conversation(200, 350)

# Claude identifies input field at (500, 700)
screenshot = lm.send_message(500, 700, "Hi! How are you?")

lm.close()
```

## 4. Search People — "Знайди AI Engineers в Берліні"

```python
from linkedin_search import LinkedInSearch
search = LinkedInSearch()
search.connect()

screenshots = search.search_people("AI Engineer Berlin", scroll_pages=2)
# Claude reads all screenshots: names, titles, locations, profile URLs

search.close()
```

## 5. Search Companies — "Знайди AI стартапи"

```python
search = LinkedInSearch()
search.connect()

screenshots = search.search_companies("AI startup Series A", scroll_pages=1)

search.close()
```

## 6. View Profile — "Подивись профіль X"

```python
from linkedin_profile import LinkedInProfile
prof = LinkedInProfile()
prof.connect()

screenshots = prof.screenshot_full_profile("https://linkedin.com/in/username")
# Claude reads all screenshots: name, title, experience, education, skills

prof.close()
```

## 7. Send Connection Request — "Відправ connection request"

```python
from linkedin_connect import LinkedInConnect
conn = LinkedInConnect()
conn.connect()

# Step 1: View profile
screenshot = conn.view_profile("https://linkedin.com/in/username")
# Claude sees Connect button at (850, 320)

# Step 2: Click Connect
screenshot = conn.click_at(850, 320)
# Claude sees modal with "Add a note" at (400, 450)

# Step 3: Click Add note
screenshot = conn.click_at(400, 450)
# Claude sees textarea at (400, 500)

# Step 4: Type note
screenshot = conn.send_connection_note(400, 500, "Hi! I'd love to connect.")
# Claude sees Send button at (500, 600)

# Step 5: Click Send
screenshot = conn.click_at(500, 600)

conn.close()
```

## 8. Accept Invitations — "Прийми запити на з'єднання"

```python
conn = LinkedInConnect()
conn.connect()

screenshot = conn.screenshot_invitations()
# Claude sees invitation list, finds Accept buttons

# Claude identifies Accept button at (700, 250)
screenshot = conn.accept_invitation(700, 250)

conn.close()
```

## 9. View Sent Invitations — "Покажи відправлені запити"

```python
conn = LinkedInConnect()
conn.connect()

screenshot = conn.screenshot_sent_invitations()
# Claude reads pending sent invitations

conn.close()
```

## 10. Multi-conversation Screenshot Collection

```python
lm = LinkedInMessages()
lm.connect()
lm.screenshot_conversations()

# Claude identifies 5 conversations with coordinates
coords = [(200, 250), (200, 330), (200, 410), (200, 490), (200, 570)]
screenshots = lm.collect_screenshots(coords)
# Claude reads each conversation's messages

lm.close()
```

## 11. Generic Click + Screenshot Flow

For any LinkedIn page, use the base class directly:

```python
from linkedin_cdp import LinkedInBot
bot = LinkedInBot()
bot.connect()

# Navigate
bot.navigate_to("https://linkedin.com/any-page")
screenshot = bot.wait_for_page()

# Click anything
screenshot = bot.click_at(x, y)

# Type anything
screenshot = bot.type_and_screenshot("text to type")

# Scroll
screenshot = bot.scroll_and_screenshot(delta_y=600)

bot.close()
```

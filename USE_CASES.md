# LinkedIn CDP — Use Cases

All use cases assume Chrome running with `--remote-debugging-port=9222` and LinkedIn logged in.

**Code base:** `/Users/ivanpasichnyk/linkedin-cdp/`

---

## 1. Inbox Check — "Хто мені писав?"

Read last N conversations, show who wrote what and when.

```python
import sys
sys.path.insert(0, '/Users/ivanpasichnyk/linkedin-cdp')
from linkedin_messages import LinkedInMessages

lm = LinkedInMessages()
lm.connect()

# Quick list without opening each conversation
convos = lm.list_conversations(limit=10)
for c in convos:
    print(f"[{c['time']}] {c['name']}: {c['snippet']}")

lm.close()
```

**Output:**
```
[Feb 24] Akshita Verma: Hey Ivan, guess you have been busy...
[Feb 24] Aleksey Koshkarov: Зрозумів, дякую, що приділили увагу...
[Feb 23] Никита Петухов: Як раз у гугл івенті вірно...
```

---

## 2. Deep Inbox — Read Full Messages from Recent Conversations

Navigate through conversations with human-like mouse, collect actual message text.

```python
from linkedin_messages import LinkedInMessages

lm = LinkedInMessages()
lm.connect()

conversations = lm.collect_recent_conversations(count=5, messages_per_convo=5)
for c in conversations:
    print(f"\n=== {c['name']} ({c['total_messages']} msgs) ===")
    for m in c['messages']:
        print(f"  [{m['time']}] {m['sender']}: {m['text'][:200]}")

lm.close()
```

---

## 3. Read Specific Conversation — "Що писав Никита?"

Find a person by name and read their conversation history.

```python
from linkedin_messages import LinkedInMessages

lm = LinkedInMessages()
lm.connect()

convo = lm.read_conversation("Никита", last_n=20)
if convo:
    print(f"Conversation with {convo['name']} ({convo['total_messages']} messages)")
    for m in convo['messages']:
        print(f"[{m['time']}] {m['sender']}: {m['text']}")
else:
    print("Not found in visible conversations")

lm.close()
```

---

## 4. Lead Research — Search People and Collect into CSV

Search by role/keyword, extract profile data, save to spreadsheet.

```python
import csv
from linkedin_search import LinkedInSearch
from linkedin_profile import LinkedInProfile

search = LinkedInSearch()
search.connect()

# Search for prospects
results = search.search_people("AI Engineer Kyiv", limit=20)

# Collect profile data
profile = LinkedInProfile()
profile.ws = search.ws  # reuse connection
profile.msg_id = search.msg_id

rows = []
for person in results:
    if not person.get('profile_url'):
        continue
    data = profile.get_profile(person['profile_url'])
    rows.append({
        'name': data.get('name', ''),
        'title': data.get('title', ''),
        'location': data.get('location', ''),
        'about': data.get('about', '')[:200],
        'url': person['profile_url'],
    })

# Save to CSV
with open('/tmp/linkedin_leads.csv', 'w', newline='') as f:
    writer = csv.DictWriter(f, fieldnames=['name', 'title', 'location', 'about', 'url'])
    writer.writeheader()
    writer.writerows(rows)

search.close()
print(f"Saved {len(rows)} leads to /tmp/linkedin_leads.csv")
```

---

## 5. Full Profile Research — Detailed Info on a Person

Get complete profile: experience, education, skills.

```python
from linkedin_profile import LinkedInProfile

prof = LinkedInProfile()
prof.connect()

data = prof.get_full_profile("https://www.linkedin.com/in/username")
print(f"Name: {data['name']}")
print(f"Title: {data['title']}")
print(f"Location: {data['location']}")
print(f"Connection: {data.get('connection_degree', '?')}")

print("\nExperience:")
for exp in data.get('experience', []):
    print(f"  - {exp.get('title')} at {exp.get('company')} ({exp.get('duration','')})")

print("\nEducation:")
for edu in data.get('education', []):
    print(f"  - {edu.get('school')} — {edu.get('degree','')}")

print("\nSkills:")
for skill in data.get('skills', [])[:10]:
    print(f"  - {skill}")

prof.close()
```

---

## 6. CRM Enrichment — Enrich Existing Contacts with LinkedIn Data

Take people from CRM CSV, find them on LinkedIn, add profile data.

```python
import pandas as pd
from linkedin_search import LinkedInSearch
from linkedin_profile import LinkedInProfile

crm = pd.read_csv('/Users/ivanpasichnyk/welababeldata/sales/crm/crm_people_master.csv')

search = LinkedInSearch()
search.connect()

profile = LinkedInProfile()
profile.ws = search.ws
profile.msg_id = search.msg_id

for idx, person in crm.iterrows():
    if pd.notna(person.get('linkedin_url')):
        continue  # already has LinkedIn

    query = f"{person['first_name']} {person['last_name']} {person.get('company_name','')}"
    results = search.search_people(query, limit=3)

    if results:
        best = results[0]
        crm.at[idx, 'linkedin_url'] = best.get('profile_url', '')
        crm.at[idx, 'linkedin_title'] = best.get('title', '')
        print(f"Found: {person['first_name']} {person['last_name']} -> {best.get('name')}")

search.close()
crm.to_csv('/tmp/crm_enriched.csv', index=False)
```

---

## 7. Connection Campaign — Send Requests to Search Results

Search for target audience and send personalized connection requests.

```python
from linkedin_search import LinkedInSearch
from linkedin_connect import LinkedInConnect

search = LinkedInSearch()
search.connect()

connect = LinkedInConnect()
connect.ws = search.ws
connect.msg_id = search.msg_id

results = search.search_people("CTO startup Berlin", limit=10)

sent = 0
for person in results:
    url = person.get('profile_url')
    if not url:
        continue

    name = person.get('name', '').split()[0]  # first name
    note = f"Hi {name}, I run a data labeling company and would love to connect."

    success = connect.send_request(url, note=note)
    if success:
        sent += 1
        print(f"Sent to {person['name']}")

search.close()
print(f"Sent {sent} connection requests")
```

---

## 8. Pending Invitations — Accept/Review Incoming Requests

Check who wants to connect with you.

```python
from linkedin_connect import LinkedInConnect

conn = LinkedInConnect()
conn.connect()

invitations = conn.get_pending_invitations()
for inv in invitations:
    print(f"{inv['name']} — {inv.get('title','')}")
    print(f"  Message: {inv.get('message','(no message)')}")

# Accept specific ones
for inv in invitations:
    if any(kw in inv.get('title','').lower() for kw in ['cto', 'founder', 'ai']):
        conn.accept_request(inv['name'])
        print(f"Accepted: {inv['name']}")

conn.close()
```

---

## 9. Follow-up Check — Did They Reply?

Check if specific people replied to your messages.

```python
from linkedin_messages import LinkedInMessages

lm = LinkedInMessages()
lm.connect()

check_names = ["Aridoss K", "Никита Петухов", "Akshita Verma"]

for name in check_names:
    convo = lm.read_conversation(name, last_n=3)
    if convo:
        last_msg = convo['messages'][-1] if convo['messages'] else None
        if last_msg:
            is_them = last_msg['sender'] != "Ivan Pasichnyk"
            status = "REPLIED" if is_them else "WAITING"
            print(f"[{status}] {name}: {last_msg['text'][:100]}")
    else:
        print(f"[NOT FOUND] {name}")

lm.close()
```

---

## 10. Conversation Export — Full History to File

Export complete conversation with a person for reference.

```python
import json
from linkedin_messages import LinkedInMessages

lm = LinkedInMessages()
lm.connect()

convo = lm.read_conversation("Aridoss K", last_n=50)
if convo:
    with open('/tmp/convo_aridoss.json', 'w') as f:
        json.dump(convo, f, indent=2, ensure_ascii=False)
    print(f"Exported {convo['total_messages']} messages")

lm.close()
```

---

## 11. Company Research — Find People at a Company

```python
from linkedin_search import LinkedInSearch

search = LinkedInSearch()
search.connect()

people = search.search_people("T-Mobile product manager", limit=15)
for p in people:
    print(f"{p['name']} — {p['title']}")
    print(f"  {p['profile_url']}")

search.close()
```

---

## 12. Daily LinkedIn Digest

Combine inbox check + follow-up check + pending invitations into one routine.

```python
from linkedin_messages import LinkedInMessages
from linkedin_connect import LinkedInConnect

# 1. Recent messages
lm = LinkedInMessages()
lm.connect()

print("=== INBOX (last 5) ===")
convos = lm.collect_recent_conversations(count=5, messages_per_convo=1)
for c in convos:
    last = c['messages'][-1] if c['messages'] else None
    if last:
        who = "THEM" if last['sender'] != "Ivan Pasichnyk" else "ME"
        print(f"  [{who}] {c['name']}: {last['text'][:120]}")

lm.close()

# 2. Pending invitations
conn = LinkedInConnect()
conn.connect()

print("\n=== PENDING INVITATIONS ===")
invs = conn.get_pending_invitations()
for inv in invs[:5]:
    print(f"  {inv['name']} — {inv.get('title','')}")

conn.close()
```

---

## Rate Limits (recommended daily)

| Action | Conservative | Moderate |
|--------|-------------|----------|
| Profile views | 50 | 100 |
| Searches | 20 | 50 |
| Connection requests | 15 | 25 |
| Messages sent | 30 | 50 |
| Conversation reads | no limit | no limit |

---

## Module Reference

| Module | Class | Key Methods |
|--------|-------|-------------|
| `linkedin_messages.py` | `LinkedInMessages` | `collect_recent_conversations()`, `read_conversation()`, `list_conversations()` |
| `linkedin_cdp.py` | `LinkedInBot` | `send_message()`, `type_text()`, `get_conversations_list()` |
| `linkedin_search.py` | `LinkedInSearch` | `search_people()`, `search_companies()` |
| `linkedin_profile.py` | `LinkedInProfile` | `get_profile()`, `get_full_profile()`, `get_experience()` |
| `linkedin_connect.py` | `LinkedInConnect` | `send_request()`, `accept_request()`, `get_pending_invitations()` |
| `rate_limiter.py` | `RateLimiter` | `wait_if_needed()`, `can_search()`, `print_stats()` |

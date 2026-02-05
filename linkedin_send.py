#!/usr/bin/env python3
"""
Send LinkedIn messages to multiple people.
Usage: python3 linkedin_send.py
"""
import sys
import time
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from linkedin_cdp import LinkedInBot

# Message to send
DECLINE_MESSAGE = "Thanks for reaching out! Not looking for external dev help at the moment. Best of luck!"

# People to message (in order as they appear in the list)
# Based on the screenshot: Aman Kaushik (1), Trupti C (2), Akshita Verma (3)
TARGETS = [
    {"name": "Aman Kaushik", "index": 1},
    {"name": "Trupti C", "index": 2},
    {"name": "Akshita Verma", "index": 3},
]


def main():
    bot = LinkedInBot()
    
    print("Connecting to Chrome...")
    if not bot.connect():
        print("✗ Failed to connect. Make sure Chrome is running with debugging.")
        print("  Run: ~/tools/chrome_debug.sh")
        return 1
    
    print(f"\nWill send decline message to {len(TARGETS)} people:")
    for t in TARGETS:
        print(f"  • {t['name']}")
    print(f"\nMessage: \"{DECLINE_MESSAGE[:50]}...\"")
    print()
    
    # Confirm before sending
    confirm = input("Proceed? (y/n): ").strip().lower()
    if confirm != 'y':
        print("Cancelled.")
        bot.close()
        return 0
    
    print()
    
    for i, target in enumerate(TARGETS):
        print(f"[{i+1}/{len(TARGETS)}] {target['name']}...")
        
        # Click on conversation
        if not bot.click_conversation(target['index']):
            print(f"  ✗ Could not find conversation")
            continue
        
        # Human pause after clicking conversation
        time.sleep(1.5)
        
        # Send message
        if bot.send_message(DECLINE_MESSAGE):
            print(f"  ✓ Message sent to {target['name']}")
        else:
            print(f"  ✗ Failed to send to {target['name']}")
        
        # Human pause between messages
        if i < len(TARGETS) - 1:
            pause = 3 + (i * 0.5)  # Increasing pause
            print(f"  Waiting {pause:.1f}s...")
            time.sleep(pause)
    
    print("\n✓ Done!")
    bot.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())

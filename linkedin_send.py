"""
LinkedIn Send — simple message sender using screenshot-based approach.

Usage:
    python linkedin_send.py

Workflow:
    1. Connect to Chrome CDP
    2. Take screenshot of messaging
    3. Caller provides coordinates of conversation + input field
    4. Click, type, send via Input domain
"""
from linkedin_messages import LinkedInMessages


def main():
    lm = LinkedInMessages()
    if not lm.connect():
        print("Failed to connect to Chrome")
        return

    # Take initial screenshot of messaging page
    screenshot = lm.screenshot_conversations()
    if screenshot:
        print("✓ Messaging page screenshot captured")
        print("  Use lm.open_conversation(x, y) to open a conversation")
        print("  Use lm.send_message(input_x, input_y, text) to send")
    else:
        print("✗ Failed to capture messaging page")

    lm.close()


if __name__ == "__main__":
    main()

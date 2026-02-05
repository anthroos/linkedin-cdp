#!/bin/bash
# Launch Google Chrome with remote debugging enabled
# Usage: ./chrome_debug.sh

PORT=9222

# Check if Chrome is already running with debugging
if curl -s "http://localhost:$PORT/json/version" > /dev/null 2>&1; then
    echo "✓ Chrome already running with debugging on port $PORT"
    curl -s "http://localhost:$PORT/json/version" | python3 -c "import sys,json; d=json.load(sys.stdin); print(f'  Browser: {d.get(\"Browser\",\"?\")}')"
    exit 0
fi

# Check if Chrome is running without debugging
if pgrep -x "Google Chrome" > /dev/null; then
    echo "⚠ Chrome is running but without debugging port."
    echo "  Please quit Chrome and run this script again,"
    echo "  or restart Chrome manually with:"
    echo ""
    echo "  /Applications/Google\\ Chrome.app/Contents/MacOS/Google\\ Chrome --remote-debugging-port=$PORT"
    exit 1
fi

# Launch Chrome with debugging
echo "Starting Chrome with remote debugging on port $PORT..."
open -a 'Google Chrome' --args \
    --remote-debugging-port=$PORT \
    --remote-allow-origins=\* \
    --user-data-dir="$HOME/chrome-debug-profile"

# Wait for Chrome to start
sleep 2

if curl -s "http://localhost:$PORT/json/version" > /dev/null 2>&1; then
    echo "✓ Chrome started successfully with debugging on port $PORT"
else
    echo "✗ Failed to start Chrome with debugging"
    exit 1
fi

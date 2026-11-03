#!/bin/bash
DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$DIR"

echo "=================================================="
echo " Starting CampusConnect Server..."
echo "=================================================="

# Check and kill any existing process running on port 5050
PID=$(lsof -ti:5050 2>/dev/null)
if [ -n "$PID" ]; then
    echo "Port 5050 is in use. Stopping previous instance (PID $PID)..."
    kill -9 $PID 2>/dev/null
    sleep 1
fi

echo "Launching application on http://localhost:5050"
echo "Admin Login: admin@campusconnect.edu | Password: admin123"
echo "Keep this window open while using CampusConnect."
echo "Press Ctrl+C to stop the server."
echo "=================================================="

# Auto-open browser after 1 second
(sleep 1.5 && open "http://localhost:5050") &

# Run server with venv python
if [ -f "$DIR/.venv/bin/python" ]; then
    "$DIR/.venv/bin/python" app.py
else
    python3 app.py
fi

#!/bin/bash
# CampusConnect: Start Server Script (Preserves existing data)

# Stop any process on port 5050 if blocked
PID=$(lsof -ti:5050)
if [ -n "$PID" ]; then
    kill -9 $PID 2>/dev/null
fi

echo "=================================================="
echo "Starting CampusConnect on http://localhost:5050"
echo "Pre-decided Admin: admin@campusconnect.edu | Password: admin123"
echo "=================================================="
.venv/bin/python app.py

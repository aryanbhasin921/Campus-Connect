#!/bin/bash
# CampusCommute: One-Click Restart & Reset Script

echo "=================================================="
echo "Restarting CampusCommute..."
echo "=================================================="

# 1. Stop any currently running server instances on port 5050
PID=$(lsof -ti:5050)
if [ -n "$PID" ]; then
    echo "Stopping existing server process (PID: $PID)..."
    kill -9 $PID 2>/dev/null
fi

# 2. Reset database to clean presentation state (0 published rides, ready accounts)
echo "Resetting database to 0 rides (presentation ready)..."
.venv/bin/python database/sqlite_init.py

# 3. Start the Flask application
echo "Starting CampusCommute on http://localhost:5050 ..."
echo "Pre-decided Admin: admin@campuscommute.edu | Password: admin123"
echo "=================================================="
.venv/bin/python app.py

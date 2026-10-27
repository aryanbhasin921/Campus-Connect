#!/bin/bash
cd "$(dirname "$0")"
PID=$(lsof -ti:5050)
if [ -n "$PID" ]; then kill -9 $PID 2>/dev/null; fi
echo "Starting CampusConnect..."
.venv/bin/python app.py

#!/bin/bash
PID=$(lsof -ti:5050)
if [ -n "$PID" ]; then
    kill -9 $PID 2>/dev/null
    echo "CampusConnect server on port 5050 stopped."
else
    echo "No server was running on port 5050."
fi
sleep 1

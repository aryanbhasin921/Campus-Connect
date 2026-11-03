#!/bin/bash
DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$DIR"

echo "=================================================="
echo " Stopping CampusConnect Server on Port 5050..."
echo "=================================================="

PID=$(lsof -ti:5050 2>/dev/null)
if [ -n "$PID" ]; then
    kill -9 $PID 2>/dev/null
    echo "✓ CampusConnect server (PID $PID) has been stopped successfully."
else
    echo "ℹ No server was found running on port 5050."
fi

echo "=================================================="
echo "Done. This window will close automatically."
sleep 2

#!/bin/bash
# Double-click to run CampusConnect on macOS.
cd "$(dirname "$0")"
if command -v python3 >/dev/null 2>&1; then
    python3 launcher.py
else
    echo "Python 3 was not found. Install it from https://www.python.org/downloads/ and try again."
fi
echo
read -n 1 -s -r -p "Press any key to close this window..."

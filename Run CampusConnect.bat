@echo off
REM Double-click to run CampusConnect on Windows.
cd /d "%~dp0"
where py >nul 2>nul && (py -3 launcher.py & goto done)
where python >nul 2>nul && (python launcher.py & goto done)
echo Python 3 was not found. Install it from https://www.python.org/downloads/
echo (tick "Add python.exe to PATH" during setup), then double-click this file again.
:done
echo.
pause

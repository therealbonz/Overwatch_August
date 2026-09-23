@echo off
title Antigravity Overwatch - VNC & Web Stream Server
cd /d "%~dp0"

echo ====================================================
echo   Antigravity Overwatch VNC ^& Web Stream Server
echo ====================================================
echo Ports:
echo   - RFB VNC: port 5900 (vnc://localhost:5900)
echo   - Web VNC: port 5901 (http://localhost:5901)
echo.
echo Starting bridge servers...

py web_server.py

if errorlevel 1 (
    echo.
    echo Server exited with an error.
    pause
)

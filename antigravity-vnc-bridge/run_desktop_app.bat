@echo off
title Antigravity Overwatch - Desktop Controller
cd /d "%~dp0"

echo ====================================================
echo   Antigravity Overwatch Desktop Controller
echo ====================================================
echo Starting desktop application...

py desktop_app.py

if errorlevel 1 (
    echo.
    echo Application exited with an error.
    pause
)

@echo off
title therealbonz.com Launchpad Backend (Dev)
cd /d "%~dp0backend"

set PYTHON_EXE="C:\Users\Brendhann\AppData\Local\Programs\Python\Python312\python.exe"
if not exist %PYTHON_EXE% (
    set PYTHON_EXE=python
)

echo ============================================================
echo  Starting therealbonz.com Homepage & CMS on http://127.0.0.1:8080
echo ============================================================

%PYTHON_EXE% -m pip install -q -r requirements.txt
%PYTHON_EXE% -m uvicorn main:app --host 127.0.0.1 --port 8080 --reload

pause

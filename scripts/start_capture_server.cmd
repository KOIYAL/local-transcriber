@echo off
setlocal
set "WHISPER_LOCAL_MODEL=%~1"
cd /d "%~2"
".venv\Scripts\python.exe" app\desktop.py --port 8765

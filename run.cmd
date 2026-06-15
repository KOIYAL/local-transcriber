@echo off
setlocal
cd /d "%~dp0"

set "VENV_PYTHON=.venv\Scripts\python.exe"
if not defined PORT set "PORT=8000"

if not exist "%VENV_PYTHON%" (
    echo Creating Python virtual environment...
    where py >nul 2>nul
    if not errorlevel 1 (
        py -3 -m venv .venv
    ) else (
        python -m venv .venv
    )
    if errorlevel 1 (
        echo Failed to create the virtual environment.
        exit /b 1
    )
)

"%VENV_PYTHON%" -c "import fastapi, faster_whisper, multipart, uvicorn" >nul 2>nul
if errorlevel 1 (
    echo Installing dependencies...
    "%VENV_PYTHON%" -m pip install --disable-pip-version-check -e .
    if errorlevel 1 (
        echo Failed to install dependencies.
        exit /b 1
    )
)

echo Local Transcriber: http://127.0.0.1:%PORT%
"%VENV_PYTHON%" -m uvicorn app.main:app --host 127.0.0.1 --port %PORT% %*

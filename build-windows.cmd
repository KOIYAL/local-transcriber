@echo off
setlocal
cd /d "%~dp0"

set "PYTHON=.venv\Scripts\python.exe"
if not exist "%PYTHON%" (
    echo Run run.cmd once before building the Windows app.
    exit /b 1
)

echo [1/4] Installing build dependencies...
"%PYTHON%" -m pip install --disable-pip-version-check -e ".[desktop]"
if errorlevel 1 exit /b 1

echo [2/4] Building the bundled transcription backend...
"%PYTHON%" -m PyInstaller --noconfirm --clean --distpath dist\backend --workpath build\pyinstaller desktop\backend.spec
if errorlevel 1 exit /b 1

echo [3/4] Installing Electron and winapp CLI...
pushd desktop
call npm.cmd install
if errorlevel 1 (
    popd
    exit /b 1
)

echo [4/4] Building the Windows desktop app...
call npm.cmd run package:electron
if errorlevel 1 (
    popd
    exit /b 1
)
popd
copy /Y START_HERE.txt dist\electron\LocalTranscriber-win32-x64\START_HERE.txt >nul
if errorlevel 1 exit /b 1

echo.
echo Build complete:
echo dist\electron\LocalTranscriber-win32-x64\LocalTranscriber.exe
echo.
echo To create an MSIX package, run:
echo package-msix.cmd

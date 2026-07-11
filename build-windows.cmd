@echo off
setlocal
cd /d "%~dp0"

set "VERSION=0.5.0"

set "PYTHON=.venv\Scripts\python.exe"
if not exist "%PYTHON%" (
    echo Run run.cmd once before building the Windows app.
    exit /b 1
)

if not exist "vendor\modelshelf.exe" (
    echo vendor\modelshelf.exe is missing - the summary feature needs it.
    echo Download it from the public modelshelf release:
    echo   mkdir vendor
    echo   curl -fL https://github.com/KOIYAL/modelshelf/releases/latest/download/modelshelf-windows-x64.exe -o vendor\modelshelf.exe
    exit /b 1
)

echo [1/5] Installing build dependencies...
"%PYTHON%" -m pip install --disable-pip-version-check -e ".[desktop,summary]" --extra-index-url https://abetlen.github.io/llama-cpp-python/whl/cpu
if errorlevel 1 exit /b 1

echo [2/5] Building the bundled transcription backend...
"%PYTHON%" -m PyInstaller --noconfirm --clean --distpath dist\backend --workpath build\pyinstaller desktop\backend.spec
if errorlevel 1 exit /b 1

echo [3/5] Installing Electron and winapp CLI...
pushd desktop
call npm.cmd install
if errorlevel 1 (
    popd
    exit /b 1
)

echo [4/5] Building the Windows desktop app...
call npm.cmd run package:electron
if errorlevel 1 (
    popd
    exit /b 1
)
popd
copy /Y START_HERE.txt dist\electron\LocalTranscriber-win32-x64\START_HERE.txt >nul
if errorlevel 1 exit /b 1

echo [5/5] Creating the portable zip...
powershell -NoProfile -Command "Compress-Archive -Path 'dist\electron\LocalTranscriber-win32-x64' -DestinationPath 'dist\LocalTranscriber-%VERSION%-win-x64.zip' -Force"
if errorlevel 1 exit /b 1

echo.
echo Build complete:
echo   dist\electron\LocalTranscriber-win32-x64\LocalTranscriber.exe
echo   dist\LocalTranscriber-%VERSION%-win-x64.zip
echo.
echo To create an MSIX package, run:
echo package-msix.cmd

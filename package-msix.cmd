@echo off
setlocal
cd /d "%~dp0"

set "PACKAGE_DIR=dist\electron\LocalTranscriber-win32-x64"
set "EXECUTABLE=%PACKAGE_DIR%\LocalTranscriber.exe"
set "MANIFEST=%PACKAGE_DIR%\Package.appxmanifest"
set "OUTPUT=dist\KOIYAL-Transcriber-Store.msix"
set "LOGO=assets\app-icon.png"

if not exist "%EXECUTABLE%" (
    echo Build the desktop app first by running build-windows.cmd.
    exit /b 1
)

if not exist "%LOGO%" (
    echo ERROR: App icon not found: %LOGO%
    echo Run scripts\generate_app_icons.py first.
    exit /b 1
)

pushd "%PACKAGE_DIR%"
if exist Package.appxmanifest del /q Package.appxmanifest
call ..\..\..\desktop\node_modules\.bin\winapp.cmd manifest generate . --package-name LocalTranscriber --description "Local audio and video transcription" --executable "LocalTranscriber.exe" --logo-path "..\..\..\%LOGO%"
if errorlevel 1 (
    popd
    exit /b 1
)
popd

if "%STORE_IDENTITY_NAME%"=="" (
    echo ERROR: STORE_IDENTITY_NAME is required.
    echo Copy Package/Identity/Name from Partner Center ^> Product identity.
    exit /b 1
)

if "%STORE_PUBLISHER%"=="" (
    echo ERROR: STORE_PUBLISHER is required.
    echo Copy Package/Identity/Publisher from Partner Center ^> Product identity.
    exit /b 1
)

".venv\Scripts\python.exe" desktop\prepare_store_manifest.py "%MANIFEST%"
if errorlevel 1 exit /b 1

if "%SIGNING_CERT%"=="" (
    echo Creating an unsigned Microsoft Store MSIX package.
    call desktop\node_modules\.bin\winapp.cmd package "%PACKAGE_DIR%" --output "%OUTPUT%"
) else (
    echo Creating a signed MSIX package.
    call desktop\node_modules\.bin\winapp.cmd package "%PACKAGE_DIR%" --output "%OUTPUT%" --cert "%SIGNING_CERT%"
)
if errorlevel 1 exit /b 1

echo.
echo Store package created:
echo %OUTPUT%

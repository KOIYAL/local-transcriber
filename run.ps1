param(
    [int]$Port = 8000,
    [switch]$Reload
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$VenvPath = Join-Path $ProjectRoot ".venv"
$PythonPath = Join-Path $VenvPath "Scripts\python.exe"

if (-not (Test-Path $PythonPath)) {
    $SystemPython = Get-Command python -ErrorAction SilentlyContinue
    if (-not $SystemPython) {
        throw "Python 3.10 or later is required."
    }
    & $SystemPython.Source -m venv $VenvPath
}

& $PythonPath -c "import fastapi, faster_whisper, multipart, uvicorn" 2>$null
if ($LASTEXITCODE -ne 0) {
    & $PythonPath -m pip install --disable-pip-version-check -e $ProjectRoot
}

$Arguments = @(
    "-m", "uvicorn",
    "app.main:app",
    "--host", "127.0.0.1",
    "--port", $Port.ToString()
)

if ($Reload) {
    $Arguments += "--reload"
}

& $PythonPath @Arguments

# StockBot Terminal - Windows PowerShell launcher
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path

Write-Host "================================================" -ForegroundColor Cyan
Write-Host "  STOCKBOT TERMINAL - Starting..." -ForegroundColor Cyan
Write-Host "================================================" -ForegroundColor Cyan

# Check .env
if (-not (Test-Path "$root\backend\.env")) {
    if (Test-Path "$root\.env") {
        Copy-Item "$root\.env" "$root\backend\.env"
    } else {
        Write-Host "ERROR: Create backend\.env from .env.example first" -ForegroundColor Red
        exit 1
    }
}

# Install Python deps
Write-Host "[1/3] Installing Python dependencies..." -ForegroundColor Green
pip install -r "$root\backend\requirements.txt" -q
if ($LASTEXITCODE -ne 0) { Write-Host "pip install failed" -ForegroundColor Red; exit 1 }

# Install Node deps
Write-Host "[2/3] Installing Node dependencies..." -ForegroundColor Green
Set-Location "$root\frontend"
npm install --silent
Set-Location $root

# Start backend in its own window
Write-Host "[3/3] Launching services..." -ForegroundColor Green
$backendCmd = "Set-Location '$root\backend'; Write-Host 'BACKEND on :8000' -ForegroundColor Cyan; uvicorn main:app --host 0.0.0.0 --port 8000 --reload"
$backend = Start-Process powershell.exe -ArgumentList "-NoExit", "-ExecutionPolicy", "Bypass", "-Command", $backendCmd -PassThru

Start-Sleep -Seconds 2

# Start frontend in its own window
$frontendCmd = "Set-Location '$root\frontend'; Write-Host 'FRONTEND on :5173' -ForegroundColor Cyan; npm run dev"
$frontend = Start-Process powershell.exe -ArgumentList "-NoExit", "-ExecutionPolicy", "Bypass", "-Command", $frontendCmd -PassThru

Start-Sleep -Seconds 3

Write-Host ""
Write-Host "================================================" -ForegroundColor Cyan
Write-Host "  STOCKBOT TERMINAL RUNNING" -ForegroundColor Cyan
Write-Host "  Frontend: http://localhost:5173" -ForegroundColor White
Write-Host "  Backend:  http://localhost:8000" -ForegroundColor White
Write-Host "  API Docs: http://localhost:8000/docs" -ForegroundColor White
Write-Host "================================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Close the backend/frontend windows to stop, or press Ctrl+C here." -ForegroundColor Yellow

try {
    while ($true) { Start-Sleep -Seconds 5 }
} finally {
    Write-Host "Stopping services..." -ForegroundColor Yellow
    Stop-Process -Id $backend.Id  -ErrorAction SilentlyContinue
    Stop-Process -Id $frontend.Id -ErrorAction SilentlyContinue
    Write-Host "Stopped." -ForegroundColor Green
}

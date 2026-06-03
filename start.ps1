# StockBot Terminal - Windows PowerShell launcher
$ErrorActionPreference = "Stop"

Write-Host "================================================" -ForegroundColor Cyan
Write-Host "  STOCKBOT TERMINAL - Starting..." -ForegroundColor Cyan
Write-Host "================================================" -ForegroundColor Cyan

# Check .env
if (-not (Test-Path "backend\.env")) {
    if (Test-Path ".env") {
        Copy-Item ".env" "backend\.env"
    } else {
        Write-Host "ERROR: Create backend\.env from .env.example first" -ForegroundColor Red
        Write-Host "  Copy-Item .env.example .env" -ForegroundColor Yellow
        Write-Host "  Then edit .env with your Alpaca API keys" -ForegroundColor Yellow
        exit 1
    }
}

# Install Python deps
Write-Host "[1/3] Installing Python dependencies..." -ForegroundColor Green
Set-Location backend
pip install -r requirements.txt -q
if ($LASTEXITCODE -ne 0) { Write-Host "pip install failed" -ForegroundColor Red; exit 1 }

# Start backend
Write-Host "[2/3] Starting FastAPI backend on :8000..." -ForegroundColor Green
$backend = Start-Process -FilePath "uvicorn" -ArgumentList "main:app","--host","0.0.0.0","--port","8000","--reload" -NoNewWindow -PassThru
Set-Location ..

# Install and start frontend
Write-Host "[3/3] Starting React frontend on :5173..." -ForegroundColor Green
Set-Location frontend
npm install --silent
$frontend = Start-Process -FilePath "cmd" -ArgumentList "/c","npm","run","dev" -NoNewWindow -PassThru
Set-Location ..

Start-Sleep -Seconds 3

Write-Host ""
Write-Host "================================================" -ForegroundColor Cyan
Write-Host "  STOCKBOT TERMINAL RUNNING" -ForegroundColor Cyan
Write-Host "  Frontend: http://localhost:5173" -ForegroundColor White
Write-Host "  Backend:  http://localhost:8000" -ForegroundColor White
Write-Host "  API Docs: http://localhost:8000/docs" -ForegroundColor White
Write-Host "================================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Press Ctrl+C to stop..." -ForegroundColor Yellow

try {
    # Keep running until Ctrl+C
    while ($true) { Start-Sleep -Seconds 5 }
} finally {
    Write-Host "Stopping services..." -ForegroundColor Yellow
    Stop-Process -Id $backend.Id -ErrorAction SilentlyContinue
    Stop-Process -Id $frontend.Id -ErrorAction SilentlyContinue
    Write-Host "Stopped." -ForegroundColor Green
}

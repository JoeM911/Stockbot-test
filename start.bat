@echo off
cd /d "%~dp0"

echo Starting StockBot Terminal...

:: Kill any old instances
taskkill /f /im python.exe >nul 2>&1
taskkill /f /im node.exe >nul 2>&1
timeout /t 1 >nul

:: Backend
start "StockBot Backend" cmd /k "cd backend && python main.py"

:: Wait for backend to start
timeout /t 3 >nul

:: Frontend
start "StockBot Frontend" cmd /k "cd frontend && npm run dev"

timeout /t 3 >nul

:: Open browser
start http://localhost:5173

echo.
echo StockBot is running!
echo Backend:  http://localhost:8000
echo Frontend: http://localhost:5173
echo.
echo Close the Backend and Frontend windows to stop.

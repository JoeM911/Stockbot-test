#!/bin/bash
set -e

echo "================================================"
echo "  STOCKBOT TERMINAL - Starting..."
echo "================================================"

# Check .env
if [ ! -f backend/.env ]; then
  if [ -f .env ]; then
    cp .env backend/.env
  else
    echo "ERROR: Create backend/.env from .env.example first"
    exit 1
  fi
fi

# Backend
echo "[1/3] Installing Python dependencies..."
cd backend
pip install -r requirements.txt -q
echo "[2/3] Starting FastAPI backend on :8000..."
uvicorn main:app --host 0.0.0.0 --port 8000 --reload &
BACKEND_PID=$!
cd ..

# Frontend
echo "[3/3] Installing and starting React frontend on :5173..."
cd frontend
npm install --silent
npm run dev &
FRONTEND_PID=$!
cd ..

echo ""
echo "================================================"
echo "  STOCKBOT TERMINAL RUNNING"
echo "  Backend:  http://localhost:8000"
echo "  Frontend: http://localhost:5173"
echo "  API Docs: http://localhost:8000/docs"
echo "================================================"
echo ""
echo "Press Ctrl+C to stop all services"

trap "kill $BACKEND_PID $FRONTEND_PID 2>/dev/null; echo 'Stopped.'" EXIT
wait

#!/bin/bash
# ── Aegis Dev Server ──
# Starts backend + frontend + Redis in parallel

set -e
trap "kill 0" EXIT

echo "🛡️  Aegis — Starting development servers..."

# Start Redis (Docker)
echo "🔴 Starting Redis..."
docker run -d --name aegis-redis -p 6379:6379 redis:alpine 2>/dev/null || echo "   Redis already running"

# Start Backend
echo "🐍 Starting backend on http://localhost:8000..."
cd backend
source .venv/bin/activate 2>/dev/null || true
uvicorn app.main:app --reload --port 8000 &
cd ..

# Start Frontend
echo "⚡ Starting frontend on http://localhost:3000..."
cd frontend
npm run dev &
cd ..

echo ""
echo "🛡️  Aegis is running!"
echo "   Frontend: http://localhost:3000"
echo "   Backend:  http://localhost:8000"
echo "   Docs:     http://localhost:8000/docs"
echo ""
echo "   Press Ctrl+C to stop all servers."

wait

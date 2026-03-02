#!/bin/bash
# ── Aegis Setup Script ──
# Run once to install all dependencies

set -e
echo "🛡️  Aegis — Installing dependencies..."

# Backend
echo ""
echo "📦 Installing Python backend dependencies..."
cd backend
python -m venv .venv 2>/dev/null || true
source .venv/bin/activate
pip install -r requirements.txt --quiet
cd ..

# Frontend
echo ""
echo "📦 Installing Node.js frontend dependencies..."
cd frontend
npm install --silent
cd ..

# Check .env
if [ ! -f backend/.env ]; then
  echo ""
  echo "⚠️  backend/.env not found!"
  echo "   Copy backend/.env.example → backend/.env and fill in your API keys."
else
  echo ""
  echo "✅ backend/.env found"
fi

echo ""
echo "🛡️  Setup complete! Run ./dev.sh to start."

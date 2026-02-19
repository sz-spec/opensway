#!/bin/bash
# Start OpenSway locally (Mac / Linux without Docker)
# Prerequisites: Python 3.10+, PostgreSQL, Redis, Node.js

set -e
cd "$(dirname "$0")/.."

echo "=== OpenSway Local Start ==="

# Check services
if ! pg_isready -q 2>/dev/null; then
  echo "Starting PostgreSQL…"
  brew services start postgresql@16 2>/dev/null || \
    pg_ctl -D /usr/local/var/postgresql start 2>/dev/null || \
    echo "  ⚠ Start PostgreSQL manually"
fi

if ! redis-cli ping &>/dev/null; then
  echo "Starting Redis…"
  brew services start redis 2>/dev/null || \
    redis-server --daemonize yes 2>/dev/null || \
    echo "  ⚠ Start Redis manually"
fi

# Create DB if missing
psql -U "$USER" -c "CREATE DATABASE opensway;" 2>/dev/null || true
psql -U "$USER" -c "CREATE USER opensway WITH PASSWORD 'opensway';" 2>/dev/null || true
psql -U "$USER" -c "GRANT ALL ON DATABASE opensway TO opensway;" 2>/dev/null || true

# Python env
if [ ! -d ".venv" ]; then
  echo "Creating virtual environment…"
  python3 -m venv .venv
fi
source .venv/bin/activate
pip install -q -r requirements.txt

echo ""
echo "Starting services in background…"

# API
uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload &
API_PID=$!
echo "  API running (PID $API_PID) → http://localhost:8000"

# Workers
celery -A workers.celery_app worker -Q image  -c 1 --loglevel=warning &
celery -A workers.celery_app worker -Q video  -c 1 --loglevel=warning &
celery -A workers.celery_app worker -Q audio  -c 1 --loglevel=warning &
echo "  Celery workers started (image, video, audio queues)"

# UI
if command -v node &>/dev/null; then
  cd ui && npm install -s && npm run dev &
  echo "  UI running → http://localhost:3000"
  cd ..
fi

echo ""
echo "=== Ready! ==="
echo "API docs:  http://localhost:8000/docs"
echo "UI:        http://localhost:3000"
echo ""
echo "Create first API key:"
echo "  curl -X POST http://localhost:8000/v1/admin/keys \\"
echo "    -H 'Content-Type: application/json' \\"
echo "    -d '{\"name\": \"default\", \"credit_balance\": 10000}'"
echo ""
echo "Press Ctrl+C to stop"
wait

#!/bin/bash
# SwiftBook — Quick Start Script
set -e

cd "$(dirname "$0")"

echo "==================================================="
echo "  SwiftBook — Monetized Travel Search Engine"
echo "==================================================="
echo ""

# Load .env if it exists
if [ -f .env ]; then
  export $(grep -v '^#' .env | xargs 2>/dev/null)
  echo "  .env loaded"
else
  echo "  ⚠ No .env found — running with mock data"
  echo "  Copy .env.example to .env and add your Travelpayouts credentials"
  echo "  to start earning affiliate commissions."
  echo ""
fi

# Check monetization status
if [ -n "$TRAVELPAYOUTS_TOKEN" ]; then
  echo "  ✓ API Token: configured (real pricing data)"
else
  echo "  ✗ API Token: not set (using mock data)"
fi

if [ -n "$TRAVELPAYOUTS_MARKER" ]; then
  echo "  ✓ Affiliate Marker: active (earning commissions!)"
else
  echo "  ✗ Affiliate Marker: not set (no revenue yet)"
fi

if [ -n "$ADSENSE_PUB_ID" ]; then
  echo "  ✓ AdSense: active (ads will display)"
else
  echo "  · AdSense: not configured (optional)"
fi

echo ""

# Check Python
if ! command -v python3 &>/dev/null; then
  echo "  Python 3 is required. Install from https://python.org"
  exit 1
fi

# Create venv if needed
if [ ! -d "venv" ]; then
  echo "  Creating virtual environment..."
  python3 -m venv venv
fi

source venv/bin/activate
echo "  Installing dependencies..."
pip install -r requirements.txt -q

echo ""
echo "  SwiftBook is running!"
echo "  Open:      http://localhost:8000"
echo "  API docs:  http://localhost:8000/docs"
echo "  Revenue:   http://localhost:8000#admin"
echo "  Press Ctrl+C to stop"
echo ""

python3 -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload

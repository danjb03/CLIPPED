#!/usr/bin/env bash
#
# Start the Clip Engine worker locally: sets up the Python venv, installs the
# worker deps + the web deps (needed for Remotion rendering), and runs the API
# on :8000. First run is slow (it downloads ML models for transcription).
#
# Prereqs on PATH: python3.11, node 20+, ffmpeg, yt-dlp.
# Put your keys in .env.local at the repo root (see .env.local.example).
set -euo pipefail

cd "$(dirname "$0")/.."

echo "▶ checking prerequisites…"
for bin in python3.11 node ffmpeg yt-dlp; do
  command -v "$bin" >/dev/null || { echo "✗ missing '$bin' on PATH"; exit 1; }
done

echo "▶ python venv + worker deps…"
cd worker
python3.11 -m venv .venv 2>/dev/null || true
# shellcheck disable=SC1091
source .venv/bin/activate
pip install -q -r requirements.txt

echo "▶ web deps (for Remotion render)…"
( cd ../web && npm install --silent )

echo
echo "✓ starting worker on http://localhost:8000  (Ctrl+C to stop)"
exec uvicorn main:app --port 8000

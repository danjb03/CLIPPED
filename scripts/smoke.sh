#!/usr/bin/env bash
#
# End-to-end smoke test against a running worker.
# Runs the full pipeline (ingest -> transcribe -> select -> render -> copy ->
# carousels -> export) for one video URL and prints where the output landed.
#
# Requires: a running worker, ffmpeg + yt-dlp on PATH, ANTHROPIC_API_KEY (and
# HUGGINGFACE_TOKEN for diarisation). Set WORKER_URL to override the default.
#
# Usage:  scripts/smoke.sh <video_url> [count]
set -euo pipefail

WORKER="${WORKER_URL:-http://localhost:8000}"
URL="${1:?usage: scripts/smoke.sh <video_url> [count]}"
COUNT="${2:-2}"

get() { python3 -c "import sys,json;print(json.load(sys.stdin)['$1'])"; }
post() {
  curl -fsS -X POST "$WORKER/$1" -H 'content-type: application/json' -d "$2"
}

echo "→ health"
curl -fsS "$WORKER/health"; echo

echo "→ ingest"
JOB=$(post ingest "{\"url\":\"$URL\"}" | get job_id)
echo "  job_id: $JOB"

echo "→ transcribe"; post transcribe "{\"job_id\":\"$JOB\"}" >/dev/null
echo "→ select ($COUNT)"; post select "{\"job_id\":\"$JOB\",\"count\":$COUNT}" >/dev/null
echo "→ render"; post render "{\"job_id\":\"$JOB\"}" >/dev/null
echo "→ copy"; post copy "{\"job_id\":\"$JOB\"}" >/dev/null
echo "→ carousels"; post carousels "{\"job_id\":\"$JOB\"}" >/dev/null
echo "→ carousels/render"; post carousels/render "{\"job_id\":\"$JOB\"}" >/dev/null
echo "→ export"
ZIP=$(post export "{\"job_id\":\"$JOB\"}" | get export)

echo
echo "✓ done — output/$JOB/"
echo "  export: $ZIP"

#!/usr/bin/env bash
# Build the submission zip from the COMMITTED tree (git archive), so only tracked files are
# included: .env, .venv, caches, videos and the guide PDF are excluded by .gitignore.
# Fails on uncommitted changes, secrets, tracked videos, or a zip larger than 50 MB.
set -euo pipefail
cd "$(dirname "$0")/.."

PY=python
if [ -x .venv/Scripts/python.exe ]; then PY=.venv/Scripts/python.exe
elif [ -x .venv/bin/python ]; then PY=.venv/bin/python
elif ! command -v python >/dev/null 2>&1; then PY=python3   # macOS/Linux without a venv
fi

if [ -n "$(git status --porcelain)" ]; then
  echo "make_zip: uncommitted changes; commit first (the zip is built from HEAD)" >&2
  exit 1
fi
if git ls-files | grep -Eiq '\.(mp4|mov|mkv|avi|webm)$'; then
  echo "make_zip: video files are tracked; remove them" >&2
  exit 1
fi
"$PY" scripts/check_secrets.py

mkdir -p dist
OUT=dist/automata-synth-eval.zip
rm -f "$OUT"
git archive --format=zip --prefix=automata-synth-eval/ -o "$OUT" HEAD

SIZE=$(wc -c < "$OUT")
LIMIT=$((50 * 1024 * 1024))
if [ "$SIZE" -gt "$LIMIT" ]; then
  echo "make_zip: $OUT is $SIZE bytes (> 50 MB)" >&2
  exit 1
fi
echo "make_zip: wrote $OUT ($SIZE bytes, commit $(git rev-parse --short HEAD))"

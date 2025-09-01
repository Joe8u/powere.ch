#!/usr/bin/env bash
set -euo pipefail

BASE="https://www.powere.ch"

echo "== /dashboard/ =="
curl -sSI "$BASE/dashboard/" | head -n 10

echo
echo "== Dashboard Chunk =="
TMP=$(mktemp)
curl -sS "$BASE/dashboard/" -o "$TMP"
CHUNK=$(grep -o '/_astro/Dashboard[^"]*\.js' "$TMP" | head -1 || true)
rm -f "$TMP"

if [ -z "$CHUNK" ]; then
  echo "Konnte Dashboard-Chunk im HTML nicht finden."
  exit 1
fi

echo "Gefundener Chunk: $CHUNK"
curl -sSI "$BASE$CHUNK" | head -n 10

echo
echo "== API /warehouse/ping (mit CORS) =="
curl -i -H "Origin: $BASE" https://api.powere.ch/warehouse/ping | head -n 20

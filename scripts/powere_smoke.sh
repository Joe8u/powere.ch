#!/usr/bin/env bash
set -euo pipefail

API_LOCAL="${API_LOCAL:-http://127.0.0.1:9000}"
API_PUBLIC="${API_PUBLIC:-https://api.powere.ch}"

pp() { if command -v jq >/dev/null 2>&1; then jq .; else cat; fi }

echo "== Containers (optional) ============"
if [ -f /opt/stacks/powere-ch/docker-compose.yml ]; then
  docker compose -f /opt/stacks/powere-ch/docker-compose.yml ps || true
fi

echo "== Health (local) ===================="
curl -fsS "$API_LOCAL/healthz" | pp
curl -fsS "$API_LOCAL/readyz" | pp
curl -fsS "$API_LOCAL/v1/ping" | pp
if command -v jq >/dev/null 2>&1; then
  curl -fsS "$API_LOCAL/openapi.json" | jq -r '.paths | keys[]'
fi

echo "== JSON (local) ======================"
curl -fsS "$API_LOCAL/v1/search?q=Test&top_k=1" | pp
curl -fsS -X POST "$API_LOCAL/v1/chat" -H 'Content-Type: application/json' \
  -d '{"question":"Smoke test","top_k":1}' | pp

echo "== SSE (local, headers) ============="
curl -sS --max-time 8 -i -N -X POST "$API_LOCAL/v1/chat/stream?debug=1" \
  -H 'Accept: text/event-stream' -H 'Content-Type: application/json' \
  -d '{"question":"Stream-Check (local)","top_k":1}' | sed -n '1,40p' || true

echo "== Warehouse (local) ================"
curl -fsS "$API_LOCAL/warehouse/ping" | pp
curl -fsS "$API_LOCAL/warehouse/survey/wide?columns=respondent_id,age,gender&limit=3" | pp
curl -fsS "$API_LOCAL/warehouse/regelenergie/tertiary?agg=hour&limit=3" | pp
curl -fsS "$API_LOCAL/warehouse/lastprofile?year=2024&month=1&limit=3" | pp

echo "== JSON (public) ====================="
curl -fsS "$API_PUBLIC/v1/ping" | pp
curl -fsS "$API_PUBLIC/v1/search?q=Test&top_k=1" | pp

echo "== SSE (public, headers) ============"
curl -sS --max-time 8 -i -N -X POST "$API_PUBLIC/v1/chat/stream" \
  -H 'Accept: text/event-stream' -H 'Content-Type: application/json' \
  -d '{"question":"Stream-Check (public)","top_k":1}' | sed -n '1,40p' || true

echo "== SSE (public, ~10s) ==============="
timeout 10s curl -sS -N -X POST "$API_PUBLIC/v1/chat/stream" \
  -H 'Accept: text/event-stream' -H 'Content-Type: application/json' \
  -d '{"question":"Bitte lang antworten.","top_k":1}' >/dev/null || true

echo "== DONE =============================="

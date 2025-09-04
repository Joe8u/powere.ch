#scripts/smoke_warehouse.sh
set -euo pipefail

API_BASE="${API_BASE:-http://127.0.0.1:8000}"

echo "[SMOKE] joined (hour, total_mw, limit=3)" >&2
curl -sS "$API_BASE/warehouse/joined/mfrr_lastprofile?agg=hour&columns=total_mw&limit=3" | jq . || true

echo "[SMOKE] lastprofile (2024-01, limit=3)" >&2
curl -sS "$API_BASE/warehouse/lastprofile?year=2024&month=1&limit=3" | jq . || true

echo "[SMOKE] mFRR tertiary (day, limit=3)" >&2
curl -sS "$API_BASE/warehouse/regelenergie/tertiary?agg=day&limit=3" | jq . || true

echo "[SMOKE] survey wide (limit=3)" >&2
curl -sS "$API_BASE/warehouse/survey/wide?limit=3" | jq . || true


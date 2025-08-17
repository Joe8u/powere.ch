#!/usr/bin/env bash
set -euo pipefail
test -d steps/01_raw_data/survey && test -d steps/01_raw_data/lastprofile
echo "✅ Step 1 OK — raw-data Links vorhanden."

#!/usr/bin/env bash
set -euo pipefail
test -d steps/03_processed_data/survey && test -d steps/03_processed_data/lastprofile
echo "✅ Step 3 OK — processed-data Links vorhanden."

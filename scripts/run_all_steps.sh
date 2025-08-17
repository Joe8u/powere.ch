#!/usr/bin/env bash
set -euo pipefail
./scripts/setup.sh
./scripts/step1.sh
./scripts/step2.sh
./scripts/step3.sh
./scripts/step4.sh
./scripts/step5.sh
./scripts/step6.sh
echo "✅ All steps done."

#!/usr/bin/env bash
set -euo pipefail
export PYTHONPATH="."
python -m steps.step03_processed_data.check

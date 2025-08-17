#!/usr/bin/env bash
set -euo pipefail
export PYTHONPATH="."
python -m steps.step01_raw_data.check

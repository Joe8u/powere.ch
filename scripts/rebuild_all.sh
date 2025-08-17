#!/usr/bin/env bash
set -euo pipefail
python -m powere.etl.survey.run_all
python -m powere.etl.lastprofile.precompute

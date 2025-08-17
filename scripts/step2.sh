#!/usr/bin/env bash
set -euo pipefail
export PYTHONPATH="."
export POWERE_DATA_ROOT="$(pwd)/data"

echo ">>> Schreibe processed nach: $POWERE_DATA_ROOT/survey/processed"

python -m steps.02_preprocessing.survey.preprocess_q10_incentive_wide
python -m steps.02_preprocessing.survey.preprocess_q9_nonuse_wide
python -m steps.02_preprocessing.survey.preprocess_q13_income
python -m steps.02_preprocessing.survey.preprocess_q11_notify_optin
python -m steps.02_preprocessing.survey.preprocess_q12_smartplug
python -m steps.02_preprocessing.survey.preprocess_q14_education
python -m steps.02_preprocessing.survey.preprocess_q15_party

echo ">>> Check:"
ls -l "$POWERE_DATA_ROOT/survey/processed"/question_{10_incentive_wide,9_nonuse_wide,11_notify_optin,12_smartplug,13_income,14_education,15_party}.csv

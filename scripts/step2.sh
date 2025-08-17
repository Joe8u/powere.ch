#!/usr/bin/env bash
set -euo pipefail
export PYTHONPATH="."
export POWERE_DATA_ROOT="$(pwd)/data"
python -m steps.step02_preprocessing.survey.preprocess_q10_incentive_wide
python -m steps.step02_preprocessing.survey.preprocess_q9_nonuse_wide
python -m steps.step02_preprocessing.survey.preprocess_q13_income
python -m steps.step02_preprocessing.survey.preprocess_q11_notify_optin
python -m steps.step02_preprocessing.survey.preprocess_q12_smartplug
python -m steps.step02_preprocessing.survey.preprocess_q14_education
python -m steps.step02_preprocessing.survey.preprocess_q15_party

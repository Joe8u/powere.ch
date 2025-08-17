#!/usr/bin/env bash
set -euo pipefail

# Repo-Root ermitteln
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

RAW="$ROOT/data/survey/raw/Energieverbrauch und Teilnahmebereitschaft an Demand-Response-Programmen in Haushalten.csv"
OUT="$ROOT/data/survey/processed"

echo "[INFO] RAW:  $RAW"
echo "[INFO] OUT:  $OUT"

# Q1–Q15 der Reihe nach
python3 "$ROOT/processing/survey/jobs/preprocess_q1_age.py"
python3 "$ROOT/processing/survey/jobs/preprocess_q2_gender.py"
python3 "$ROOT/processing/survey/jobs/preprocess_q3_household_size.py"
python3 "$ROOT/processing/survey/jobs/preprocess_q4_accommodation.py"
python3 "$ROOT/processing/survey/jobs/preprocess_q5_electricity.py"
python3 "$ROOT/processing/survey/jobs/preprocess_q6_challenges.py"
python3 "$ROOT/processing/survey/jobs/preprocess_q7_consequence.py"
python3 "$ROOT/processing/survey/jobs/preprocess_q8_importance_wide.py"
python3 "$ROOT/processing/survey/jobs/preprocess_q9_nonuse_wide.py"
python3 "$ROOT/processing/survey/jobs/preprocess_q10_incentive_wide.py"
python3 "$ROOT/processing/survey/jobs/preprocess_q11_notify_optin.py"
python3 "$ROOT/processing/survey/jobs/preprocess_q12_smartplug.py"
python3 "$ROOT/processing/survey/jobs/preprocess_q13_income.py"
python3 "$ROOT/processing/survey/jobs/preprocess_q14_education.py"
python3 "$ROOT/processing/survey/jobs/preprocess_q15_party.py"

echo "[OK] Survey processed neu erzeugt."

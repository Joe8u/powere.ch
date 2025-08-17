from pathlib import Path
import pandas as pd

step_dir = Path(__file__).resolve().parent
sv = step_dir / "survey"
lp = step_dir / "lastprofile"

assert sv.is_symlink() and sv.resolve().is_dir(), f"survey-Link kaputt: {sv}"
assert lp.is_symlink() and lp.resolve().is_dir(), f"lastprofile-Link kaputt: {lp}"

must = [
    "question_10_incentive_wide.csv",
    "question_11_notify_optin.csv",
    "question_12_smartplug.csv",
    "question_13_income.csv",
    "question_14_education.csv",
    "question_15_party.csv",
    "question_9_nonuse_wide.csv",
]
missing = [m for m in must if not (sv.resolve()/m).exists()]
assert not missing, "Fehlende processed CSVs: " + ", ".join(missing)

df = pd.read_csv(sv.resolve()/"question_10_incentive_wide.csv")
assert "respondent_id" in df.columns and len(df) >= 300

print("✅ Step 3 OK — processed-Symlinks & Kern-Dateien vorhanden und plausibel.")

from __future__ import annotations
from pathlib import Path
import runpy
import pandas as pd

# DATA_ROOT beziehen (falls Step 4 noch nicht importierbar, Fallback auf repo/data)
try:
    from steps.step04_dataloaders.dataloaders.io import DATA_ROOT
except Exception:
    DATA_ROOT = Path(__file__).resolve().parents[2] / "data"

SURVEY_RAW = DATA_ROOT / "survey" / "raw"
SURVEY_OUT = DATA_ROOT / "survey" / "processed"
assert SURVEY_RAW.exists(), f"raw fehlt: {SURVEY_RAW}"
SURVEY_OUT.mkdir(parents=True, exist_ok=True)

REQUIRED = [
    ("question_10_incentive_wide.csv", "steps.step02_preprocessing.survey.preprocess_q10_incentive_wide", dict(min_rows=300, min_cols=10)),
    ("question_9_nonuse_wide.csv",    "steps.step02_preprocessing.survey.preprocess_q9_nonuse_wide",    dict(min_rows=300, min_cols=5)),
    ("question_11_notify_optin.csv",  "steps.step02_preprocessing.survey.preprocess_q11_notify_optin",  dict(min_rows=300, columns=["respondent_id","notify_optin"])),
    ("question_12_smartplug.csv",     "steps.step02_preprocessing.survey.preprocess_q12_smartplug",     dict(min_rows=300, columns=["respondent_id","smartplug"])),
    ("question_13_income.csv",        "steps.step02_preprocessing.survey.preprocess_q13_income",        dict(min_rows=300, columns=["respondent_id","q13_income"])),
    ("question_14_education.csv",     "steps.step02_preprocessing.survey.preprocess_q14_education",     dict(min_rows=300, columns=["respondent_id","q14_education"])),
    ("question_15_party.csv",         "steps.step02_preprocessing.survey.preprocess_q15_party",         dict(min_rows=300, columns=["respondent_id","q15_party"])),
]

def ensure_generated(path: Path, module: str) -> None:
    if not path.exists():
        runpy.run_module(module, run_name="__main__")

def validate_csv(path: Path, expect: dict) -> None:
    df = pd.read_csv(path)
    assert not df.empty, f"{path.name} ist leer"
    if "min_rows" in expect:
        assert len(df) >= expect["min_rows"], f"{path.name}: zu wenig Zeilen ({len(df)})"
    if "min_cols" in expect:
        assert df.shape[1] >= expect["min_cols"], f"{path.name}: zu wenig Spalten ({df.shape[1]})"
    for col in expect.get("columns", []):
        assert col in df.columns, f"{path.name}: Spalte fehlt: {col}"

created = []
for fname, module, exp in REQUIRED:
    p = SURVEY_OUT / fname
    before = p.exists()
    ensure_generated(p, module)
    assert p.exists(), f"{fname} wurde nicht erzeugt"
    validate_csv(p, exp)
    if not before:
        created.append(fname)

print("✅ Step 2 OK — ETL-Dateien vorhanden & validiert.", ("Neu erzeugt: " + ", ".join(created)) if created else "")

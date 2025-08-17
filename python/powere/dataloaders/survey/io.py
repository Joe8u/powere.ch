from __future__ import annotations
from pathlib import Path
import pandas as pd
from ..common import DATA_ROOT

PROC = DATA_ROOT / "survey" / "processed"

Q_FILES = {
    "q1_age": "question_1_age.csv",
    "q2_gender": "question_2_gender.csv",
    "q3_household_size": "question_3_household_size.csv",
    "q4_accommodation": "question_4_accommodation.csv",
    "q5_electricity": "question_5_electricity.csv",
    "q6_challenges": "question_6_challenges.csv",
    "q7_consequence": "question_7_consequence.csv",
    "q8_importance_wide": "question_8_importance_wide.csv",
    "q9_nonuse_wide": "question_9_nonuse_wide.csv",
    "q10_incentive_wide": "question_10_incentive_wide.csv",
    "q11_notify_optin": "question_11_notify_optin.csv",
    "q12_smartplug": "question_12_smartplug.csv",
    "q13_income": "question_13_income.csv",
    "q14_education": "question_14_education.csv",
    "q15_party": "question_15_party.csv",
}

def _load(name: str) -> pd.DataFrame:
    path = PROC / Q_FILES[name]
    return pd.read_csv(path, dtype={"respondent_id": str})

# bequeme Wrapper (IDE-Autocomplete)
def q1_age(): return _load("q1_age")
def q2_gender(): return _load("q2_gender")
def q3_household_size(): return _load("q3_household_size")
def q4_accommodation(): return _load("q4_accommodation")
def q5_electricity(): return _load("q5_electricity")
def q6_challenges(): return _load("q6_challenges")
def q7_consequence(): return _load("q7_consequence")
def q8_importance_wide(): return _load("q8_importance_wide")
def q9_nonuse_wide(): return _load("q9_nonuse_wide")
def q10_incentive_wide(): return _load("q10_incentive_wide")
def q11_notify_optin(): return _load("q11_notify_optin")
def q12_smartplug(): return _load("q12_smartplug")
def q13_income(): return _load("q13_income")
def q14_education(): return _load("q14_education")
def q15_party(): return _load("q15_party")

def join_demographics() -> pd.DataFrame:
    """Merge der wichtigsten Demografie-Antworten (outer, damit nichts verloren geht)."""
    dfs = [
        q1_age(), q2_gender(), q3_household_size(), q4_accommodation(),
        q13_income(), q14_education(), q15_party()
    ]
    out = dfs[0]
    for d in dfs[1:]:
        out = out.merge(d, on="respondent_id", how="outer")
    return out

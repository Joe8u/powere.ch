from pathlib import Path
import pandas as pd
from ..common import DATA_ROOT

PROC = Path(DATA_ROOT) / "survey" / "processed"

def _p(name: str) -> Path:
    return PROC / name

# Einzelfragen ---------------------------------------------------------------
def q1_age() -> pd.DataFrame:
    return pd.read_csv(_p("question_1_age.csv"), dtype={"respondent_id": str})

def q2_gender() -> pd.DataFrame:
    return pd.read_csv(_p("question_2_gender.csv"), dtype={"respondent_id": str})

def q3_household_size() -> pd.DataFrame:
    return pd.read_csv(_p("question_3_household_size.csv"), dtype={"respondent_id": str})

def q4_accommodation() -> pd.DataFrame:
    return pd.read_csv(_p("question_4_accommodation.csv"), dtype={"respondent_id": str})

def q5_electricity() -> pd.DataFrame:
    return pd.read_csv(_p("question_5_electricity.csv"), dtype={"respondent_id": str})

def q6_challenges() -> pd.DataFrame:
    return pd.read_csv(_p("question_6_challenges.csv"), dtype={"respondent_id": str})

def q7_consequence() -> pd.DataFrame:
    return pd.read_csv(_p("question_7_consequence.csv"), dtype={"respondent_id": str})

def q8_importance_wide() -> pd.DataFrame:
    return pd.read_csv(_p("question_8_importance_wide.csv"), dtype={"respondent_id": str})

def q9_nonuse_wide() -> pd.DataFrame:
    return pd.read_csv(_p("question_9_nonuse_wide.csv"), dtype={"respondent_id": str})

def q10_incentive_wide() -> pd.DataFrame:
    return pd.read_csv(_p("question_10_incentive_wide.csv"), dtype={"respondent_id": str})

def q11_notify_optin() -> pd.DataFrame:
    return pd.read_csv(_p("question_11_notify_optin.csv"), dtype={"respondent_id": str})

def q12_smartplug() -> pd.DataFrame:
    return pd.read_csv(_p("question_12_smartplug.csv"), dtype={"respondent_id": str})

def q13_income() -> pd.DataFrame:
    # processed enthält bereits Min/Max/Mid; wir lesen sie nur ein
    return pd.read_csv(_p("question_13_income.csv"), dtype={"respondent_id": str})

def q14_education() -> pd.DataFrame:
    return pd.read_csv(_p("question_14_education.csv"), dtype={"respondent_id": str})

def q15_party() -> pd.DataFrame:
    return pd.read_csv(_p("question_15_party.csv"), dtype={"respondent_id": str})

# Joins ---------------------------------------------------------------------
def join_demographics() -> pd.DataFrame:
    """
    Basis-Demografie: Age, Gender, Household Size, Accommodation, Income (+numeric ranges)
    """
    df = q1_age()
    for adder in (q2_gender, q3_household_size, q4_accommodation, q13_income):
        df = df.merge(adder(), on="respondent_id", how="left")
    return df

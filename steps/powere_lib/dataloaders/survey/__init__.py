"""Survey dataloaders."""
from .attitudes import load_attitudes, load_challenges, load_consequence
from .demand_response import (
    load_demand_response, load_importance, load_notification, load_smart_plug
)
from .demographics import (
    load_demographics, load_age, load_gender, load_household_size,
    load_accommodation, load_electricity
)
from .incentives import load_incentives, load_question_10_incentives
from .nonuse import load_nonuse, load_question_9_nonuse
from .socioeconomics import (
    load_socioeconomics, load_income, load_education, load_party_pref
)

__all__ = [
    "load_attitudes", "load_challenges", "load_consequence",
    "load_demand_response", "load_importance", "load_notification", "load_smart_plug",
    "load_demographics", "load_age", "load_gender", "load_household_size",
    "load_accommodation", "load_electricity",
    "load_incentives", "load_question_10_incentives",
    "load_nonuse", "load_question_9_nonuse",
    "load_socioeconomics", "load_income", "load_education", "load_party_pref",
    # Back-compat für älteren API-Code:
    "q10_incentive_wide", "q13_income", "join_demographics",
]

# --- Back-compat Wrapper ---
def q10_incentive_wide():
    return load_incentives()

def q13_income():
    return load_income()

def join_demographics():
    import pandas as pd
    from functools import reduce
    dfs = load_demographics()
    frames = [df for df in dfs.values() if not df.empty]
    if not frames:
        return pd.DataFrame()
    return reduce(lambda l, r: l.merge(r, on="respondent_id", how="outer"), frames)

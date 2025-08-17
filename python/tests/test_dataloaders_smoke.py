import pandas as pd
from datetime import datetime
from powere.dataloaders.survey import (
    load_attitudes, load_demand_response, load_demographics,
    load_incentives, load_nonuse, load_socioeconomics
)
from powere.dataloaders.lastprofile import (
    list_appliances, load_month, load_range, load_appliances
)

def _nonempty(df: pd.DataFrame) -> bool:
    return isinstance(df, pd.DataFrame) and not df.empty

def test_survey_min():
    att = load_attitudes();       assert all(_nonempty(v) for v in att.values())
    dr  = load_demand_response(); assert all(_nonempty(v) for v in dr.values())
    dem = load_demographics();    assert all(_nonempty(v) for v in dem.values())
    inc = load_incentives();      assert _nonempty(inc) and "respondent_id" in inc.columns
    non = load_nonuse();          assert _nonempty(non) and "respondent_id" in non.columns
    soc = load_socioeconomics();  assert all(_nonempty(v) for v in soc.values())

def test_lastprofile_min():
    assert len(list_appliances(2024)) >= 1
    m = load_month(2024, 1)
    assert _nonempty(m) and str(m.index.dtype).startswith("datetime64")
    r = load_range(datetime(2024,1,1), datetime(2024,1,2))
    assert _nonempty(r)
    sub = load_appliances(["Geschirrspüler","Waschmaschine"],
                          datetime(2024,1,1), datetime(2024,1,2), group=True)
    assert _nonempty(sub) and set(sub.columns) <= {"Geschirrspüler","Waschmaschine"}

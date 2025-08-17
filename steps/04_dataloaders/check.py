from datetime import datetime
from pathlib import Path
import sys
import pandas as pd
from steps.powere_lib.dataloaders.io import DATA_ROOT
from steps.powere_lib.dataloaders.lastprofile import list_appliances, load_month, load_range, load_appliances
from steps.powere_lib.dataloaders.survey import (
    load_attitudes, load_demand_response, load_demographics,
    load_incentives, load_nonuse, load_socioeconomics
)

def must_exist(paths: list[Path]) -> None:
    missing = [str(p) for p in paths if not p.exists()]
    if missing:
        print("❌ Fehlende Dateien:\n  - " + "\n  - ".join(missing))
        sys.exit(1)

# 1) Dateien prüfen
required = [
    DATA_ROOT / "survey/processed/q10_incentive_wide.csv",
    DATA_ROOT / "survey/processed/q9_nonuse_wide.csv",
    DATA_ROOT / "survey/processed/q13_income.csv",
]
must_exist(required)

# 2) Loader prüfen (nicht-leer)
def _nonempty(df: pd.DataFrame) -> bool:
    return isinstance(df, pd.DataFrame) and not df.empty

att = load_attitudes();       assert all(_nonempty(v) for v in att.values())
dr  = load_demand_response(); assert all(_nonempty(v) for v in dr.values())
dem = load_demographics();    assert all(_nonempty(v) for v in dem.values())
inc = load_incentives();      assert _nonempty(inc) and "respondent_id" in inc.columns
non = load_nonuse();          assert _nonempty(non) and "respondent_id" in non.columns
soc = load_socioeconomics();  assert all(_nonempty(v) for v in soc.values())

# 3) lastprofile
assert len(list_appliances(2024)) >= 1
m = load_month(2024, 1); assert _nonempty(m) and str(m.index.dtype).startswith("datetime64")
r = load_range(datetime(2024,1,1), datetime(2024,1,2)); assert _nonempty(r)
sub = load_appliances(["Geschirrspüler","Waschmaschine"], datetime(2024,1,1), datetime(2024,1,2), group=True)
assert _nonempty(sub) and set(sub.columns) <= {"Geschirrspüler","Waschmaschine"}

print("✅ Step 4 OK — alle Dataloader- und Datei-Checks bestanden.")
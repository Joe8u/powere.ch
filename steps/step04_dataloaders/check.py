from __future__ import annotations

from datetime import datetime
from pathlib import Path
import sys
import pandas as pd

# 1) Dataloader-Imports: erst unter Step 04, sonst Fallback auf powere_lib
try:
    from .dataloaders.io import DATA_ROOT
    from .dataloaders.lastprofile import (
        list_appliances, load_month, load_range, load_appliances
    )
    from .dataloaders.survey import (
        load_attitudes, load_demand_response, load_demographics,
        load_incentives, load_nonuse, load_socioeconomics
    )
except Exception:
    from steps.lib.dataloaders.io import DATA_ROOT
    from steps.lib.dataloaders.lastprofile import (
        list_appliances, load_month, load_range, load_appliances
    )
    from steps.lib.dataloaders.survey import (
        load_attitudes, load_demand_response, load_demographics,
        load_incentives, load_nonuse, load_socioeconomics
    )

def must_exist_any(pairs: list[tuple[str, str]]) -> None:
    missing: list[tuple[str, str]] = []
    base = DATA_ROOT / "survey" / "processed"
    for a, b in pairs:
        if not ((base / a).exists() or (base / b).exists()):
            missing.append((a, b))
    if missing:
        print("❌ Fehlende Dateien (mind. eine Variante pro Zeile ausreichend):")
        for a, b in missing:
            print(f"  - {a} ODER {b}")
        sys.exit(1)

# 2) Dateien prüfen (neue "question_*" ODER alte "q*")
must_exist_any([
    ("question_10_incentive_wide.csv", "q10_incentive_wide.csv"),
    ("question_9_nonuse_wide.csv",    "q9_nonuse_wide.csv"),
    ("question_11_notify_optin.csv",  "q11_notify_optin.csv"),
    ("question_12_smartplug.csv",     "q12_smartplug.csv"),
    ("question_13_income.csv",        "q13_income.csv"),
    ("question_14_education.csv",     "q14_education.csv"),
    ("question_15_party.csv",         "q15_party.csv"),
])

# 3) Loader prüfen (nicht-leer)
def _nonempty(df: pd.DataFrame) -> bool:
    return isinstance(df, pd.DataFrame) and not df.empty

att = load_attitudes();       assert all(_nonempty(v) for v in att.values())
dr  = load_demand_response(); assert all(_nonempty(v) for v in dr.values())
dem = load_demographics();    assert all(_nonempty(v) for v in dem.values())
inc = load_incentives();      assert _nonempty(inc) and "respondent_id" in inc.columns
non = load_nonuse();          assert _nonempty(non) and "respondent_id" in non.columns
soc = load_socioeconomics();  assert all(_nonempty(v) for v in soc.values())

# 4) Lastprofile prüfen
assert len(list_appliances(2024)) >= 1
m = load_month(2024, 1);      assert _nonempty(m) and str(m.index.dtype).startswith("datetime64")
r = load_range(datetime(2024,1,1), datetime(2024,1,2)); assert _nonempty(r)
sub = load_appliances(["Geschirrspüler","Waschmaschine"], datetime(2024,1,1), datetime(2024,1,2), group=True)
assert _nonempty(sub) and set(sub.columns) <= {"Geschirrspüler","Waschmaschine"}

print("✅ Step 4 OK — alle Dataloader- und Datei-Checks bestanden.")

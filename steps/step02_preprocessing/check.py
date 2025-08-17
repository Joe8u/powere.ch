from __future__ import annotations
from pathlib import Path
import pandas as pd
import sys

try:
    # zentrale Pfadlogik wiederverwenden
    from steps.step04_dataloaders.dataloaders.io import DATA_ROOT
except Exception:
    # Fallback: Repo-Root = drei Ebenen über dieser Datei
    DATA_ROOT = Path(__file__).resolve().parents[2] / "data"

RAW = DATA_ROOT / "survey/raw/Energieverbrauch und Teilnahmebereitschaft an Demand-Response-Programmen in Haushalten.csv"
OUT = DATA_ROOT / "survey/processed"

REQUIRED = [
    "question_10_incentive_wide.csv",
    "question_9_nonuse_wide.csv",
    "question_11_notify_optin.csv",
    "question_12_smartplug.csv",
    "question_13_income.csv",
    "question_14_education.csv",
    "question_15_party.csv",
]

def must_exist(path: Path) -> pd.DataFrame:
    assert path.exists(), f"❌ fehlt: {path}"
    assert path.stat().st_size > 0, f"❌ leer: {path}"
    df = pd.read_csv(path)
    assert not df.empty, f"❌ DataFrame leer: {path.name}"
    return df

problems = []

# Dateien prüfen
dfs = {}
for name in REQUIRED:
    try:
        dfs[name] = must_exist(OUT / name)
    except AssertionError as e:
        problems.append(str(e))

# Invarianten (leichtgewichtig)
def approx(n, target, tol=5):  # ±5 Zeilen Toleranz
    return abs(n - target) <= tol

try:
    inc = dfs.get("question_10_incentive_wide.csv")
    if inc is not None:
        assert "respondent_id" in inc.columns, "❌ respondent_id fehlt in Q10"
        assert approx(len(inc), 372), f"❌ Q10 Zeilen unplausibel: {len(inc)}"
except AssertionError as e:
    problems.append(str(e))

try:
    non = dfs.get("question_9_nonuse_wide.csv")
    if non is not None:
        assert "respondent_id" in non.columns, "❌ respondent_id fehlt in Q9"
        assert approx(len(non), 372), f"❌ Q9 Zeilen unplausibel: {len(non)}"
except AssertionError as e:
    problems.append(str(e))

try:
    incm = dfs.get("question_13_income.csv")
    if incm is not None:
        assert "q13_income" in incm.columns, "❌ q13_income fehlt"
        assert approx(len(incm), 372), f"❌ Q13 Zeilen unplausibel: {len(incm)}"
except AssertionError as e:
    problems.append(str(e))

# Freshness (optional, nur wenn RAW existiert)
if RAW.exists():
    raw_mtime = RAW.stat().st_mtime
    stale = [n for n in REQUIRED if (OUT / n).exists() and (OUT / n).stat().st_mtime < raw_mtime]
    if stale:
        problems.append("⚠️ Outputs älter als RAW: " + ", ".join(stale))

if problems:
    print("❌ Step 2 CHECKS fehlgeschlagen:\n  - " + "\n  - ".join(problems))
    sys.exit(1)

print("✅ Step 2 OK — ETL-Outputs vorhanden & plausibel.")

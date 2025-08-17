from pathlib import Path
import pandas as pd
from powere.dataloaders.io import DATA_ROOT

# Datei im Wide-Format für Frage 10
_INCENTIVE_FILE = "question_10_incentive_wide.csv"

def load_incentives() -> pd.DataFrame:
    """
    Lädt <DATA_ROOT>/survey/processed/question_10_incentive_wide.csv
    und gibt sie als DataFrame (alle Spalten als string) zurück.
    """
    path = DATA_ROOT / "survey" / "processed" / _INCENTIVE_FILE
    if not path.is_file():
        raise FileNotFoundError(f"Incentive-Datei nicht gefunden: {path}")
    return pd.read_csv(path, dtype=str, encoding="utf-8")

# Alias für Rückwärtskompatibilität mit altem Namen
def load_question_10_incentives() -> pd.DataFrame:
    return load_incentives()

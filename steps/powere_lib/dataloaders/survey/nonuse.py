from pathlib import Path
import pandas as pd
from ..io import DATA_ROOT

_NONUSE_FILE = "question_9_nonuse_wide.csv"

def load_nonuse() -> pd.DataFrame:
    """
    Lädt <DATA_ROOT>/survey/processed/question_9_nonuse_wide.csv
    und gibt ein DataFrame (alle Spalten als string) zurück.
    """
    path = DATA_ROOT / "survey" / "processed" / _NONUSE_FILE
    if not path.is_file():
        raise FileNotFoundError(f"Nonuse-Datei nicht gefunden: {path}")
    return pd.read_csv(path, dtype=str, encoding="utf-8")

# Alias für Rückwärtskompatibilität
def load_question_9_nonuse() -> pd.DataFrame:
    return load_nonuse()

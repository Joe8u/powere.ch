from __future__ import annotations
from pathlib import Path
import pandas as pd
import numpy as np
from ..io import DATA_ROOT  # -> .../data

# Verarbeitete Dateien (Q6/Q7) im neuen Layout
PROCESSED_DIR = DATA_ROOT / "survey" / "processed"
FILES = {
    "challenges":   "question_6_challenges.csv",
    "consequence":  "question_7_consequence.csv",
}

def _read_csv_safe(path: Path) -> pd.DataFrame:
    if not path.is_file():
        print(f"WARNUNG [attitudes]: Datei nicht gefunden: {path}. Leeres DataFrame.")
        return pd.DataFrame()
    try:
        df = pd.read_csv(path, dtype=str, encoding="utf-8")
        if not df.empty:
            if "respondent_id" in df.columns:
                df["respondent_id"] = df["respondent_id"].str.replace(r"\.0$", "", regex=True)
                df["respondent_id"] = (
                    df["respondent_id"]
                    .replace(r"^\s*$", np.nan, regex=True)
                    .replace("nan", np.nan)
                )
                df.dropna(subset=["respondent_id"], inplace=True)
            else:
                print(f"WARNUNG [attitudes]: Spalte 'respondent_id' fehlt in {path.name}.")
        return df
    except Exception as e:
        print(f"FEHLER [attitudes] beim Lesen {path}: {e}")
        return pd.DataFrame()

def load_attitudes() -> dict[str, pd.DataFrame]:
    """Lädt Q6 (challenges) und Q7 (consequence) als Dict."""
    return {k: _read_csv_safe(PROCESSED_DIR / fname) for k, fname in FILES.items()}

# Bequeme Direkt-Lader (optional)
def load_challenges() -> pd.DataFrame:
    return _read_csv_safe(PROCESSED_DIR / FILES["challenges"])

def load_consequence() -> pd.DataFrame:
    return _read_csv_safe(PROCESSED_DIR / FILES["consequence"])

if __name__ == "__main__":
    dfs = load_attitudes()
    for k, v in dfs.items():
        print(f"{k}: {v.shape}")

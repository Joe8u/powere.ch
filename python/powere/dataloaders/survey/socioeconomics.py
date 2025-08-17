from pathlib import Path
import numpy as np
import pandas as pd
from powere.dataloaders.io import DATA_ROOT

PROCESSED_DIR = DATA_ROOT / "survey" / "processed"

FILES = {
    "income":     "question_13_income.csv",
    "education":  "question_14_education.csv",
    "party_pref": "question_15_party.csv",
}

def _read_csv_safe(path: Path, *, key: str = "") -> pd.DataFrame:
    try:
        if not path.is_file():
            print(f"WARNUNG [socioeconomics]: Datei fehlt: {path}")
            return pd.DataFrame()
        df = pd.read_csv(path, dtype=str, encoding="utf-8")
        if not df.empty:
            if "respondent_id" in df.columns:
                df["respondent_id"] = (
                    df["respondent_id"].astype(str)
                    .str.replace(r"\.0$", "", regex=True)
                    .replace(r"^\s*$", np.nan, regex=True)
                    .replace("nan", np.nan)
                )
                df.dropna(subset=["respondent_id"], inplace=True)
            else:
                print(f"WARNUNG [socioeconomics]: 'respondent_id' fehlt in {path.name}")
        return df
    except Exception as e:
        print(f"FEHLER [socioeconomics] beim Lesen {path}: {e}")
        return pd.DataFrame()

def load_socioeconomics() -> dict[str, pd.DataFrame]:
    return {k: _read_csv_safe(PROCESSED_DIR / f, key=k) for k, f in FILES.items()}

# Convenience-Funktionen
def load_income() -> pd.DataFrame:
    return _read_csv_safe(PROCESSED_DIR / FILES["income"], key="income")

def load_education() -> pd.DataFrame:
    return _read_csv_safe(PROCESSED_DIR / FILES["education"], key="education")

def load_party_pref() -> pd.DataFrame:
    return _read_csv_safe(PROCESSED_DIR / FILES["party_pref"], key="party_pref")

if __name__ == "__main__":
    dfs = load_socioeconomics()
    for k, v in dfs.items():
        print(f"{k}: {v.shape}")

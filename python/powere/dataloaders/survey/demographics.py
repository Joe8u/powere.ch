import pandas as pd
import numpy as np
from pathlib import Path
from ..io import DATA_ROOT

# Verzeichnis der verarbeiteten Survey-Daten
PROCESSED_DIR = DATA_ROOT / "survey" / "processed"

FILES = {
    "age":            "question_1_age.csv",
    "gender":         "question_2_gender.csv",
    "household_size": "question_3_household_size.csv",
    "accommodation":  "question_4_accommodation.csv",
    "electricity":    "question_5_electricity.csv",
}

def _read_csv_safe(path: Path, *, key: str | None = None) -> pd.DataFrame:
    df = pd.DataFrame()
    if not path.is_file():
        print(f"WARNUNG [demographics]: Datei fehlt: {path}")
        return df
    try:
        df = pd.read_csv(path, dtype=str, encoding="utf-8")
        if not df.empty:
            if "respondent_id" in df.columns:
                s = df["respondent_id"].astype(str).str.replace(r"\.0$", "", regex=True)
                s = s.replace(r"^\s*$", np.nan, regex=True).replace("nan", np.nan)
                df["respondent_id"] = s
                df.dropna(subset=["respondent_id"], inplace=True)
            else:
                print(f"WARNUNG [demographics]: 'respondent_id' fehlt in {path.name}")

            # optionale Typkonvertierungen
            if key == "age" and "age" in df.columns:
                df["age"] = pd.to_numeric(df["age"], errors="coerce")
            if key == "household_size" and "household_size" in df.columns:
                df["household_size"] = pd.to_numeric(df["household_size"], errors="coerce")
        return df
    except Exception as e:
        print(f"FEHLER [demographics] beim Lesen {path}: {e}")
        return pd.DataFrame()

def load_demographics() -> dict[str, pd.DataFrame]:
    return {k: _read_csv_safe(PROCESSED_DIR / fname, key=k) for k, fname in FILES.items()}

# Bequeme Direkt-Funktionen
def load_age() -> pd.DataFrame:            return _read_csv_safe(PROCESSED_DIR / FILES["age"], key="age")
def load_gender() -> pd.DataFrame:         return _read_csv_safe(PROCESSED_DIR / FILES["gender"], key="gender")
def load_household_size() -> pd.DataFrame: return _read_csv_safe(PROCESSED_DIR / FILES["household_size"], key="household_size")
def load_accommodation() -> pd.DataFrame:  return _read_csv_safe(PROCESSED_DIR / FILES["accommodation"], key="accommodation")
def load_electricity() -> pd.DataFrame:    return _read_csv_safe(PROCESSED_DIR / FILES["electricity"], key="electricity")

if __name__ == "__main__":
    dfs = load_demographics()
    for k, v in dfs.items():
        print(f"{k}: {v.shape}")

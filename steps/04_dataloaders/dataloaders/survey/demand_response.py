import pandas as pd
import numpy as np
from pathlib import Path
from ..io import DATA_ROOT

# Verzeichnis der verarbeiteten Survey-Daten
PROCESSED_DIR = DATA_ROOT / "survey" / "processed"

# Dateinamen in deinem Repo
_FILES = {
    "importance":   "question_8_importance_wide.csv",
    "notification": "question_11_notify_optin.csv",
    "smart_plug":   "question_12_smartplug.csv",
}

def _read_csv_safe(path: Path) -> pd.DataFrame:
    df = pd.DataFrame()
    if not path.is_file():
        print(f"WARNUNG [demand_response]: Datei fehlt: {path}")
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
                print(f"WARNUNG [demand_response]: 'respondent_id' fehlt in {path.name}")
        return df
    except Exception as e:
        print(f"FEHLER [demand_response] beim Lesen {path}: {e}")
        return pd.DataFrame()

def load_demand_response() -> dict[str, pd.DataFrame]:
    keys = ["importance", "notification", "smart_plug"]
    return {k: _read_csv_safe(PROCESSED_DIR / _FILES[k]) for k in keys}

def load_importance() -> pd.DataFrame:
    return _read_csv_safe(PROCESSED_DIR / _FILES["importance"])

def load_notification() -> pd.DataFrame:
    return _read_csv_safe(PROCESSED_DIR / _FILES["notification"])

def load_smart_plug() -> pd.DataFrame:
    return _read_csv_safe(PROCESSED_DIR / _FILES["smart_plug"])

if __name__ == "__main__":
    dfs = load_demand_response()
    for k, v in dfs.items():
        print(k, v.shape)

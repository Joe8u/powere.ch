from datetime import datetime
from steps.step04_dataloaders.dataloaders.lastprofile import list_appliances
from steps.step04_dataloaders.dataloaders.survey import load_incentives, load_nonuse
import pandas as pd

def _nonempty(df: pd.DataFrame) -> bool:
    return isinstance(df, pd.DataFrame) and not df.empty

def main():
    inc = load_incentives()
    non = load_nonuse()
    assert _nonempty(inc) and "respondent_id" in inc.columns
    assert _nonempty(non) and "respondent_id" in non.columns
    assert len(list_appliances(2024)) >= 1
    print("✅ step06: Import ok & Daten erreichbar")

if __name__ == "__main__":
    main()

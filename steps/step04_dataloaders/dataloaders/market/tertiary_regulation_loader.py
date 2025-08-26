# steps/step04_dataloaders/dataloaders/market/tertiary_regulation_loader.py
from __future__ import annotations

from pathlib import Path
from typing import List
import datetime as dt
import pandas as pd

# ---------------------------------------------------------------------
# Basisverzeichnisse: bevorzugt data/market/processed/regelenergie,
# Fallback: steps/step03_processed_data/market/regelenergie
# ---------------------------------------------------------------------
def _project_root_from_file() -> Path:
    here = Path(__file__).resolve()
    for p in here.parents:
        if p.name == "steps":
            return p.parent
    return here.parents[4] if len(here.parents) >= 5 else Path.cwd()

PROJECT_ROOT = _project_root_from_file()
PROCESSED_PRIMARY = PROJECT_ROOT / "data" / "market" / "processed" / "regelenergie"
PROCESSED_MIRROR  = PROJECT_ROOT / "steps" / "step03_processed_data" / "market" / "regelenergie"

def _base_dir() -> Path:
    if PROCESSED_PRIMARY.exists():
        return PROCESSED_PRIMARY
    if PROCESSED_MIRROR.exists():
        return PROCESSED_MIRROR
    return PROCESSED_PRIMARY  # Standardpfad; Fehler kommt dann beim Datei-Zugriff

# ---------------------------------------------------------------------
# Öffentliche API
# ---------------------------------------------------------------------
def list_regulation_months(year: int) -> List[int]:
    """
    Gibt eine sortierte Liste der verfügbaren Monate (1..12) zurück.
    Sucht in data/market/processed/regelenergie (Fallback: Mirror in steps/...).
    """
    base = _base_dir()
    months: List[int] = []
    for f in base.glob(f"{year}-[0-1][0-9].csv"):
        try:
            months.append(int(f.stem.split("-")[1]))
        except Exception:
            pass
    return sorted(set(months))


def load_regulation_month(
    year: int,
    month: int,
    *,
    tz: str = "Europe/Zurich",
) -> pd.DataFrame:
    """
    Lädt eine Monatsdatei mit Spalten:
      - timestamp (naiv)
      - total_called_mw
      - avg_price_eur_mwh

    Rückgabe: DataFrame mit Index=timestamp.
    Verhalten: naive Zeitstempel werden als Europe/Zurich lokalisiert und
    anschließend tz-untagged (entspricht der bisherigen Logik).
    """
    path = _base_dir() / f"{year}-{month:02d}.csv"
    if not path.exists():
        raise FileNotFoundError(path)

    df = pd.read_csv(path, parse_dates=["timestamp"])


    if tz:
        # Lokalisieren (DST-robust), dann TZ DROPPEN (Wall-Time behalten)
        try:
            ts = df["timestamp"].dt.tz_localize(
                tz, ambiguous="infer", nonexistent="shift_forward"
            )
        except Exception:
            # Fallback, falls "infer" scheitert
            ts = df["timestamp"].dt.tz_localize(
                tz, ambiguous="NaT", nonexistent="NaT"
            )
        df["timestamp"] = ts.dt.tz_localize(None)

    # Jetzt als Index zurückgeben
    return df.set_index("timestamp").sort_index()


def load_regulation_range(
    start: dt.datetime,
    end:   dt.datetime,
    *,
    tz: str = "Europe/Zurich",
) -> pd.DataFrame:
    """
    Lädt zusammenhängend Daten im Bereich [start, end].
    Hinweis: start und end müssen im selben Jahr liegen.
    Robust gegen Endzeitpunkte, die nicht exakt im Index liegen
    (z. B. 23:59:59 bei 15-Min-Raster).
    """
    if start.year != end.year:
        raise ValueError("Start und Enddatum müssen im selben Jahr liegen.")

    month_from = min(start.month, end.month)
    month_to   = max(start.month, end.month)
    parts = [load_regulation_month(start.year, m, tz=tz) for m in range(month_from, month_to + 1)]
    df = pd.concat(parts).sort_index()

    # Naiv sicherstellen (Loader gibt naive Timestamps zurück)
    if getattr(start, "tzinfo", None) is not None:
        start = start.replace(tzinfo=None)
    if getattr(end, "tzinfo", None) is not None:
        end = end.replace(tzinfo=None)

    # An Indexbereich klammern und mit Bool-Maske filtern
    idx_min = df.index.min()
    idx_max = df.index.max()
    start_clamped = max(start, idx_min)
    end_clamped   = min(end,   idx_max)

    return df[(df.index >= start_clamped) & (df.index <= end_clamped)]

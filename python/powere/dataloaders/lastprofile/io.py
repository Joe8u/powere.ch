from __future__ import annotations
from pathlib import Path
import datetime as dt
import pandas as pd
from ..common import DATA_ROOT

# processed/2024 enthält bereits aggregierte Survey-Kategorien als Spalten
GROUP_MAP = {
    "Geschirrspüler": ["Geschirrspüler"],
    "Backofen und Herd": ["Backofen und Herd"],
    "Fernseher und Entertainment-Systeme": ["Fernseher und Entertainment-Systeme"],
    "Bürogeräte": ["Bürogeräte"],
    "Waschmaschine": ["Waschmaschine"],
}

def _processed_dir(year: int) -> Path:
    return DATA_ROOT / "lastprofile" / "processed" / str(year)

def list_appliances(year: int, *, group: bool = False) -> list[str]:
    sample = _processed_dir(year) / f"{year}-01.csv"
    cols = pd.read_csv(sample, nrows=0).columns.tolist()
    raw = [c for c in cols if c != "timestamp"]
    return list(GROUP_MAP.keys()) if group else raw

def load_month(year: int, month: int, *, group: bool = False) -> pd.DataFrame:
    path = _processed_dir(year) / f"{year}-{month:02d}.csv"
    df = pd.read_csv(path, parse_dates=["timestamp"]).set_index("timestamp")
    if not group:
        return df
    out = pd.DataFrame(index=df.index)
    for g, cols in GROUP_MAP.items():
        exist = [c for c in cols if c in df.columns]
        out[g] = df[exist].sum(axis=1) if exist else 0.0
    return out

def load_range(start: dt.datetime, end: dt.datetime, *, year: int | None = None, group: bool = False) -> pd.DataFrame:
    if year is None:
        if start.year != end.year:
            raise ValueError("Jahresübergreifend: bitte year=… explizit setzen.")
        year = start.year
    months = range(1, 13) if start.year != end.year else range(start.month, end.month + 1)
    parts = [load_month(year, m, group=group) for m in months]
    df = pd.concat(parts).sort_index()
    return df.loc[start:end]

def load_appliances(appliances: list[str], start: dt.datetime, end: dt.datetime, *, year: int | None = None, group: bool = False) -> pd.DataFrame:
    df = load_range(start, end, year=year, group=group)
    return df[appliances]

# -*- coding: utf-8 -*-
"""
Lastprofile-Dataloader (Step 4).
Greift auf data/lastprofile/processed/{year}/{year}-{month:02d}.csv zu.

Kompatibel zu powere.dataloaders.lastprofile:
- list_appliances(year, group=False)
- load_month(year, month, tz="Europe/Zurich", group=False)
- load_range(start, end, year=None, tz="Europe/Zurich", group=False)
- load_appliances(appliances, start, end, year=None, tz="Europe/Zurich", group=False)
"""
from pathlib import Path
from typing import List, Optional, Iterator, Tuple
import datetime as dt
import pandas as pd

# zentrale Datenwurzel aus dem Paket (zeigt via Symlink auf repo/data)
from powere.dataloaders.io import DATA_ROOT

BASE_DIR = DATA_ROOT / "lastprofile" / "processed"

# optionale Survey-Gruppierung (falls CSVs Roh-Spalten haben)
group_map = {
    "Geschirrspüler":                      ["Geschirrspüler"],
    "Backofen und Herd":                   ["Backofen und Herd"],
    "Fernseher und Entertainment-Systeme": ["Fernseher und Entertainment-Systeme"],
    "Bürogeräte":                          ["Bürogeräte"],
    "Waschmaschine":                       ["Waschmaschine"],
}

def _month_path(year: int, month: int) -> Path:
    p = BASE_DIR / f"{year}" / f"{year}-{month:02d}.csv"
    if not p.exists():
        raise FileNotFoundError(f"CSV nicht gefunden: {p}")
    return p

def _to_local_naive(ts: pd.Series, tz: str) -> pd.Series:
    # robust: sowohl tz-aware als auch naive Timestamps unterstützen
    s = pd.to_datetime(ts, errors="coerce")
    try:
        if hasattr(s.dt, "tz") and s.dt.tz is not None:  # Pylance-freundlich
            s = s.dt.tz_convert(tz).dt.tz_localize(None)
    except Exception:
        # falls nicht konvertierbar, lassen wir es wie es ist (naiv)
        pass
    return s

def _ym_iter(start: dt.datetime, end: dt.datetime) -> Iterator[Tuple[int, int]]:
    """Alle (Jahr, Monat) zwischen start und end inkl."""
    y, m = start.year, start.month
    while (y < end.year) or (y == end.year and m <= end.month):
        yield y, m
        m += 1
        if m == 13:
            y += 1
            m = 1

# 1) Welche Appliances (oder Gruppen) gibt es?
def list_appliances(year: int, *, group: bool = False) -> List[str]:
    # nimm den ersten vorhandenen Monat statt stur Januar
    for m in range(1, 13):
        p = BASE_DIR / f"{year}" / f"{year}-{m:02d}.csv"
        if p.exists():
            sample = pd.read_csv(p, nrows=1)
            raw = [c for c in sample.columns if c != "timestamp"]
            return list(group_map.keys()) if group else raw
    raise FileNotFoundError(f"Keine Monatsdateien für {year} unter {BASE_DIR}")

# 2) Einen Monat laden
def load_month(
    year: int,
    month: int,
    *,
    tz: str = "Europe/Zurich",
    group: bool = False
) -> pd.DataFrame:
    df = pd.read_csv(_month_path(year, month), parse_dates=["timestamp"])
    # Zeitindex Pylance-sicher setzen
    ts_idx: pd.DatetimeIndex = pd.DatetimeIndex(
        _to_local_naive(df["timestamp"], tz), name="timestamp"
    )
    df = df.drop(columns=["timestamp"]).set_index(ts_idx).sort_index()

    if not group:
        return df

    # Gruppierung anwenden (falls nötig)
    out = pd.DataFrame(index=df.index)
    for grp_name, cols in group_map.items():
        existing = [c for c in cols if c in df.columns]
        out[grp_name] = df[existing].sum(axis=1) if existing else 0.0
    return out

# 3) Bereich laden (über mehrere Monate/jahresübergreifend)
def load_range(
    start: dt.datetime,
    end: dt.datetime,
    *,
    year: Optional[int] = None,          # wenn gesetzt: ganzes Jahr laden
    tz: str = "Europe/Zurich",
    group: bool = False
) -> pd.DataFrame:
    if start > end:
        raise ValueError("start muss <= end sein")

    frames: List[pd.DataFrame] = []

    if year is not None:
        months = [(year, m) for m in range(1, 13)]
    else:
        months = list(_ym_iter(start, end))

    for y, m in months:
        try:
            frames.append(load_month(y, m, tz=tz, group=group))
        except FileNotFoundError:
            # fehlende Monate stillschweigend überspringen
            continue

    if not frames:
        return pd.DataFrame()

    full = pd.concat(frames).sort_index()
    return full.loc[start:end]

# 4) Nur bestimmte Appliances/Groups laden
def load_appliances(
    appliances: List[str],
    start: dt.datetime,
    end: dt.datetime,
    *,
    year: Optional[int] = None,
    tz: str = "Europe/Zurich",
    group: bool = False
) -> pd.DataFrame:
    df = load_range(start, end, year=year, tz=tz, group=group)
    if df.empty:
        return df
    missing = [a for a in appliances if a not in df.columns]
    if missing:
        raise KeyError(f"Spalten nicht gefunden: {missing}")
    return df[appliances]